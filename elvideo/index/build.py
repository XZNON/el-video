"""Orchestrator — run the stages, join them, validate, write.

Four producers feed this: ``probe``, ``scenes``, ``transcribe``, ``gemini``. ``quality`` needs
shot boundaries first. ``build_index`` joins all five into one ``footage_index.json`` and
validates it against the shared JSON Schema before writing.

Three things this module owns that nothing else does:

* **Alignment.** Gemini is handed our shot boundaries and answers by ``shot_index`` (D-010), so
  the join is an index lookup rather than a fuzzy timestamp match. Every ``t_start`` / ``t_end``
  written to the index comes from PySceneDetect; the model's own timestamps are second-granular
  and never reach the artifact. See ``docs/architecture.md`` § *Division of labour*.
* **Per-stage timing.** The <5 min budget is a per-stage claim, so "total: 4m12s" is not an
  acceptable log line. The A/B compares *where* each path spends time.
* **The one-call rule, checked rather than assumed.** ``gemini.generate_call_count()`` is read
  back after the understanding stage and a value other than 1 aborts the run. A 10-min video is
  100–300 shots; per-shot calls would blow the free tier's 10 RPM cap instantly, and this module
  is exactly where a well-meaning "just re-ask for the shots it missed" refactor would land.

See ``docs/IDEA.md`` § *Architecture (Path B)* and § *Definition of done*.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from elvideo.index import gemini, probe, quality, scenes, transcribe
from elvideo.index.gemini import DEFAULT_MEDIA_RESOLUTION, DEFAULT_SAMPLE_FPS
from elvideo.schema import validate_index
from elvideo.schema.models import (
    FootageIndex,
    IndexMeta,
    MediaResolution,
    Shot,
    ShotUnderstanding,
    Word,
)

__all__ = ["CANDIDATE_THRESHOLD", "OUTPUT_FILENAME", "align_understanding", "build_index"]

logger = logging.getLogger(__name__)

CANDIDATE_THRESHOLD = 0.65
"""``editorial_score`` at or above which a shot is flagged ``is_candidate``.

Not a magic number: it is the floor of the **strong** band in the scoring rubric
(``gemini.SYSTEM_INSTRUCTION``) — 0.65–0.84 "clear subject, purposeful motion, or a sound bite
that stands on its own", 0.85+ "hero moment". Anything below is the rubric's own "useful
connective tissue" or worse, which is real footage but not a moment to cut to.

Moving this does not lose data: ``is_candidate`` is a derived view over the full index (D-001), so
a different threshold is one pass over ``shots[]`` away. Recorded in ``state/decisions-log.md``
D-023, because ``index_meta`` has no field to carry it and adding one is a contract change."""

OUTPUT_FILENAME = "footage_index.json"
"""The s1 deliverable, written into ``work_dir`` (``docs/IDEA.md`` § *Storage & speed*)."""


def build_index(
    path: str,
    work_dir: str = "work",
    fps: float = DEFAULT_SAMPLE_FPS,
    media_resolution: MediaResolution = DEFAULT_MEDIA_RESOLUTION,
    *,
    threshold: float = scenes.DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """Run the full pipeline and return a validated ``footage_index.json`` document.

    Stages, in order: probe → shots → transcript → Gemini understanding → per-shot quality →
    join → validate → write. Each stage's wall-clock time is logged separately, then a total.

    Exactly one Gemini call is made, regardless of shot count — and the counter is read back to
    prove it rather than trusting that the code path is what it looks like.

    Args:
        path: Path to the source video.
        work_dir: Directory for keyframes and the output file. Gitignored.
        fps: Frames per second sampled for the Gemini call. Per-video knob.
        media_resolution: Token cost per frame for the Gemini call.
        threshold: ``ContentDetector`` threshold handed to
            :func:`~elvideo.index.scenes.detect_shots` — a per-video knob (D-012). Keyword-only,
            so the positional signature in ``docs/IDEA.md`` stays literally callable. The value
            used lands in ``index_meta.scene_threshold`` (D-013).

    Returns:
        The index as plain JSON-compatible data, already validated against
        ``footage_index.schema.json`` and already written to ``{work_dir}/footage_index.json``.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        RuntimeError: If the understanding stage did not issue exactly one Gemini call.
        ValueError: If the model returned a ``shot_index`` outside the detected shot range.
        jsonschema.ValidationError: If the assembled document violates the shared contract. The
            file is written only after validation passes, so a failure leaves nothing behind.
    """
    if not Path(path).is_file():
        raise FileNotFoundError(f"video not found: {path}")

    timings: dict[str, float] = {}
    started = time.perf_counter()
    gemini.reset_call_count()

    with _stage("probe", timings):
        video = probe.probe(path)

    with _stage("shots", timings):
        shots = scenes.detect_shots(path, threshold=threshold)

    with _stage("transcript", timings):
        words = transcribe.transcribe(path)

    with _stage("understand", timings):
        understanding = gemini.understand(path, fps, media_resolution, shots=shots)
    _assert_one_call()

    with _stage("quality", timings):
        for shot in shots:
            # shot_id is what makes work/keyframes/ match the ids in the index (D-018).
            shot.quality = quality.score_shot(
                path, shot.t_start, shot.t_end, work_dir, shot_id=shot.id
            )

    with _stage("join", timings):
        shots = align_understanding(shots, understanding)
        _apply_transcripts(shots, words)
        _flag_candidates(shots)
        doc = FootageIndex(
            video=video,
            index_meta=IndexMeta(
                path_variant="gemini",
                model=gemini.MODEL,
                media_resolution=media_resolution,
                sample_fps=fps,
                # The threshold is read off this run's call, not from the module constant, so an
                # index built with --threshold 20 says so (D-013). The detector itself is not
                # parameterized in detect_shots(), so the constant *is* what ran.
                scene_detector=scenes.DEFAULT_DETECTOR,
                scene_threshold=threshold,
            ),
            shots=shots,
            words=words,
        ).model_dump(mode="json")

    # Validation is the gate, not a postscript: attribute assignment on a pydantic model does not
    # re-validate, so this is the first point where the assembled document is actually checked.
    with _stage("validate", timings):
        validate_index(doc)

    with _stage("write", timings):
        out_path = _write(doc, work_dir)

    total_s = time.perf_counter() - started
    logger.info(
        "index built  %s  %d shots  %d words  %.1fs total (%s)",
        out_path,
        len(doc["shots"]),
        len(doc["words"]),
        total_s,
        " ".join(f"{name} {secs:.1f}s" for name, secs in timings.items()),
    )
    return doc


def align_understanding(shots: list[Shot], understanding: list[ShotUnderstanding]) -> list[Shot]:
    """Merge the model's judgment onto the frame-accurate shot list.

    **An index lookup on ``shot_index``, not an overlap match** (D-010). The model is given our
    boundaries in the prompt and answers per boundary, so there is nothing to guess at. The
    ``*_hint`` fields are ignored here entirely — they only matter on the free-segmentation path,
    which ``build_index`` does not use.

    ``caption``, ``editorial_score``, ``moment_reason`` and ``tags`` are copied across. **``id``,
    ``t_start`` and ``t_end`` are never touched** — they stay exactly as PySceneDetect returned
    them. Shots the model did not cover keep their defaults (``caption=""``,
    ``editorial_score=None``), so a short or empty response still yields a full, valid index: a
    structurally valid index with no judgment is a legible result, a crash is not.

    Args:
        shots: Frame-accurate shots from :func:`elvideo.index.scenes.detect_shots`.
        understanding: Per-shot judgment from :func:`elvideo.index.gemini.understand`.

    Returns:
        The same shot objects, mutated in place, with understanding fields populated where the
        model supplied them.

    Raises:
        ValueError: If a ``shot_index`` is outside ``range(len(shots))``, or if two entries claim
            the same index. Both mean the model ignored the boundaries it was given; dropping
            them silently would attach captions to the wrong shots with no error anywhere.
    """
    if not understanding:
        logger.warning(
            "understanding is empty - all %d shots keep empty captions and a null "
            "editorial_score; the index is still valid",
            len(shots),
        )
        return shots

    by_index: dict[int, ShotUnderstanding] = {}
    for item in understanding:
        if not 0 <= item.shot_index < len(shots):
            raise ValueError(
                f"shot_index {item.shot_index} is outside the detected range "
                f"0-{len(shots) - 1}: the model did not judge the shots it was given"
            )
        if item.shot_index in by_index:
            raise ValueError(f"duplicate shot_index {item.shot_index} in the understanding")
        by_index[item.shot_index] = item

    for i, shot in enumerate(shots):
        judgment = by_index.get(i)
        if judgment is None:
            continue
        shot.caption = judgment.caption
        shot.editorial_score = judgment.editorial_score
        shot.moment_reason = judgment.moment_reason
        shot.tags = list(judgment.tags)

    if len(by_index) < len(shots):
        missing = [shots[i].id for i in range(len(shots)) if i not in by_index]
        logger.warning(
            "understanding covers %d of %d shots; %d left with defaults (first few: %s)",
            len(by_index),
            len(shots),
            len(missing),
            ", ".join(missing[:5]),
        )
    return shots


@contextmanager
def _stage(name: str, timings: dict[str, float]) -> Iterator[None]:
    """Time one stage, log it on its own line, and record it for the summary.

    Timed in ``finally`` so a stage that raises still reports how long it ran before failing —
    which is the number you want when a stage is what blew the budget.
    """
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - started
        timings[name] = elapsed
        logger.info("stage %-10s %7.2fs", name, elapsed)


def _assert_one_call() -> None:
    """Fail the run if the understanding stage did not issue exactly one Gemini call.

    The hard constraint is *one call per video, never per shot* (``docs/IDEA.md`` § *Gemini call
    settings*, ``.claude/CLAUDE.md`` constraint 1). Checked against the counter rather than
    asserted in a comment — the point of the instrument is that a refactor cannot quietly break
    the rule. A count above 1 is also what a 429 retry storm looks like from here.
    """
    calls = gemini.generate_call_count()
    if calls != 1:
        raise RuntimeError(
            f"expected exactly 1 Gemini generate_content call for this video, counted {calls} - "
            f"see .claude/CLAUDE.md constraint 1 (one call per video, never per shot)"
        )
    logger.info("gemini generate_content calls: %d", calls)


def _apply_transcripts(shots: Sequence[Shot], words: list[Word]) -> None:
    """Slice the flat word list into per-shot transcripts.

    ``words_in_range`` is half-open on the right, so a word on a cut lands in exactly one shot.
    A silent shot gets ``""``, never ``None`` — the empty string is the claim "nothing was said
    here", which is what actually happened (``docs/schema.md``, the ``transcript`` field).
    """
    for shot in shots:
        in_shot = transcribe.words_in_range(words, shot.t_start, shot.t_end)
        shot.transcript = " ".join(word.w for word in in_shot)


def _flag_candidates(shots: Sequence[Shot]) -> None:
    """Derive ``is_candidate`` from ``editorial_score`` against :data:`CANDIDATE_THRESHOLD`.

    A shot with no score is not a candidate: an unjudged shot is unknown, not good. That keeps a
    Path A index — where ``editorial_score`` may be null throughout (``docs/schema.md``) — from
    coming out with every shot flagged or every shot silently rejected on a null comparison.
    """
    for shot in shots:
        shot.is_candidate = (
            shot.editorial_score is not None and shot.editorial_score >= CANDIDATE_THRESHOLD
        )


def _write(doc: dict[str, Any], work_dir: str) -> Path:
    """Write the validated document to ``{work_dir}/footage_index.json``.

    Written to a temporary file in the same directory and then renamed, so a crash mid-write
    cannot leave a half-written index where a valid one used to be. ``os.replace`` is atomic on
    both POSIX and Windows.

    Local filesystem only — no GCS, no Firestore (``docs/IDEA.md`` § *Storage & speed*).
    """
    out_dir = Path(work_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / OUTPUT_FILENAME
    tmp_path = out_path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
    os.replace(tmp_path, out_path)
    return out_path

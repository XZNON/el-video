"""Measure whether a caption describes the shot it is stored on — T011 criterion 1.

D-027 recorded the defect: on the `p2` index of ``in.mp4``, 13 of 17 hand-checked captions
describe a different shot than the one they are attached to. **Every automated gate in this repo
is a shape check, and a caption on the wrong shot has the right shape** — so the measurement has
to look at pictures, which is why it lived in a human spot-check until now.

This module makes that spot-check repeatable: a frozen sample (``alignment_sample.json``), a fixed
rubric, and a grader that scores each ``(keyframe, caption)`` pair *match / partial / mismatch*.
The sample is the same 17 shots T009 checked by hand, kept verbatim so a run after the fix
compares like with like against the published **2 match / 2 partial / 13 mismatch** baseline.

**The grader is a separate Gemini call and is not part of the index pipeline.** It never touches
:func:`elvideo.index.gemini.generate_call_count`, which counts index calls only and must stay at
1 per video (hard constraint 1). Grading is cheap by comparison — 17 stills at ``low`` resolution,
no video, no audio — and the whole sample is graded in **one** request, not one per shot.

The grader sees the frame and the caption. It is not told the T009 verdicts, so its agreement with
the human column is a calibration check on the grader itself rather than a foregone conclusion.

See ``tasks/T011-caption-shot-alignment.md``, ``state/decisions-log.md`` D-027, and
``docs/run-report.md`` § *The alignment failure*.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import cv2
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from elvideo.index.gemini import (
    MODEL,
    RETRY_MAX_ATTEMPTS,
    RETRY_WAIT_MAX_S,
    RETRY_WAIT_MULTIPLIER_S,
    SEED,
    check_api_key,
    is_rate_limited,
)
from elvideo.schema.models import FootageIndex

__all__ = [
    "FRAME_JPEG_QUALITY",
    "FRAME_MAX_WIDTH",
    "GRADER_PROMPT_VERSION",
    "GRADER_SYSTEM_INSTRUCTION",
    "GRADER_TEMPERATURE",
    "SAMPLE_PATH",
    "AgreementReport",
    "AlignmentSample",
    "Grade",
    "SampleShot",
    "Verdict",
    "grade_index",
    "load_sample",
    "report_markdown",
]

logger = logging.getLogger(__name__)

Verdict = Literal["match", "partial", "mismatch"]
"""The three-way verdict T009 used by hand, kept identical so the numbers are comparable."""

SAMPLE_PATH = Path(__file__).with_name("alignment_sample.json")
"""The committed sample. Frozen — changing it invalidates the comparison it exists to enable."""

GRADER_PROMPT_VERSION = "g1"
"""Bump on every grader-prompt edit. A report quotes the version that produced its numbers."""

FRAME_MAX_WIDTH = 768
"""Keyframes are downscaled to this width before being sent. At ``MEDIA_RESOLUTION_LOW`` the model
sees a small tile regardless, and 17 full-size PNGs would be ~16 MB base64 against a 20 MB inline
request ceiling."""

FRAME_JPEG_QUALITY = 85
"""JPEG quality for the downscaled frames. High enough that nothing a caption could name — a
person, a bottle, a boot floor — becomes unreadable."""

GRADER_TEMPERATURE = 0.0
"""Near-greedy. Unlike the index call (D-019, ``temperature=0.4``), grading wants no spread: the
same frame and the same caption should get the same verdict on every run."""

GRADER_SYSTEM_INSTRUCTION = """\
You are checking whether a caption describes the picture it is attached to. You are given still \
frames, each immediately preceded by the shot id and the caption stored on that shot. Each frame \
is taken from the exact middle of the shot the caption is stored on.

For each pair, return a verdict:

match - the caption describes THIS frame. The subject, the setting and the framing are the ones \
in the picture. Small differences of wording, or an action that plainly continues just outside \
the frame, are still a match.

partial - the caption belongs to this part of the video but does not describe this frame. The \
setting or the subject is right and the specific action, object or framing named in the caption \
is not visible.

mismatch - the caption describes something else. A different subject, a different place, a \
different object, or a person the frame does not contain.

Judge the picture, not the plausibility of the sentence. These captions are accurate descriptions \
of *some* moment in the source video; the question is only whether they describe THIS one. A \
caption naming a person the frame does not show, or an object the frame does not contain, is a \
mismatch no matter how well written it is.

reason - at most 12 words naming the deciding detail: what the frame shows versus what the \
caption claims. Do not restate the caption.

Return JSON only, one object per pair, in the order given.\
"""
"""Grader rubric. See :data:`GRADER_PROMPT_VERSION`."""

_PAIR_PROMPT = """\
{n} pairs follow. Grade every one, in order, and return exactly {n} objects.\
"""


class SampleShot(BaseModel):
    """One row of the frozen sample."""

    shot_id: str = Field(description="Index id, e.g. 'shot_059'. Names the keyframe file too.")
    t009_verdict: Verdict = Field(
        description="The human verdict from T009. Never shown to the grader."
    )


class AlignmentSample(BaseModel):
    """The committed sample list plus the baseline it is compared against."""

    video: str
    n: int
    rule: str = Field(description="How these shots were chosen. Frozen; see the JSON file.")
    source: str
    keyframe_pattern: str = Field(description="Where the keyframe for a shot_id lives.")
    baseline: dict[str, object]
    shots: list[SampleShot]

    def ids(self) -> list[str]:
        """Shot ids in sample order."""
        return [s.shot_id for s in self.shots]


class Grade(BaseModel):
    """One graded pair. Also the wire shape of the grader's response."""

    shot_id: str = Field(description="The shot id given with this frame.")
    verdict: Verdict = Field(description="match, partial, or mismatch.")
    reason: str = Field(description="At most 12 words naming the deciding detail.")


class AgreementReport(BaseModel):
    """The measurement. Written to disk so two runs can be diffed rather than remembered."""

    index_path: str
    prompt_version: str = Field(description="The index's PROMPT_VERSION, from index_meta or given.")
    grader_model: str
    grader_prompt_version: str
    sample_n: int
    match: int
    partial: int
    mismatch: int
    grades: list[Grade]
    agreement_with_t009: int = Field(
        description="How many verdicts equal the T009 human column. Calibration, not a target."
    )
    grader_tokens: int | None = Field(
        default=None, description="Total tokens for the grading call."
    )

    @property
    def clean_match_rate(self) -> str:
        """``'2/17'`` — the number T011 criterion 2 is written against."""
        return f"{self.match}/{self.sample_n}"


def load_sample(path: Path | None = None) -> AlignmentSample:
    """Load the frozen sample.

    Raises:
        FileNotFoundError: If the sample file is missing.
        ValueError: If it does not match :class:`AlignmentSample`, or if ``n`` disagrees with the
            number of rows — a silent truncation would make two runs incomparable while still
            producing a plausible number.
    """
    src = path or SAMPLE_PATH
    if not src.is_file():
        raise FileNotFoundError(f"alignment sample not found: {src}")
    try:
        sample = AlignmentSample.model_validate_json(src.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise ValueError(f"{src} is not a valid alignment sample: {exc}") from exc
    if sample.n != len(sample.shots):
        raise ValueError(f"{src} declares n={sample.n} but lists {len(sample.shots)} shots")
    return sample


def grade_index(
    index_path: str | Path,
    keyframes_dir: str | Path,
    *,
    sample: AlignmentSample | None = None,
    prompt_version: str = "",
) -> AgreementReport:
    """Grade one index's captions against its keyframes, in a single Gemini call.

    Args:
        index_path: A ``footage_index.json`` to measure.
        keyframes_dir: Directory of ``shot_###.png`` midpoint frames, as written by
            :func:`elvideo.index.quality.score_shot` (D-018 — this is why keyframe names match
            index ids).
        sample: Which shots to grade. Defaults to the frozen sample.
        prompt_version: The index's own ``PROMPT_VERSION``, for the report. Only needed because
            ``index_meta`` has no field for it (see :data:`elvideo.index.gemini.PROMPT_VERSION`).

    Returns:
        An :class:`AgreementReport`. ``match`` is the number T011 criterion 2 is written against.

    Raises:
        FileNotFoundError: If the index, a keyframe, or the sample file is missing.
        RuntimeError: If ``GEMINI_API_KEY`` is unset, if the rate limit survives the retries, or
            if the grader does not return exactly one verdict per sampled shot.
        ValueError: If a sampled shot is absent from the index.
    """
    chosen = sample or load_sample()
    index = _load_index(index_path)
    captions = _captions_for(index, chosen.ids())
    frames = _keyframes_for(Path(keyframes_dir), chosen.ids())

    grades = _grade(chosen.ids(), captions, frames)
    tally = Counter(g.verdict for g in grades)
    human = {s.shot_id: s.t009_verdict for s in chosen.shots}

    report = AgreementReport(
        index_path=str(index_path),
        prompt_version=prompt_version or _prompt_version_hint(index),
        grader_model=MODEL,
        grader_prompt_version=GRADER_PROMPT_VERSION,
        sample_n=len(chosen.shots),
        match=tally["match"],
        partial=tally["partial"],
        mismatch=tally["mismatch"],
        grades=grades,
        agreement_with_t009=sum(1 for g in grades if human.get(g.shot_id) == g.verdict),
        grader_tokens=_grader_tokens.get("total"),
    )
    logger.info(
        "alignment: %d match / %d partial / %d mismatch of %d (grader agrees with T009 on %d)",
        report.match,
        report.partial,
        report.mismatch,
        report.sample_n,
        report.agreement_with_t009,
    )
    return report


def report_markdown(report: AgreementReport, sample: AlignmentSample | None = None) -> str:
    """Render the report as the table that goes into ``docs/run-report.md``."""
    chosen = sample or load_sample()
    human = {s.shot_id: s.t009_verdict for s in chosen.shots}
    symbol = {"match": "match", "partial": "partial", "mismatch": "MISMATCH"}
    lines = [
        f"**{report.match} match / {report.partial} partial / {report.mismatch} mismatch "
        f"of {report.sample_n}** — index `{report.index_path}` (prompt `{report.prompt_version}`), "
        f"graded by `{report.grader_model}` rubric `{report.grader_prompt_version}`.",
        "",
        "| Shot | T009 (human) | Grader | Deciding detail |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| `{g.shot_id}` | {human.get(g.shot_id, '-')} | {symbol[g.verdict]} | {g.reason} |"
        for g in report.grades
    ]
    return "\n".join(lines)


_grader_tokens: dict[str, int] = {}
"""Token usage of the last grading call. Module-level for the same reason the index call counter
is: the report needs the number and threading it back through the parse would buy nothing."""


def _load_index(index_path: str | Path) -> FootageIndex:
    """Load and validate a ``footage_index.json``.

    Raises:
        FileNotFoundError: If the file is missing.
        ValueError: If it does not validate against the contract.
    """
    src = Path(index_path)
    if not src.is_file():
        raise FileNotFoundError(f"index not found: {src}")
    try:
        return FootageIndex.model_validate_json(src.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise ValueError(f"{src} does not validate against the index contract: {exc}") from exc


def _captions_for(index: FootageIndex, ids: Sequence[str]) -> dict[str, str]:
    """Caption per sampled shot.

    Raises:
        ValueError: If a sampled shot is not in the index, or has no caption to grade.
    """
    by_id = {s.id: s for s in index.shots}
    captions: dict[str, str] = {}
    for shot_id in ids:
        shot = by_id.get(shot_id)
        if shot is None:
            raise ValueError(f"{shot_id} is in the sample but not in the index")
        if not shot.caption.strip():
            raise ValueError(f"{shot_id} has an empty caption; nothing to grade")
        captions[shot_id] = shot.caption
    return captions


def _keyframes_for(keyframes_dir: Path, ids: Sequence[str]) -> dict[str, bytes]:
    """Read the midpoint keyframe for each sampled shot, re-encoded for the wire.

    The keyframes on disk are 1280x720 PNGs — 17 of them is ~12 MB, which base64s to ~16 MB
    against a 20 MB inline-request ceiling. They are also pointless at full size: the grading call
    runs at ``MEDIA_RESOLUTION_LOW``, so the model sees a small tile either way. See
    :data:`FRAME_MAX_WIDTH`.

    Raises:
        FileNotFoundError: If a keyframe is missing — grading a subset silently would produce a
            number that looks like the others and is not.
        RuntimeError: If a keyframe cannot be decoded or re-encoded.
    """
    frames: dict[str, bytes] = {}
    for shot_id in ids:
        png = keyframes_dir / f"{shot_id}.png"
        if not png.is_file():
            raise FileNotFoundError(f"keyframe missing for {shot_id}: {png}")
        frames[shot_id] = _encode_frame(png)
    return frames


def _encode_frame(png: Path) -> bytes:
    """Downscale one keyframe to :data:`FRAME_MAX_WIDTH` and JPEG-encode it.

    OpenCV rather than Pillow because ``elvideo.index.quality`` already depends on it — this adds
    no dependency to measure what that module wrote.

    Raises:
        RuntimeError: If the file cannot be decoded or the encode fails.
    """
    img = cv2.imread(str(png), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"could not decode keyframe {png}")
    h, w = img.shape[:2]
    if w > FRAME_MAX_WIDTH:
        scale = FRAME_MAX_WIDTH / w
        img = cv2.resize(
            img, (FRAME_MAX_WIDTH, max(1, round(h * scale))), interpolation=cv2.INTER_AREA
        )
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), FRAME_JPEG_QUALITY])
    if not ok:
        raise RuntimeError(f"could not JPEG-encode keyframe {png}")
    return bytes(buf.tobytes())


def _build_parts(
    ids: Sequence[str], captions: dict[str, str], frames: dict[str, bytes]
) -> list[types.Part]:
    """Interleave ``caption text -> frame`` so each picture is unambiguously paired with one claim.

    One request for the whole sample. Pairing by position in a single prompt is what keeps this
    from becoming a per-shot loop — the failure mode this project exists to avoid, applied to its
    own measurement.
    """
    parts: list[types.Part] = [types.Part(text=_PAIR_PROMPT.format(n=len(ids)))]
    for shot_id in ids:
        parts.append(types.Part(text=f"{shot_id} caption: {captions[shot_id]}"))
        parts.append(types.Part.from_bytes(data=frames[shot_id], mime_type="image/jpeg"))
    return parts


def _grade(
    ids: Sequence[str], captions: dict[str, str], frames: dict[str, bytes]
) -> list[Grade]:
    """Issue the one grading request and validate its verdicts against the sample.

    Raises:
        RuntimeError: If ``GEMINI_API_KEY`` is unset, if the rate limit survives the retries, or
            if the response is not one verdict per sampled shot.
    """
    check_api_key()
    load_dotenv()
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"].strip())

    config = types.GenerateContentConfig(
        system_instruction=GRADER_SYSTEM_INSTRUCTION,
        media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
        response_mime_type="application/json",
        response_schema=list[Grade],
        temperature=GRADER_TEMPERATURE,
        seed=SEED,
    )
    contents = types.Content(role="user", parts=_build_parts(ids, captions, frames))

    def _once() -> types.GenerateContentResponse:
        logger.info(
            "alignment grader request model=%s rubric=%s pairs=%d",
            MODEL,
            GRADER_PROMPT_VERSION,
            len(ids),
        )
        return client.models.generate_content(model=MODEL, contents=contents, config=config)

    retryer = Retrying(
        retry=retry_if_exception(is_rate_limited),
        wait=wait_exponential(multiplier=RETRY_WAIT_MULTIPLIER_S, max=RETRY_WAIT_MAX_S),
        stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
        reraise=False,
    )
    try:
        response = retryer(_once)
    except RetryError as exc:
        raise RuntimeError(
            f"Gemini returned HTTP 429 on all {RETRY_MAX_ATTEMPTS} attempts of the alignment "
            f"grading call: {exc.last_attempt.exception()}"
        ) from exc

    usage = response.usage_metadata
    total = getattr(usage, "total_token_count", None) if usage else None
    _grader_tokens.clear()
    if isinstance(total, int):
        _grader_tokens["total"] = total

    return _parse_grades(response.text, ids)


def _parse_grades(text: str | None, ids: Sequence[str]) -> list[Grade]:
    """Validate the grader's JSON into one :class:`Grade` per sampled shot, in sample order.

    Raises:
        RuntimeError: If the body is missing, is not a JSON array of the expected shape, or does
            not cover the sample exactly once. A partial grading would still produce a ratio, and
            a ratio over an unknown denominator is the kind of number this task exists to stop
            trusting.
    """
    if not text or not text.strip():
        raise RuntimeError("alignment grader returned no text; nothing to parse")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"alignment grader response is not valid JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise RuntimeError(
            f"alignment grader returned {type(payload).__name__}, expected a JSON array"
        )

    try:
        grades = [Grade.model_validate(raw) for raw in payload]
    except ValidationError as exc:
        raise RuntimeError(f"alignment grader response does not match Grade: {exc}") from exc

    by_id = {g.shot_id: g for g in grades}
    if len(by_id) != len(grades):
        raise RuntimeError("alignment grader returned duplicate shot_id values")
    missing = [i for i in ids if i not in by_id]
    extra = [g.shot_id for g in grades if g.shot_id not in set(ids)]
    if missing or extra:
        raise RuntimeError(
            f"alignment grader did not cover the sample: missing={missing} unexpected={extra}"
        )
    return [by_id[i] for i in ids]


def _prompt_version_hint(index: FootageIndex) -> str:
    """Best-effort label for which index this is. ``index_meta`` carries no prompt version."""
    return f"{index.index_meta.model}@fps{index.index_meta.sample_fps}"


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m elvideo.eval.alignment work/footage_index.json`` — grade and print."""
    parser = argparse.ArgumentParser(description="Measure caption/keyframe agreement (T011).")
    parser.add_argument("index", help="Path to a footage_index.json")
    parser.add_argument("--keyframes", default="work/keyframes", help="Keyframe directory")
    parser.add_argument("--prompt-version", default="", help="The index's PROMPT_VERSION")
    parser.add_argument("--out", default="", help="Write the report JSON here as well")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    report = grade_index(
        args.index, args.keyframes, prompt_version=args.prompt_version
    )
    print(report_markdown(report))
    if args.out:
        Path(args.out).write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover - thin entry point
    raise SystemExit(main())

"""Orchestrator tests — the join, the one-call rule, and what lands on disk.

Two halves, deliberately separated:

* **Alignment** is pure and gets synthetic inputs — no video, no API, no mocks. It is the part
  that can silently attach a caption to the wrong shot, so it is tested on its own.
* **``build_index``** runs against every stage mocked out, including the Gemini call: T004 is
  code-complete but its key has no quota (D-021), and none of this task's criteria are about
  whether the model answers. The stage boundaries are what is under test here.

See ``tasks/T007-build-orchestrator.md``.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from elvideo.index import build
from elvideo.index.build import CANDIDATE_THRESHOLD, align_understanding, build_index
from elvideo.schema import validate_index
from elvideo.schema.models import MediaResolution, Shot, ShotUnderstanding, VideoMeta, Word


def _shots(n: int = 4) -> list[Shot]:
    """``n`` back-to-back 2s shots, exactly as ``detect_shots`` would return them."""
    return [Shot(id=f"shot_{i:03d}", t_start=2.0 * i, t_end=2.0 * (i + 1)) for i in range(n)]


def _judgment(index: int, score: float = 0.5, **overrides: Any) -> ShotUnderstanding:
    fields: dict[str, Any] = {
        "shot_index": index,
        "caption": f"caption {index}",
        "editorial_score": score,
        "moment_reason": f"reason {index}",
        "tags": ["food", "wide"],
    }
    fields.update(overrides)
    return ShotUnderstanding(**fields)


# --------------------------------------------------------------------------------------------
# align_understanding — synthetic inputs, no video
# --------------------------------------------------------------------------------------------


def test_alignment_exact_one_to_one() -> None:
    """The normal case: one judgment per detected shot, matched by ``shot_index``."""
    shots = _shots()
    aligned = align_understanding(shots, [_judgment(i, 0.1 * i) for i in range(4)])

    assert [s.caption for s in aligned] == [f"caption {i}" for i in range(4)]
    assert [s.editorial_score for s in aligned] == [pytest.approx(0.1 * i) for i in range(4)]
    assert [s.moment_reason for s in aligned] == [f"reason {i}" for i in range(4)]
    assert all(s.tags == ["food", "wide"] for s in aligned)


def test_alignment_never_touches_timings_or_ids() -> None:
    """PySceneDetect owns ``t_start`` / ``t_end``. The model's hints are not even read here."""
    shots = _shots()
    before = [(s.id, s.t_start, s.t_end) for s in shots]

    aligned = align_understanding(
        shots, [_judgment(i, t_start_hint=99.0, t_end_hint=100.0) for i in range(4)]
    )

    assert [(s.id, s.t_start, s.t_end) for s in aligned] == before


def test_alignment_survives_fewer_segments_than_shots() -> None:
    """40 segments for 120 shots must not crash, drop shots, or shift the mapping."""
    shots = _shots(120)
    aligned = align_understanding(shots, [_judgment(i, 0.9) for i in (0, 7, 119)])

    assert len(aligned) == 120
    for i, shot in enumerate(aligned):
        if i in (0, 7, 119):
            assert shot.caption == f"caption {i}"
            assert shot.editorial_score == pytest.approx(0.9)
        else:
            assert shot.caption == ""
            assert shot.editorial_score is None
            assert shot.moment_reason is None
            assert shot.tags == []


def test_alignment_with_no_understanding_at_all() -> None:
    """A call that succeeds but returns nothing usable still yields a full, valid index.

    A structurally valid index with no judgment is a legible result; a crash is not.
    """
    shots = _shots()
    aligned = align_understanding(shots, [])

    assert len(aligned) == 4
    assert all(s.caption == "" and s.editorial_score is None for s in aligned)


@pytest.mark.parametrize("bad_index", [4, 40, 999])
def test_alignment_fails_loudly_on_out_of_range_index(bad_index: int) -> None:
    """D-010: an index outside the real range means the model ignored the boundaries it got.

    Dropping it silently would put captions on the wrong shots with no error anywhere.
    """
    with pytest.raises(ValueError, match="outside the detected range"):
        align_understanding(_shots(), [_judgment(0), _judgment(bad_index)])


def test_alignment_fails_loudly_on_negative_index() -> None:
    """``ShotUnderstanding`` already rejects a negative index, so this cannot even be built."""
    with pytest.raises(ValueError):
        _judgment(-1)


def test_alignment_fails_loudly_on_duplicate_index() -> None:
    """Two judgments for one shot means one shot's judgment belongs to another shot."""
    with pytest.raises(ValueError, match="duplicate shot_index"):
        align_understanding(_shots(), [_judgment(1), _judgment(1, 0.9)])


def test_alignment_more_segments_than_shots_is_out_of_range() -> None:
    """The model returning *more* shots than were detected is the same failure, not a truncation."""
    with pytest.raises(ValueError, match="outside the detected range"):
        align_understanding(_shots(2), [_judgment(i) for i in range(5)])


def test_alignment_does_not_alias_the_model_tag_list() -> None:
    """A shared list would let a later mutation of one shot's tags rewrite the model's output."""
    judgment = _judgment(0)
    aligned = align_understanding(_shots(1), [judgment])
    aligned[0].tags.append("extra")

    assert judgment.tags == ["food", "wide"]


def test_alignment_warns_when_shots_are_left_unjudged(caplog: pytest.LogCaptureFixture) -> None:
    """A short response is recoverable, but it must be visible in the log."""
    with caplog.at_level(logging.WARNING, logger="elvideo.index.build"):
        align_understanding(_shots(4), [_judgment(0)])

    assert "covers 1 of 4 shots" in caplog.text


# --------------------------------------------------------------------------------------------
# build_index — every stage mocked
# --------------------------------------------------------------------------------------------


@dataclass
class FakePipeline:
    """Stand-ins for the five producer stages, plus a record of how they were called."""

    video_path: Path
    order: list[str] = field(default_factory=list)
    quality_calls: list[dict[str, Any]] = field(default_factory=list)
    understand_calls: list[dict[str, Any]] = field(default_factory=list)
    detect_calls: list[dict[str, Any]] = field(default_factory=list)
    shot_count: int = 4
    understanding: list[ShotUnderstanding] | None = None
    words: list[Word] | None = None
    call_count: int = 1
    attempt_count: int = 1


@pytest.fixture
def pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakePipeline:
    """Patch out probe / scenes / transcribe / gemini / quality, leaving the joins real.

    ``words_in_range`` is deliberately **not** mocked — slicing the flat word list per shot is
    one of the two joins this task owns, so it runs for real against synthetic words.
    """
    video_path = tmp_path / "in.mp4"
    video_path.write_bytes(b"not really a video")
    fake = FakePipeline(video_path=video_path)

    fake.words = [
        Word(t=0.5, d=0.2, w="hello"),
        Word(t=1.2, d=0.3, w="world"),
        # nothing in [2.0, 4.0) - shot_001 is silent
        Word(t=4.1, d=0.2, w="third"),
        Word(t=6.5, d=0.2, w="fourth"),
    ]
    fake.understanding = [
        _judgment(0, 0.90),
        _judgment(1, 0.64),
        _judgment(2, CANDIDATE_THRESHOLD),
        _judgment(3, 0.10),
    ]

    def fake_probe(path: str) -> VideoMeta:
        fake.order.append("probe")
        return VideoMeta(path=path, duration_s=8.0, fps=25.0, w=1280, h=720)

    def fake_detect(path: str, threshold: float = 27.0) -> list[Shot]:
        fake.order.append("shots")
        fake.detect_calls.append({"path": path, "threshold": threshold})
        return _shots(fake.shot_count)

    def fake_transcribe(path: str, **kwargs: Any) -> list[Word]:
        fake.order.append("transcript")
        assert fake.words is not None
        return list(fake.words)

    def fake_understand(
        path: str,
        fps: float = 0.5,
        media_resolution: MediaResolution = "low",
        *,
        shots: list[Shot] | None = None,
    ) -> list[ShotUnderstanding]:
        fake.order.append("understand")
        fake.understand_calls.append(
            {"path": path, "fps": fps, "media_resolution": media_resolution, "shots": shots}
        )
        return list(fake.understanding or [])

    def fake_score_shot(
        path: str, t_start: float, t_end: float, work_dir: str, *, shot_id: str | None = None
    ) -> float:
        if "quality" not in fake.order:
            fake.order.append("quality")
        fake.quality_calls.append(
            {"t_start": t_start, "t_end": t_end, "work_dir": work_dir, "shot_id": shot_id}
        )
        return 0.42

    monkeypatch.setattr(build.probe, "probe", fake_probe)
    monkeypatch.setattr(build.scenes, "detect_shots", fake_detect)
    monkeypatch.setattr(build.transcribe, "transcribe", fake_transcribe)
    monkeypatch.setattr(build.gemini, "understand", fake_understand)
    monkeypatch.setattr(build.gemini, "generate_call_count", lambda: fake.call_count)
    monkeypatch.setattr(build.gemini, "generate_attempt_count", lambda: fake.attempt_count)
    monkeypatch.setattr(build.gemini, "reset_call_count", lambda: None)
    monkeypatch.setattr(build.quality, "score_shot", fake_score_shot)
    return fake


def test_missing_video_fails_before_any_stage(pipeline: FakePipeline, tmp_path: Path) -> None:
    """Cheapest possible failure: no ffprobe, no model download, no upload."""
    with pytest.raises(FileNotFoundError, match="video not found"):
        build_index(str(tmp_path / "nope.mp4"), work_dir=str(tmp_path / "work"))

    assert pipeline.order == []


def test_stage_order(
    pipeline: FakePipeline, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """probe -> shots -> transcript -> Gemini -> quality -> join -> validate -> write.

    Checked twice over: the producers record the order they were actually called in, and the
    stage log — which is what a human reads after a real run — must tell the same story.
    """
    with caplog.at_level(logging.INFO, logger="elvideo.index.build"):
        build_index(str(pipeline.video_path), work_dir=str(tmp_path / "work"))

    assert pipeline.order == ["probe", "shots", "transcript", "understand", "quality"]
    messages = [record.getMessage() for record in caplog.records]
    logged = [msg.split()[1] for msg in messages if msg.startswith("stage ")]
    assert logged == [
        "probe",
        "shots",
        "transcript",
        "understand",
        "quality",
        "join",
        "validate",
        "write",
    ]


def test_output_validates_and_is_written(pipeline: FakePipeline, tmp_path: Path) -> None:
    """The returned document is the written document, and both satisfy the shared contract."""
    work = tmp_path / "work"
    doc = build_index(str(pipeline.video_path), work_dir=str(work))

    validate_index(doc)
    written = json.loads((work / "footage_index.json").read_text(encoding="utf-8"))
    assert written == doc


def test_every_detected_shot_appears(pipeline: FakePipeline, tmp_path: Path) -> None:
    """Full index, not top-N (D-001) — including the shots that scored badly."""
    pipeline.shot_count = 120
    pipeline.understanding = [_judgment(i, 0.9) for i in (0, 5)]

    doc = build_index(str(pipeline.video_path), work_dir=str(tmp_path / "work"))

    assert [s["id"] for s in doc["shots"]] == [f"shot_{i:03d}" for i in range(120)]


def test_exactly_one_gemini_call_is_required(pipeline: FakePipeline, tmp_path: Path) -> None:
    """The counter is the instrument behind the one-call rule; a run that reads 1 proceeds."""
    build_index(str(pipeline.video_path), work_dir=str(tmp_path / "work"))

    assert len(pipeline.understand_calls) == 1


@pytest.mark.parametrize("counted", [0, 2, 117])
def test_wrong_gemini_call_count_aborts_the_run(
    pipeline: FakePipeline, tmp_path: Path, counted: int
) -> None:
    """Per-shot calls would blow the 10 RPM free-tier cap — the run stops rather than continues.

    Nothing is written: the abort happens before quality, join, validate or write.
    """
    pipeline.call_count = counted
    pipeline.attempt_count = counted
    work = tmp_path / "work"

    with pytest.raises(RuntimeError, match="exactly 1 Gemini"):
        build_index(str(pipeline.video_path), work_dir=str(work))

    assert not (work / "footage_index.json").exists()


def test_a_429_retry_does_not_abort_a_run_that_succeeded(
    pipeline: FakePipeline, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """One request, two transport attempts — the run completes and the index is written.

    T013. Before it, ``build.py`` read the attempt count and aborted here, discarding ~235s of
    finished work over a 429 the D-020 backoff had already absorbed.
    """
    pipeline.call_count = 1
    pipeline.attempt_count = 2
    work = tmp_path / "work"

    with caplog.at_level(logging.WARNING, logger="elvideo.index.build"):
        build_index(str(pipeline.video_path), work_dir=str(work))

    assert (work / "footage_index.json").exists()
    assert any("429 retries" in r.getMessage() for r in caplog.records)


def test_understand_gets_the_detected_boundaries(pipeline: FakePipeline, tmp_path: Path) -> None:
    """D-010: the model judges *our* shots, which is what makes alignment an index lookup."""
    build_index(str(pipeline.video_path), work_dir=str(tmp_path / "work"))

    passed = pipeline.understand_calls[0]["shots"]
    assert [s.id for s in passed] == ["shot_000", "shot_001", "shot_002", "shot_003"]


def test_index_meta_records_what_actually_ran(pipeline: FakePipeline, tmp_path: Path) -> None:
    """Non-default knobs on every axis — ``index_meta`` must report the run, not the defaults."""
    doc = build_index(
        str(pipeline.video_path),
        work_dir=str(tmp_path / "work"),
        fps=2.0,
        media_resolution="medium",
        threshold=20.0,
    )

    assert doc["index_meta"] == {
        "path_variant": "gemini",
        "model": "gemini-3.5-flash",
        "media_resolution": "medium",
        "sample_fps": 2.0,
        "scene_detector": "ContentDetector",
        "scene_threshold": 20.0,
    }
    assert pipeline.understand_calls[0]["fps"] == 2.0
    assert pipeline.understand_calls[0]["media_resolution"] == "medium"
    assert pipeline.detect_calls[0]["threshold"] == 20.0


def test_scene_threshold_is_read_off_the_call_not_the_constant(
    pipeline: FakePipeline, tmp_path: Path
) -> None:
    """D-013: the same threshold reaches ``detect_shots`` and ``index_meta``, or neither means
    anything."""
    doc = build_index(str(pipeline.video_path), work_dir=str(tmp_path / "work"), threshold=31.5)

    assert doc["index_meta"]["scene_threshold"] == pipeline.detect_calls[0]["threshold"] == 31.5


def test_transcript_is_sliced_per_shot(pipeline: FakePipeline, tmp_path: Path) -> None:
    """Words joined from ``words_in_range``; a silent shot gets ``""``, never ``None``."""
    doc = build_index(str(pipeline.video_path), work_dir=str(tmp_path / "work"))

    assert [s["transcript"] for s in doc["shots"]] == ["hello world", "", "third", "fourth"]


def test_words_are_carried_through_flat(pipeline: FakePipeline, tmp_path: Path) -> None:
    """``words[]`` is the whole video's timing, not a per-shot nesting."""
    doc = build_index(str(pipeline.video_path), work_dir=str(tmp_path / "work"))

    assert doc["words"] == [
        {"t": 0.5, "d": 0.2, "w": "hello"},
        {"t": 1.2, "d": 0.3, "w": "world"},
        {"t": 4.1, "d": 0.2, "w": "third"},
        {"t": 6.5, "d": 0.2, "w": "fourth"},
    ]


def test_is_candidate_is_derived_at_the_documented_threshold(
    pipeline: FakePipeline, tmp_path: Path
) -> None:
    """Scores are 0.90 / 0.64 / 0.65 / 0.10 against a 0.65 floor — the boundary is inclusive."""
    doc = build_index(str(pipeline.video_path), work_dir=str(tmp_path / "work"))

    assert [s["is_candidate"] for s in doc["shots"]] == [True, False, True, False]


def test_unjudged_shots_are_not_candidates(pipeline: FakePipeline, tmp_path: Path) -> None:
    """A null score is unknown, not good — this is the shape a Path A index arrives in."""
    pipeline.understanding = []

    doc = build_index(str(pipeline.video_path), work_dir=str(tmp_path / "work"))

    assert all(s["editorial_score"] is None for s in doc["shots"])
    assert not any(s["is_candidate"] for s in doc["shots"])
    validate_index(doc)


def test_quality_is_scored_per_shot_with_the_index_id(
    pipeline: FakePipeline, tmp_path: Path
) -> None:
    """D-018: keyframes are named after the index ids, or ``work/keyframes/`` is useless."""
    work = tmp_path / "work"
    doc = build_index(str(pipeline.video_path), work_dir=str(work))

    assert [c["shot_id"] for c in pipeline.quality_calls] == [
        "shot_000",
        "shot_001",
        "shot_002",
        "shot_003",
    ]
    assert [c["t_start"] for c in pipeline.quality_calls] == [0.0, 2.0, 4.0, 6.0]
    assert all(c["work_dir"] == str(work) for c in pipeline.quality_calls)
    assert all(s["quality"] == 0.42 for s in doc["shots"])


def test_embedding_is_null_on_every_shot(pipeline: FakePipeline, tmp_path: Path) -> None:
    """RESERVED field — present in the output, never computed (``docs/IDEA.md`` § *Non-goals*)."""
    doc = build_index(str(pipeline.video_path), work_dir=str(tmp_path / "work"))

    assert all(s["embedding"] is None for s in doc["shots"])


def test_per_stage_timing_is_logged(
    pipeline: FakePipeline, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """"Total: 4m12s" alone fails the criterion — the A/B compares *where* time goes."""
    with caplog.at_level(logging.INFO, logger="elvideo.index.build"):
        build_index(str(pipeline.video_path), work_dir=str(tmp_path / "work"))

    stages = ("probe", "shots", "transcript", "understand", "quality", "join", "validate", "write")
    for stage in stages:
        assert f"stage {stage}" in caplog.text
    assert "total" in caplog.text


def test_validation_failure_leaves_no_file_behind(
    pipeline: FakePipeline, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The contract is a gate, not a postscript: nothing is written unless it validates."""
    work = tmp_path / "work"

    def boom(doc: dict[str, Any]) -> None:
        raise ValidationError("$.shots[0].quality: 2.0 is greater than the maximum of 1")

    monkeypatch.setattr(build, "validate_index", boom)

    with pytest.raises(ValidationError):
        build_index(str(pipeline.video_path), work_dir=str(work))

    assert not (work / "footage_index.json").exists()
    assert not work.exists() or not list(work.glob("*.tmp"))


def test_out_of_range_shot_index_aborts_the_build(pipeline: FakePipeline, tmp_path: Path) -> None:
    """The loud failure from ``align_understanding`` propagates instead of writing a bad index."""
    pipeline.understanding = [_judgment(0), _judgment(99)]
    work = tmp_path / "work"

    with pytest.raises(ValueError, match="outside the detected range"):
        build_index(str(pipeline.video_path), work_dir=str(work))

    assert not (work / "footage_index.json").exists()


def test_work_dir_is_created_if_absent(pipeline: FakePipeline, tmp_path: Path) -> None:
    """First run on a fresh clone has no ``work/``."""
    work = tmp_path / "nested" / "work"
    build_index(str(pipeline.video_path), work_dir=str(work))

    assert (work / "footage_index.json").is_file()


# --------------------------------------------------------------------------------------------
# Real video — everything runs for real except the Gemini call (D-021)
# --------------------------------------------------------------------------------------------

IN_MP4 = Path(__file__).resolve().parents[1] / "in.mp4"


@pytest.mark.slow
@pytest.mark.skipif(not IN_MP4.is_file(), reason="A/B test video not present (D-003, gitignored)")
def test_real_video_full_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole pipeline on ``in.mp4`` — probe, PySceneDetect, WhisperX and OpenCV all real.

    **The understanding stage is mocked, and that is not a detail to gloss:** the key in ``.env``
    has no quota (D-021), so no live Gemini call is possible. What this test proves is everything
    around the model — that 117 real shots survive the joins, that the transcript slicing lines up
    with real word timings, that the keyframes match the ids, and that the document the pipeline
    assembles satisfies the contract. What it cannot prove is anything about caption or
    ``editorial_score`` quality.

    The wall-clock assertion is likewise a floor, not the budget check: the missing stage is one
    Gemini call. The real <5 min number needs a working key.
    """
    scores = [round(0.05 + (i % 19) / 20.0, 3) for i in range(500)]

    def mock_understand(
        path: str,
        fps: float = 0.5,
        media_resolution: MediaResolution = "low",
        *,
        shots: list[Shot] | None = None,
    ) -> list[ShotUnderstanding]:
        logging.getLogger("elvideo.index.build").warning(
            "GEMINI STAGE IS MOCKED - no live call was made (D-021, key has no quota)"
        )
        assert shots is not None
        return [_judgment(i, scores[i]) for i in range(len(shots))]

    monkeypatch.setattr(build.gemini, "understand", mock_understand)
    monkeypatch.setattr(build.gemini, "generate_call_count", lambda: 1)

    started = time.perf_counter()
    doc = build_index(str(IN_MP4), work_dir=str(tmp_path))
    elapsed = time.perf_counter() - started

    shots = doc["shots"]
    assert len(shots) == 117, "D-003/D-012: 117 shots at ContentDetector(threshold=27.0)"
    assert shots[0]["t_start"] == 0.0
    # Gapless: every shot starts exactly where the previous one ended.
    assert all(a["t_end"] == b["t_start"] for a, b in zip(shots, shots[1:], strict=False))
    # D-014: the container outlives the video stream by 0.066s on this clip, so compare loosely.
    assert doc["video"]["duration_s"] - shots[-1]["t_end"] < 0.1

    assert [s["id"] for s in shots] == [f"shot_{i:03d}" for i in range(117)]
    assert all(s["embedding"] is None for s in shots)
    assert all(0.0 <= s["quality"] <= 1.0 for s in shots)
    assert len(doc["words"]) > 1000, "in.mp4 has ~1436 words (D-015)"
    assert sum(1 for s in shots if s["transcript"]) > 100, "only ~7 of 117 shots are silent"

    keyframes = sorted(p.stem for p in (tmp_path / "keyframes").glob("shot_*.png"))
    assert keyframes == [f"shot_{i:03d}" for i in range(117)], "D-018: keyframes match index ids"

    written = json.loads((tmp_path / "footage_index.json").read_text(encoding="utf-8"))
    assert written == doc
    validate_index(written)

    assert elapsed < 300.0, f"budget is 300s of wall-clock, took {elapsed:.1f}s"

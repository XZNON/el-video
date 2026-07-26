"""Tests for T011 — ``elvideo.eval.alignment``.

The grading call is mocked. What is worth asserting without spending a token is that the
*measurement* is honest: the frozen sample stays frozen, a partial or padded response is refused
rather than turned into a ratio, and grading never touches the one-call-per-video counter that
hard constraint 1 is enforced through.

See ``tasks/T011-caption-shot-alignment.md``.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from elvideo.eval import alignment
from elvideo.eval.alignment import (
    AgreementReport,
    Grade,
    grade_index,
    load_sample,
    report_markdown,
)
from elvideo.index import gemini
from elvideo.schema.models import FootageIndex, IndexMeta, Shot, VideoMeta

SAMPLE_IDS = load_sample().ids()


# --- fakes ---------------------------------------------------------------------------------


def _response(payload: Any, *, total_tokens: int | None = 3000) -> SimpleNamespace:
    return SimpleNamespace(
        text=json.dumps(payload),
        usage_metadata=SimpleNamespace(total_token_count=total_tokens),
    )


class _FakeClient:
    def __init__(self, response: Any) -> None:
        self.calls: list[dict[str, Any]] = []
        outer = self

        class _Models:
            def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
                outer.calls.append({"model": model, "contents": contents, "config": config})
                return response

        self.models = _Models()


def _index(ids: list[str], caption: str = "a caption") -> FootageIndex:
    return FootageIndex(
        video=VideoMeta(path="in.mp4", duration_s=10.0, fps=25.0, w=1280, h=720),
        index_meta=IndexMeta(
            path_variant="gemini",
            model="gemini-3.5-flash",
            media_resolution="low",
            sample_fps=0.5,
            scene_detector="ContentDetector",
            scene_threshold=27.0,
        ),
        shots=[
            Shot(id=i, t_start=n * 2.0, t_end=n * 2.0 + 2.0, caption=caption)
            for n, i in enumerate(ids)
        ],
        words=[],
    )


@pytest.fixture
def graded(tmp_path: Path) -> tuple[Path, Path]:
    """An index and a keyframe directory covering the frozen sample."""
    index_path = tmp_path / "footage_index.json"
    index_path.write_text(_index(SAMPLE_IDS).model_dump_json(), encoding="utf-8")

    frames = tmp_path / "keyframes"
    frames.mkdir()
    png = Path("work/keyframes/shot_000.png")
    blob = png.read_bytes() if png.is_file() else _blank_png()
    for shot_id in SAMPLE_IDS:
        (frames / f"{shot_id}.png").write_bytes(blob)
    return index_path, frames


def _blank_png() -> bytes:
    """A 2x2 PNG, for machines without the gitignored ``work/`` artifacts."""
    import cv2
    import numpy as np

    ok, buf = cv2.imencode(".png", np.zeros((2, 2, 3), dtype=np.uint8))
    assert ok
    return bytes(buf.tobytes())


def _verdicts(*, ids: list[str] | None = None, verdict: str = "match") -> list[dict[str, str]]:
    chosen = ids if ids is not None else SAMPLE_IDS
    return [{"shot_id": i, "verdict": verdict, "reason": "r"} for i in chosen]


# --- the frozen sample ------------------------------------------------------------------------


def test_sample_is_the_17_shots_t009_checked() -> None:
    """Frozen. Changing it invalidates the comparison against 2 match / 2 partial / 13 mismatch."""
    sample = load_sample()
    assert sample.n == 17
    assert len(sample.shots) == 17
    assert sample.baseline["match"] == 2
    assert sample.baseline["partial"] == 2
    assert sample.baseline["mismatch"] == 13
    assert {"shot_000", "shot_005", "shot_059", "shot_105", "shot_116"} <= set(sample.ids())


def test_sample_declared_size_must_match_its_rows(tmp_path: Path) -> None:
    """A truncated sample would still produce a plausible ratio over a different denominator."""
    src = tmp_path / "sample.json"
    doc = json.loads(alignment.SAMPLE_PATH.read_text(encoding="utf-8"))
    doc["shots"] = doc["shots"][:5]
    src.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="declares n=17 but lists 5"):
        load_sample(src)


# --- response handling ------------------------------------------------------------------------


def test_partial_grading_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="did not cover the sample: missing="):
        alignment._parse_grades(json.dumps(_verdicts(ids=SAMPLE_IDS[:10])), SAMPLE_IDS)


def test_unexpected_shot_ids_are_refused() -> None:
    payload = _verdicts(ids=[*SAMPLE_IDS[:-1], "shot_999"])
    with pytest.raises(RuntimeError, match="unexpected=\\['shot_999'\\]"):
        alignment._parse_grades(json.dumps(payload), SAMPLE_IDS)


def test_duplicate_verdicts_are_refused() -> None:
    payload = _verdicts(ids=[SAMPLE_IDS[0], *SAMPLE_IDS])
    with pytest.raises(RuntimeError, match="duplicate shot_id"):
        alignment._parse_grades(json.dumps(payload), SAMPLE_IDS)


def test_grades_come_back_in_sample_order() -> None:
    payload = _verdicts(ids=list(reversed(SAMPLE_IDS)))
    grades = alignment._parse_grades(json.dumps(payload), SAMPLE_IDS)
    assert [g.shot_id for g in grades] == SAMPLE_IDS


def test_non_json_body_is_refused() -> None:
    with pytest.raises(RuntimeError, match="not valid JSON"):
        alignment._parse_grades("sorry, I can't help with that", SAMPLE_IDS)


def test_empty_body_is_refused() -> None:
    with pytest.raises(RuntimeError, match="returned no text"):
        alignment._parse_grades("", SAMPLE_IDS)


# --- grading ------------------------------------------------------------------------------


def test_grade_index_tallies_and_never_touches_the_index_call_counter(
    graded: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hard constraint 1 is enforced by a counter; the grader must stay out of it."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    gemini.reset_call_count()
    index_path, frames = graded
    verdicts = _verdicts(verdict="mismatch")
    verdicts[0]["verdict"] = "match"
    verdicts[1]["verdict"] = "partial"
    client = _FakeClient(_response(verdicts))

    with patch.object(alignment.genai, "Client", return_value=client):
        report = grade_index(index_path, frames, prompt_version="p3")

    assert (report.match, report.partial, report.mismatch) == (1, 1, 15)
    assert report.sample_n == 17
    assert report.clean_match_rate == "1/17"
    assert report.grader_tokens == 3000
    assert gemini.generate_call_count() == 0, "grading must not count as an index call"
    assert len(client.calls) == 1, "the whole sample is graded in one request, not one per shot"


def test_one_request_carries_every_pair_interleaved(
    graded: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each frame is preceded by its own caption, so pairing cannot drift — the T011 failure."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    index_path, frames = graded
    client = _FakeClient(_response(_verdicts()))

    with patch.object(alignment.genai, "Client", return_value=client):
        grade_index(index_path, frames)

    parts = client.calls[0]["contents"].parts
    assert len(parts) == 1 + 2 * 17
    assert parts[1].text is not None and parts[1].text.startswith("shot_000 caption:")
    assert parts[2].inline_data is not None
    assert client.calls[0]["config"].temperature == 0.0


def test_calibration_against_the_human_column_is_reported(
    graded: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The grader's agreement with T009 is what makes it usable as a stand-in for the human."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    index_path, frames = graded
    sample = load_sample()
    payload = [
        {"shot_id": s.shot_id, "verdict": s.t009_verdict, "reason": "r"} for s in sample.shots
    ]
    client = _FakeClient(_response(payload))

    with patch.object(alignment.genai, "Client", return_value=client):
        report = grade_index(index_path, frames)

    assert report.agreement_with_t009 == 17


def test_missing_keyframe_is_an_error_not_a_smaller_sample(
    graded: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    index_path, frames = graded
    (frames / "shot_059.png").unlink()
    with pytest.raises(FileNotFoundError, match="keyframe missing for shot_059"):
        grade_index(index_path, frames)


def test_empty_caption_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    index_path = tmp_path / "index.json"
    index_path.write_text(_index(SAMPLE_IDS, caption="").model_dump_json(), encoding="utf-8")
    frames = tmp_path / "keyframes"
    frames.mkdir()
    for shot_id in SAMPLE_IDS:
        (frames / f"{shot_id}.png").write_bytes(_blank_png())
    with pytest.raises(ValueError, match="shot_000 has an empty caption"):
        grade_index(index_path, frames)


def test_shot_missing_from_the_index_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    index_path = tmp_path / "index.json"
    index_path.write_text(_index(SAMPLE_IDS[:-1]).model_dump_json(), encoding="utf-8")
    frames = tmp_path / "keyframes"
    frames.mkdir()
    for shot_id in SAMPLE_IDS:
        (frames / f"{shot_id}.png").write_bytes(_blank_png())
    with pytest.raises(ValueError, match="shot_116 is in the sample but not in the index"):
        grade_index(index_path, frames)


# --- reporting ----------------------------------------------------------------------------


def test_report_markdown_shows_both_columns() -> None:
    report = AgreementReport(
        index_path="work/footage_index.json",
        prompt_version="p3",
        grader_model="gemini-3.5-flash",
        grader_prompt_version="g1",
        sample_n=2,
        match=1,
        partial=0,
        mismatch=1,
        grades=[
            Grade(shot_id="shot_000", verdict="match", reason="ok"),
            Grade(shot_id="shot_059", verdict="mismatch", reason="empty boot"),
        ],
        agreement_with_t009=2,
    )
    out = report_markdown(report)
    assert "1 match / 0 partial / 1 mismatch of 2" in out
    assert "| `shot_059` | mismatch | MISMATCH | empty boot |" in out

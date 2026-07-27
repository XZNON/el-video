"""Tests for T004 — ``elvideo.index.gemini``.

The Gemini client is mocked throughout: the acceptance criteria are about the *request* we build
(one call, pinned model, ``media_resolution`` and ``fps`` actually reaching the payload, boundaries
in the prompt) and about how we treat the *response* (strict schema, loud failure on a bad
``shot_index``). All of that is checkable without spending a token.

One real-API run is marked ``slow`` at the bottom — it is the only way to confirm the settings
survive contact with the service and to produce the token/score numbers T009 needs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors as genai_errors
from google.genai import types

from elvideo.index import gemini
from elvideo.index.gemini import (
    DEFAULT_MEDIA_RESOLUTION,
    DEFAULT_SAMPLE_FPS,
    MODEL,
    PROMPT_VERSION,
    generate_call_count,
    reset_call_count,
    understand,
)
from elvideo.schema.models import Shot, ShotUnderstanding

IN_MP4 = Path(__file__).resolve().parent.parent / "in.mp4"


# --- fakes ---------------------------------------------------------------------------------


def _judgment(i: int, score: float = 0.5, **extra: Any) -> dict[str, Any]:
    return {
        "shot_index": i,
        "caption": f"caption {i}",
        "editorial_score": score,
        "moment_reason": f"reason {i}",
        "tags": ["a", "b"],
        **extra,
    }


def _response(payload: Any, *, text: str | None = None) -> SimpleNamespace:
    """A stand-in for ``GenerateContentResponse`` — only the attributes we read."""
    return SimpleNamespace(
        text=text if text is not None else json.dumps(payload),
        usage_metadata=SimpleNamespace(
            prompt_token_count=14000,
            candidates_token_count=6000,
            thoughts_token_count=500,
            total_token_count=20500,
        ),
        candidates=[SimpleNamespace(finish_reason=None)],
    )


class _FakeFile:
    def __init__(self, state: str = "ACTIVE") -> None:
        self.name = "files/abc123"
        self.uri = "https://generativelanguage.googleapis.com/v1beta/files/abc123"
        self.mime_type = "video/mp4"
        self.state = state


class _FakeClient:
    """Records what was sent, so the assertions are against the request, not the signature."""

    def __init__(
        self,
        responses: list[Any] | None = None,
        *,
        file_states: list[str] | None = None,
    ) -> None:
        self._responses = responses if responses is not None else [_response([_judgment(0)])]
        self._file_states = file_states or ["ACTIVE"]
        self.calls: list[dict[str, Any]] = []
        self.uploaded: list[str] = []
        self.deleted: list[str] = []
        self.polls = 0

        outer = self

        class _Files:
            def upload(self, *, file: str) -> _FakeFile:
                outer.uploaded.append(str(file))
                return _FakeFile(outer._file_states[0])

            def get(self, *, name: str) -> _FakeFile:
                outer.polls += 1
                state = outer._file_states[min(outer.polls, len(outer._file_states) - 1)]
                return _FakeFile(state)

            def delete(self, *, name: str) -> None:
                outer.deleted.append(name)

        class _Models:
            def generate_content(
                self, *, model: str, contents: Any, config: Any
            ) -> SimpleNamespace:
                outer.calls.append({"model": model, "contents": contents, "config": config})
                nxt = outer._responses[min(len(outer.calls) - 1, len(outer._responses) - 1)]
                if isinstance(nxt, Exception):
                    raise nxt
                return nxt

        self.files = _Files()
        self.models = _Models()


@pytest.fixture(autouse=True)
def _fast_and_keyed(monkeypatch: pytest.MonkeyPatch) -> None:
    """No real key, no real sleeping. Backoff constants are read per call, so this works."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini, "RETRY_WAIT_MULTIPLIER_S", 0.0)
    monkeypatch.setattr(gemini, "RETRY_WAIT_MAX_S", 0.0)
    monkeypatch.setattr(gemini, "UPLOAD_POLL_INTERVAL_S", 0.0)
    reset_call_count()


@pytest.fixture
def video(tmp_path: Path) -> str:
    """A file that exists — the SDK is mocked, so the bytes never matter."""
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"not really a video")
    return str(path)


def _shots(n: int) -> list[Shot]:
    return [Shot(id=f"shot_{i:03d}", t_start=i * 2.0, t_end=i * 2.0 + 2.0) for i in range(n)]


def _run(client: _FakeClient, video: str, *args: Any, **kwargs: Any) -> list[Any]:
    with patch.object(gemini.genai, "Client", return_value=client):
        return understand(video, *args, **kwargs)


# --- guards --------------------------------------------------------------------------------


def test_missing_file_raises_before_any_client_is_built(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="video not found"):
        understand(str(tmp_path / "nope.mp4"))


def test_missing_api_key_is_an_actionable_runtime_error(
    video: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # .env on this machine has a real key; loading it would defeat the test.
    monkeypatch.setattr(gemini, "load_dotenv", lambda *a, **k: False)
    with pytest.raises(RuntimeError, match=r"GEMINI_API_KEY is not set.*aistudio"):
        understand(video)


def test_blank_api_key_is_treated_as_unset(video: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    monkeypatch.setattr(gemini, "load_dotenv", lambda *a, **k: False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not set"):
        understand(video)


@pytest.mark.parametrize("bad_fps", [0.0, -1.0])
def test_non_positive_fps_rejected(video: str, bad_fps: float) -> None:
    with pytest.raises(ValueError, match="fps must be > 0"):
        understand(video, bad_fps)


def test_unknown_media_resolution_rejected(video: str) -> None:
    with pytest.raises(ValueError, match="unknown media_resolution"):
        understand(video, 0.5, "ultra")  # type: ignore[arg-type]


def test_empty_shot_list_is_rejected_rather_than_silently_free_segmenting(video: str) -> None:
    client = _FakeClient()
    with pytest.raises(ValueError, match="pass None"):
        _run(client, video, shots=[])


# --- the one rule: exactly one call ---------------------------------------------------------


def test_exactly_one_call_regardless_of_shot_count(video: str) -> None:
    """117 shots, one request. The whole free-tier design rests on this."""
    shots = _shots(117)
    client = _FakeClient([_response([_judgment(i) for i in range(117)])])
    out = _run(client, video, shots=shots)

    assert len(client.calls) == 1
    assert generate_call_count() == 1
    assert len(out) == 117


def test_call_counter_accumulates_across_invocations_and_resets(video: str) -> None:
    client = _FakeClient([_response([_judgment(0)])])
    _run(client, video, shots=_shots(1))
    _run(client, video, shots=_shots(1))
    assert generate_call_count() == 2
    reset_call_count()
    assert generate_call_count() == 0


# --- the request payload --------------------------------------------------------------------


def test_model_string_is_pinned(video: str) -> None:
    client = _FakeClient()
    _run(client, video, shots=_shots(1))
    assert client.calls[0]["model"] == "gemini-3.5-flash" == MODEL


def test_media_resolution_low_reaches_the_request_by_default(video: str) -> None:
    client = _FakeClient()
    _run(client, video, shots=_shots(1))
    config = client.calls[0]["config"]
    assert config.media_resolution == types.MediaResolution.MEDIA_RESOLUTION_LOW


def test_media_resolution_override_reaches_the_request(video: str) -> None:
    client = _FakeClient()
    _run(client, video, 0.5, "medium", shots=_shots(1))
    config = client.calls[0]["config"]
    assert config.media_resolution == types.MediaResolution.MEDIA_RESOLUTION_MEDIUM


def test_fps_defaults_to_half_and_reaches_video_metadata(video: str) -> None:
    client = _FakeClient()
    _run(client, video, shots=_shots(1))
    parts = client.calls[0]["contents"].parts
    assert parts[0].video_metadata is not None
    assert parts[0].video_metadata.fps == DEFAULT_SAMPLE_FPS == 0.5


def test_fps_is_overridable_per_call(video: str) -> None:
    """A per-video knob: the override reaches the payload, the default is untouched."""
    client = _FakeClient()
    _run(client, video, 2.0, shots=_shots(1))
    assert client.calls[0]["contents"].parts[0].video_metadata.fps == 2.0
    assert gemini.DEFAULT_SAMPLE_FPS == 0.5


def test_uploaded_file_is_referenced_not_inlined(video: str) -> None:
    client = _FakeClient()
    _run(client, video, shots=_shots(1))
    part = client.calls[0]["contents"].parts[0]
    assert part.file_data is not None
    assert part.file_data.file_uri.endswith("files/abc123")
    assert client.uploaded == [video]


def test_structured_output_is_enforced_with_a_response_schema(video: str) -> None:
    """Strict JSON via schema — no prose, no markdown fences to strip."""
    client = _FakeClient()
    _run(client, video, shots=_shots(1))
    config = client.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is not None


def test_system_instruction_carries_the_scoring_rubric(video: str) -> None:
    client = _FakeClient()
    _run(client, video, shots=_shots(1))
    instruction = client.calls[0]["config"].system_instruction
    assert "editorial_score" in instruction
    assert "moment_reason" in instruction
    assert "EVIDENCE" in instruction


# --- D-010: boundaries in the prompt text ---------------------------------------------------


def test_shot_boundaries_go_into_the_prompt_as_a_numbered_list(video: str) -> None:
    client = _FakeClient([_response([_judgment(i) for i in range(3)])])
    _run(client, video, shots=_shots(3))
    prompt = client.calls[0]["contents"].parts[1].text

    assert "0 0.00-2.00" in prompt
    assert "1 2.00-4.00" in prompt
    assert "2 4.00-6.00" in prompt
    assert "3 shots" in prompt
    assert "Do not merge" in prompt


def test_free_segmentation_path_still_works_and_keeps_hints(video: str) -> None:
    """``shots=None`` is the fallback and the thing that makes the Path A seam real."""
    payload = [_judgment(0, t_start_hint=0.0, t_end_hint=3.0)]
    client = _FakeClient([_response(payload)])
    out = _run(client, video)

    prompt = client.calls[0]["contents"].parts[1].text
    assert "Segment this video into shots yourself" in prompt
    assert out[0].t_start_hint == 0.0
    assert out[0].t_end_hint == 3.0


def test_hints_are_requested_on_both_paths(video: str) -> None:
    """Since ``p3``, hints are asked for even when we supplied the boundaries (T011).

    ``p2`` skipped them on the shot-list path, reasoning that echoing 117 pairs of numbers we
    already know is output tokens for nothing. D-027 is what that reasoning cost: the model filed
    accurate captions under the wrong indices, and because it never said where it had looked,
    **nothing in the pipeline could tell**. The hint is not a number we already know — it is the
    model's own account of where it looked, and it is the only evidence that distinguishes a bad
    caption from a misfiled one.
    """
    client = _FakeClient()
    _run(client, video, shots=_shots(1))
    with_shots = client.calls[0]["config"].response_schema

    client2 = _FakeClient()
    _run(client2, video)
    without_shots = client2.calls[0]["config"].response_schema

    assert "t_start_hint" in gemini._JudgmentWithHints.model_fields
    assert with_shots == list[gemini._JudgmentWithHints]
    assert without_shots == list[gemini._JudgmentWithHints]


# --- hint alignment (T011) --------------------------------------------------------------------


def _hinted(i: int, start: float, end: float) -> ShotUnderstanding:
    return ShotUnderstanding(
        shot_index=i,
        caption=f"caption {i}",
        editorial_score=0.5,
        moment_reason=f"reason {i}",
        tags=["a"],
        t_start_hint=start,
        t_end_hint=end,
    )


def test_hint_drift_is_empty_when_every_judgment_lands_in_its_own_shot() -> None:
    shots = _shots(3)
    hinted = [_hinted(i, s.t_start, s.t_end) for i, s in enumerate(shots)]
    assert gemini.hint_drift(hinted, shots) == []


def test_hint_drift_names_the_judgment_that_describes_another_shot() -> None:
    """The D-027 signature: an accurate caption filed against footage it does not describe."""
    shots = _shots(20)
    hinted = [_hinted(i, s.t_start, s.t_end) for i, s in enumerate(shots)]
    # shot_005's judgment describes what happens at shot_017 - the -15 displacement D-027 measured.
    hinted[5] = _hinted(5, shots[17].t_start, shots[17].t_end)
    assert gemini.hint_drift(hinted, shots) == [5]


def test_second_granular_rounding_is_not_counted_as_drift() -> None:
    """Gemini's timestamps are second-granular (hard constraint 4); tolerance keeps that out."""
    shots = _shots(3)
    hinted = [_hinted(i, s.t_start - 0.9, s.t_end - 0.9) for i, s in enumerate(shots) if i]
    assert gemini.hint_drift(hinted, shots) == []


def test_judgments_without_hints_are_skipped_not_counted_as_aligned() -> None:
    """A model returning no hints is unmeasured, not verified. The caller logs the denominator."""
    shots = _shots(2)
    plain = ShotUnderstanding(
        shot_index=0, caption="c", editorial_score=0.5, moment_reason="r", tags=["a"]
    )
    assert gemini.hint_drift([plain], shots) == []


def test_drift_above_the_threshold_warns(caplog: pytest.LogCaptureFixture) -> None:
    shots = _shots(4)
    hinted = [_hinted(i, shots[3].t_start, shots[3].t_end) for i in range(4)]
    with caplog.at_level(logging.WARNING):
        gemini._check_hints(hinted, shots)
    assert "describe a moment outside their own shot" in caplog.text


# --- response handling ----------------------------------------------------------------------


def test_judgment_fields_survive_the_round_trip(video: str) -> None:
    payload = [
        {
            "shot_index": 0,
            "caption": "chef plating a dosa, steam rising",
            "editorial_score": 0.86,
            "moment_reason": "hero framing, action peak",
            "tags": ["food", "indoor"],
        }
    ]
    client = _FakeClient([_response(payload)])
    out = _run(client, video, shots=_shots(1))

    assert out[0].caption == "chef plating a dosa, steam rising"
    assert out[0].editorial_score == 0.86
    assert out[0].moment_reason == "hero framing, action peak"
    assert out[0].tags == ["food", "indoor"]


def test_output_is_sorted_by_shot_index(video: str) -> None:
    payload = [_judgment(2), _judgment(0), _judgment(1)]
    client = _FakeClient([_response(payload)])
    out = _run(client, video, shots=_shots(3))
    assert [u.shot_index for u in out] == [0, 1, 2]


def test_unknown_response_fields_are_dropped_not_fatal(video: str) -> None:
    """``ShotUnderstanding`` forbids extras — that is our constraint, not the model's."""
    payload = [_judgment(0, mood="warm")]
    client = _FakeClient([_response(payload)])
    out = _run(client, video, shots=_shots(1))
    assert out[0].shot_index == 0


def test_out_of_range_shot_index_fails_loudly(video: str) -> None:
    """The silent-failure surface D-010 exists to close: captions on the wrong shots."""
    payload = [_judgment(0), _judgment(7)]
    client = _FakeClient([_response(payload)])
    with pytest.raises(RuntimeError, match=r"shot_index \[7\].*only 3 shots"):
        _run(client, video, shots=_shots(3))


def test_duplicate_shot_index_fails_loudly(video: str) -> None:
    payload = [_judgment(0), _judgment(1), _judgment(1)]
    client = _FakeClient([_response(payload)])
    with pytest.raises(RuntimeError, match=r"duplicate shot_index values \[1\]"):
        _run(client, video, shots=_shots(3))


def test_missing_shots_warn_but_do_not_fail(video: str, caplog: pytest.LogCaptureFixture) -> None:
    """Recoverable and visible: T007 leaves those shots captionless."""
    client = _FakeClient([_response([_judgment(0)])])
    with caplog.at_level(logging.WARNING, logger="elvideo.index.gemini"):
        out = _run(client, video, shots=_shots(3))
    assert len(out) == 1
    assert "judged 1 of 3 shots" in caplog.text


def test_unparseable_json_raises_runtime_error(video: str) -> None:
    client = _FakeClient([_response(None, text="```json\nnot really\n```")])
    with pytest.raises(RuntimeError, match="not valid JSON"):
        _run(client, video, shots=_shots(1))


def test_json_object_instead_of_array_raises(video: str) -> None:
    client = _FakeClient([_response({"shots": []})])
    with pytest.raises(RuntimeError, match="expected a JSON array"):
        _run(client, video, shots=_shots(1))


def test_empty_response_text_raises_with_finish_reason(video: str) -> None:
    response = _response(None, text="")
    response.candidates = [SimpleNamespace(finish_reason=SimpleNamespace(name="MAX_TOKENS"))]
    client = _FakeClient([response])
    with pytest.raises(RuntimeError, match="MAX_TOKENS"):
        _run(client, video, shots=_shots(1))


def test_empty_array_raises_rather_than_returning_nothing(video: str) -> None:
    client = _FakeClient([_response([])])
    with pytest.raises(RuntimeError, match="empty shot list"):
        _run(client, video, shots=_shots(1))


def test_score_outside_zero_to_one_is_rejected(video: str) -> None:
    client = _FakeClient([_response([_judgment(0, editorial_score=1.4)])])
    with pytest.raises(RuntimeError, match="does not match ShotUnderstanding"):
        _run(client, video, shots=_shots(1))


# --- backoff --------------------------------------------------------------------------------


def _rate_limited() -> genai_errors.ClientError:
    return genai_errors.ClientError(
        429, {"error": {"message": "quota exceeded", "status": "RESOURCE_EXHAUSTED"}}
    )


def test_429_is_retried_then_succeeds(video: str) -> None:
    """One request, two transport attempts. T013: the counters report those separately.

    This is the case that broke T012's first live run — before T013 the request counter read 2
    here, and ``build.py``'s ``!= 1`` assertion discarded a run whose understanding had already
    succeeded.
    """
    client = _FakeClient([_rate_limited(), _response([_judgment(0)])])
    out = _run(client, video, shots=_shots(1))
    assert len(out) == 1
    assert len(client.calls) == 2
    assert generate_call_count() == 1  # one request...
    assert gemini.generate_attempt_count() == 2  # ...that took two goes. Visible, not hidden.


def test_retry_is_logged_at_warning_because_it_costs_a_daily_request(
    video: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A retry is free of correctness consequences and expensive against the quota (D-031)."""
    client = _FakeClient([_rate_limited(), _response([_judgment(0)])])
    with caplog.at_level(logging.WARNING, logger="elvideo.index.gemini"):
        _run(client, video, shots=_shots(1))

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("transport attempt 2" in r.getMessage() for r in warnings)


def test_attempts_are_counted_per_request_not_cumulatively(video: str) -> None:
    """A second request whose first attempt succeeds must not be mislabelled a retry."""
    client = _FakeClient([_rate_limited(), _response([_judgment(0)])])
    _run(client, video, shots=_shots(1))
    _run(client, video, shots=_shots(1))

    assert generate_call_count() == 2
    assert gemini.generate_attempt_count() == 3  # 2 for the first request, 1 for the second


def test_reset_zeroes_both_counters(video: str) -> None:
    client = _FakeClient([_rate_limited(), _response([_judgment(0)])])
    _run(client, video, shots=_shots(1))
    reset_call_count()

    assert generate_call_count() == 0
    assert gemini.generate_attempt_count() == 0


def test_persistent_429_surfaces_a_clear_error_not_an_empty_list(video: str) -> None:
    client = _FakeClient([_rate_limited()])
    with pytest.raises(RuntimeError, match=r"HTTP 429 on all \d+ attempts.*10 RPM"):
        _run(client, video, shots=_shots(1))
    assert len(client.calls) == gemini.RETRY_MAX_ATTEMPTS


def test_429_on_the_upload_is_retried_too(video: str) -> None:
    """Observed for real: a depleted key trips at the File API upload, before generate_content."""
    client = _FakeClient()
    client.files.upload = MagicMock(  # type: ignore[method-assign]
        side_effect=[_rate_limited(), _FakeFile("ACTIVE")]
    )
    out = _run(client, video, shots=_shots(1))
    assert len(out) == 1
    assert client.files.upload.call_count == 2


def test_persistent_429_on_the_upload_is_actionable(video: str) -> None:
    client = _FakeClient()
    client.files.upload = MagicMock(side_effect=_rate_limited())  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match=r"File API upload.*depleted credits"):
        _run(client, video, shots=_shots(1))
    assert client.calls == []
    assert generate_call_count() == 0


def test_non_429_errors_are_not_retried(video: str) -> None:
    """A 400 is a bug in our request; retrying it four more times just burns the window."""
    client = _FakeClient([genai_errors.ClientError(400, {"error": {"message": "bad request"}})])
    with pytest.raises(genai_errors.ClientError):
        _run(client, video, shots=_shots(1))
    assert len(client.calls) == 1


# --- File API lifecycle ---------------------------------------------------------------------


def test_upload_is_deleted_after_a_successful_call(video: str) -> None:
    client = _FakeClient()
    _run(client, video, shots=_shots(1))
    assert client.deleted == ["files/abc123"]


def test_upload_is_deleted_even_when_the_call_fails(video: str) -> None:
    """Otherwise a debug loop leaks one upload per run."""
    client = _FakeClient([_rate_limited()])
    with pytest.raises(RuntimeError):
        _run(client, video, shots=_shots(1))
    assert client.deleted == ["files/abc123"]


def test_processing_upload_is_polled_until_active(video: str) -> None:
    client = _FakeClient(file_states=["PROCESSING", "PROCESSING", "ACTIVE"])
    _run(client, video, shots=_shots(1))
    assert client.polls == 2
    assert len(client.calls) == 1


def test_failed_upload_raises_before_any_generate_call(video: str) -> None:
    client = _FakeClient(file_states=["FAILED"])
    with pytest.raises(RuntimeError, match="not ACTIVE"):
        _run(client, video, shots=_shots(1))
    assert client.calls == []


def test_upload_that_never_finishes_processing_times_out(
    video: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gemini, "UPLOAD_TIMEOUT_S", 0.0)
    client = _FakeClient(file_states=["PROCESSING"])
    with pytest.raises(RuntimeError, match="still PROCESSING"):
        _run(client, video, shots=_shots(1))


def test_delete_failure_is_warned_not_raised(video: str, caplog: pytest.LogCaptureFixture) -> None:
    client = _FakeClient()
    client.files.delete = MagicMock(side_effect=RuntimeError("gone"))  # type: ignore[method-assign]
    with caplog.at_level(logging.WARNING, logger="elvideo.index.gemini"):
        out = _run(client, video, shots=_shots(1))
    assert len(out) == 1
    assert "could not delete gemini upload" in caplog.text


# --- observability --------------------------------------------------------------------------


def test_token_usage_is_logged(video: str, caplog: pytest.LogCaptureFixture) -> None:
    """T009 checks the ~30K target against this line, not against an estimate."""
    client = _FakeClient()
    with caplog.at_level(logging.INFO, logger="elvideo.index.gemini"):
        _run(client, video, shots=_shots(1))
    assert "gemini tokens: prompt=14000 output=6000" in caplog.text
    assert "total=20500" in caplog.text


def test_call_is_logged_with_settings_and_prompt_version(
    video: str, caplog: pytest.LogCaptureFixture
) -> None:
    client = _FakeClient()
    with caplog.at_level(logging.INFO, logger="elvideo.index.gemini"):
        _run(client, video, shots=_shots(1))
    assert "gemini generate_content request #1" in caplog.text
    assert f"model={MODEL}" in caplog.text
    assert "media_resolution=low" in caplog.text
    assert f"prompt={PROMPT_VERSION}" in caplog.text


def test_flat_scores_are_flagged_as_a_prompt_bug(
    video: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A model that scores everything 0.8 must not look like a clean run."""
    payload = [_judgment(i, score=0.8) for i in range(5)]
    client = _FakeClient([_response(payload)])
    with caplog.at_level(logging.WARNING, logger="elvideo.index.gemini"):
        _run(client, video, shots=_shots(5))
    assert "barely varies" in caplog.text


def test_spread_scores_do_not_warn(video: str, caplog: pytest.LogCaptureFixture) -> None:
    payload = [_judgment(i, score=s) for i, s in enumerate([0.12, 0.44, 0.61, 0.83, 0.95])]
    client = _FakeClient([_response(payload)])
    with caplog.at_level(logging.INFO, logger="elvideo.index.gemini"):
        _run(client, video, shots=_shots(5))
    assert "barely varies" not in caplog.text
    assert "distinct@2dp=5/5" in caplog.text


def test_settings_are_recorded(video: str) -> None:
    """The reproducibility record: these are the numbers the A/B writeup quotes (D-002)."""
    assert MODEL == "gemini-3.5-flash"
    assert DEFAULT_SAMPLE_FPS == 0.5
    assert DEFAULT_MEDIA_RESOLUTION == "low"
    assert gemini.TEMPERATURE == 0.4
    assert gemini.SEED == 7
    assert gemini.THINKING_LEVEL == types.ThinkingLevel.LOW
    assert gemini.RETRY_MAX_ATTEMPTS == 5
    assert PROMPT_VERSION == "p3"


# --- real API, one call ----------------------------------------------------------------------


@pytest.mark.slow
def test_real_video_one_call_spread_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    """One real free-tier call on the A/B clip (D-003).

    Everything above proves the request we build; this proves the service accepts it and that the
    prompt produces judgment rather than 117 copies of 0.8. Costs ~20K tokens of a free key.
    """
    import os

    from dotenv import load_dotenv

    from elvideo.index.scenes import detect_shots

    # The autouse fixture above plants a fake key, and load_dotenv() does not override a set
    # variable — so the real key has to be pulled in deliberately.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    load_dotenv()
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        pytest.skip("no GEMINI_API_KEY")
    if not IN_MP4.is_file():
        pytest.skip("in.mp4 not present")

    shots = detect_shots(str(IN_MP4))
    reset_call_count()
    out = understand(str(IN_MP4), shots=shots)

    assert generate_call_count() == 1, "one Gemini call per video, never per shot"
    assert len(out) > 0
    assert all(0.0 <= u.editorial_score <= 1.0 for u in out)
    assert all(u.shot_index < len(shots) for u in out)
    assert all(u.caption.strip() for u in out)
    assert all(u.moment_reason.strip() for u in out)

    scores = [u.editorial_score for u in out]
    distinct = len({round(s, 2) for s in scores})
    on_grid = sum(1 for s in scores if round(s * 100) % 5 == 0)

    # Thresholds set from the measured p1 → p2 iteration (D-024), so a regression to p1's
    # behaviour fails here rather than passing quietly: p1 scored 11 distinct values, every one
    # of them on the 0.05 grid, and never used the hero band. p2 scored 37, 32/117 on the grid,
    # and reached 0.85.
    #
    # Range lowered 0.3 -> 0.2 in T011 session 009, on six measured p3 runs rather than on two:
    # 0.27 / 0.48 / 0.27 at fps=0.5 and 0.32 / 0.65 / 0.25 at fps=1.0. At 0.3 this assertion fails
    # 4 of those 6 — it was a coin-flip, not a guard. **And it never caught what it was written
    # for:** p1's range was 0.65 (0.10-0.75, D-024), comfortably over 0.3, so clustering has always
    # been detected by the granularity assertions below, not by this one. 0.2 sits under the
    # measured floor of 0.25 with margin and still fails a genuinely collapsed distribution.
    # Whether the model calls the outro frames unusable is what moves min-score, and `seed` is
    # best-effort (D-019). See D-030.
    assert max(scores) - min(scores) > 0.2, f"scores did not spread: {sorted(set(scores))}"
    assert distinct >= 15, f"scores cluster — prompt bug ({distinct} distinct values at 2dp)"
    assert on_grid < 0.9 * len(scores), (
        f"{on_grid}/{len(scores)} scores land on the 0.05 grid — the model is picking from a "
        f"handful of round numbers instead of judging"
    )

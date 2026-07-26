"""Tests for T003 — ``elvideo.index.transcribe``.

``words_in_range`` is pure and gets the boundary coverage the task calls for with no audio
fixture at all. ``transcribe`` is tested for its guard paths (missing file, no audio track) and
for the WhisperX-output conversion, with WhisperX mocked — a real transcription pass is a
minutes-long integration run, not a unit test.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from elvideo.index.transcribe import (
    DEFAULT_COMPUTE_TYPE,
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL_SIZE,
    transcribe,
    words_in_range,
)
from elvideo.schema.models import Word

IN_MP4 = Path(__file__).resolve().parent.parent / "in.mp4"


def _words(*times: float) -> list[Word]:
    return [Word(t=t, d=0.2, w=f"w{i}") for i, t in enumerate(times)]


# --- words_in_range: half-open [t_start, t_end) -------------------------------------------


def test_boundary_word_at_t_start_is_included() -> None:
    words = _words(1.0, 1.5)
    assert [w.t for w in words_in_range(words, 1.0, 2.0)] == [1.0, 1.5]


def test_boundary_word_at_t_end_is_excluded() -> None:
    """Half-open on the right: a word landing exactly on the cut belongs to the next shot."""
    words = _words(1.0, 2.0)
    assert [w.t for w in words_in_range(words, 1.0, 2.0)] == [1.0]


def test_cut_boundary_word_lands_in_exactly_one_shot() -> None:
    """The reason for half-open: never both shots, never neither."""
    words = _words(0.5, 2.0, 3.5)
    first = words_in_range(words, 0.0, 2.0)
    second = words_in_range(words, 2.0, 4.0)
    assert len(first) + len(second) == 3
    assert not {id(w) for w in first} & {id(w) for w in second}


def test_silent_range_returns_empty_and_joins_to_empty_string() -> None:
    """A silent shot's transcript is "" — the schema requires a string, not None."""
    words = _words(0.5, 10.0)
    picked = words_in_range(words, 3.0, 5.0)
    assert picked == []
    assert " ".join(w.w for w in picked) == ""


def test_empty_word_list_returns_empty() -> None:
    assert words_in_range([], 0.0, 10.0) == []


def test_zero_width_range_returns_empty() -> None:
    """t_start == t_end can select nothing, by definition of half-open."""
    assert words_in_range(_words(1.0), 1.0, 1.0) == []


def test_order_is_preserved() -> None:
    words = _words(0.1, 0.4, 0.9, 1.4)
    assert [w.t for w in words_in_range(words, 0.0, 1.0)] == [0.1, 0.4, 0.9]


# --- transcribe: guard paths and settings --------------------------------------------------


def test_missing_file_raises_with_path(tmp_path: Any) -> None:
    missing = str(tmp_path / "nope.mp4")
    with pytest.raises(FileNotFoundError, match="nope.mp4"):
        transcribe(missing)


def test_transcribe_settings_are_recorded() -> None:
    """D-002: the settings Path A must match are explicit module constants."""
    assert DEFAULT_MODEL_SIZE == "base"
    assert DEFAULT_COMPUTE_TYPE == "int8"
    assert DEFAULT_LANGUAGE == "en"


def test_no_audio_track_returns_empty_list(tmp_path: Any) -> None:
    """A silent video yields [] rather than raising — WhisperX is never even loaded."""
    video = tmp_path / "silent.mp4"
    video.write_bytes(b"\x00")
    empty = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch("elvideo.index.transcribe.subprocess.run", return_value=empty):
        assert transcribe(str(video)) == []


def test_real_video_without_audio_track_returns_empty_list(tmp_path: Any) -> None:
    """Same criterion against a real container ffprobe actually inspects, not a mock."""
    clip = tmp_path / "noaudio.mp4"
    proc = subprocess.run(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x64:d=1:r=10",
            "-pix_fmt",
            "yuv420p",
            str(clip),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"ffmpeg unavailable or failed: {proc.stderr[-200:]}")

    assert transcribe(str(clip)) == []


def test_missing_ffprobe_raises_actionable_error(tmp_path: Any) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"\x00")
    with (
        patch("elvideo.index.transcribe.subprocess.run", side_effect=FileNotFoundError),
        pytest.raises(FileNotFoundError, match="ffprobe not on PATH"),
    ):
        transcribe(str(video))


def _fake_whisperx(word_segments: list[dict[str, Any]]) -> MagicMock:
    fake = MagicMock()
    fake.load_audio.return_value = object()
    fake.load_model.return_value = SimpleNamespace(
        transcribe=lambda *a, **k: {"segments": [], "language": "en"}
    )
    fake.load_align_model.return_value = (object(), {})
    fake.align.return_value = {"word_segments": word_segments}
    return fake


def _run_with_fake_whisperx(tmp_path: Any, word_segments: list[dict[str, Any]]) -> list[Word]:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"\x00")
    audio = subprocess.CompletedProcess(args=[], returncode=0, stdout="audio\n", stderr="")
    fake = _fake_whisperx(word_segments)
    with (
        patch("elvideo.index.transcribe.subprocess.run", return_value=audio),
        patch("elvideo.index.transcribe.pick_device", return_value="cpu"),
        patch.dict(sys.modules, {"whisperx": fake}),
    ):
        return transcribe(str(video))


def test_words_are_per_word_and_chronological(tmp_path: Any) -> None:
    """Per-word t/d, not segment spans — and sorted even if WhisperX emits out of order."""
    words = _run_with_fake_whisperx(
        tmp_path,
        [
            {"word": "world", "start": 0.62, "end": 0.98},
            {"word": "hello", "start": 0.20, "end": 0.55},
        ],
    )
    assert [(w.w, w.t, round(w.d, 2)) for w in words] == [
        ("hello", 0.20, 0.35),
        ("world", 0.62, 0.36),
    ]


def test_unalignable_words_without_timing_are_dropped(tmp_path: Any) -> None:
    """WhisperX omits start/end for characters outside the wav2vec2 dictionary."""
    words = _run_with_fake_whisperx(
        tmp_path,
        [
            {"word": "2026", "score": 0.1},
            {"word": "ok", "start": 1.0, "end": 1.2},
            {"word": "  ", "start": 2.0, "end": 2.1},
        ],
    )
    assert [w.w for w in words] == ["ok"]


def test_negative_duration_is_clamped(tmp_path: Any) -> None:
    """Word.d is ge=0 in the schema; a degenerate end < start must not raise ValidationError."""
    words = _run_with_fake_whisperx(tmp_path, [{"word": "x", "start": 5.0, "end": 4.9}])
    assert words[0].d == 0.0


@pytest.mark.skipif(not IN_MP4.is_file(), reason="A/B test video not present (D-003, gitignored)")
@pytest.mark.slow
def test_real_video_word_level_timing() -> None:
    """Integration: the real clip has audio, so words[] must be populated and well-formed.

    Slow (minutes on CPU) — deselect with ``-m "not slow"``.
    """
    words = transcribe(str(IN_MP4))

    assert words, "the A/B clip has an audio track; words[] must not be empty"
    assert all(a.t <= b.t for a, b in zip(words, words[1:], strict=False))
    # Word-level, not segment-level: a segment would run for seconds.
    assert max(w.d for w in words) < 5.0
    # Covers the track, not just the opening (clip is 428s).
    assert words[-1].t > 300.0

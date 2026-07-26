"""Tests for T002 — ``elvideo.index.scenes``.

Two layers:

* Mocked PySceneDetect — invariant checks with no video needed (id format, ordering).
* Integration on real footage — the gitignored ``in.mp4`` A/B clip when present (D-003), and a
  tiny ffmpeg-generated single-colour clip for the no-cuts degenerate case.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from elvideo.index.scenes import DEFAULT_DETECTOR, DEFAULT_THRESHOLD, detect_shots

IN_MP4 = Path(__file__).resolve().parent.parent / "in.mp4"


def test_missing_file_raises_with_path(tmp_path: Any) -> None:
    missing = str(tmp_path / "nope.mp4")
    with pytest.raises(FileNotFoundError, match="nope.mp4"):
        detect_shots(missing)


def test_detector_settings_are_recorded() -> None:
    """D-002/D-012: the settings Path A must match are explicit module constants."""
    assert DEFAULT_DETECTOR == "ContentDetector"
    assert DEFAULT_THRESHOLD == 27.0


def _timecode(seconds: float) -> MagicMock:
    tc = MagicMock()
    tc.seconds = seconds
    return tc


def test_ids_zero_padded_and_unique_past_100(tmp_path: Any) -> None:
    """A 100+ shot video must still validate against ``^shot_[0-9]{3,}$``."""
    video = tmp_path / "in.mp4"
    video.write_bytes(b"\x00")
    scenes = [(_timecode(i * 0.5), _timecode((i + 1) * 0.5)) for i in range(120)]
    manager = MagicMock()
    manager.get_scene_list.return_value = scenes
    with (
        patch("elvideo.index.scenes.open_video"),
        patch("elvideo.index.scenes.SceneManager", return_value=manager),
    ):
        shots = detect_shots(str(video))
    assert len(shots) == 120
    assert shots[0].id == "shot_000"
    assert shots[99].id == "shot_099"
    assert shots[100].id == "shot_100"
    assert len({s.id for s in shots}) == 120


@pytest.mark.skipif(not IN_MP4.is_file(), reason="A/B test video not present (D-003, gitignored)")
def test_real_video_invariants() -> None:
    shots = detect_shots(str(IN_MP4))

    # D-012: 117 shots at threshold 27.0 on this clip.
    assert len(shots) == 117

    # Ascending order, gapless, non-overlapping.
    assert shots[0].t_start == 0.0
    for a, b in zip(shots, shots[1:], strict=False):
        assert a.t_end == b.t_start
        assert a.t_start < a.t_end

    # Final t_end matches the video stream duration within one frame (25 fps -> 0.04s).
    assert shots[-1].t_end == pytest.approx(428.04, abs=1 / 25)

    # Frame-accurate: every boundary sits on a frame at 25 fps.
    for s in shots:
        assert (s.t_start * 25) == pytest.approx(round(s.t_start * 25), abs=1e-6)


def test_single_shot_video_returns_one_shot(tmp_path: Any) -> None:
    """No cuts -> exactly one shot spanning the whole duration, not an empty list."""
    clip = tmp_path / "flat.mp4"
    proc = subprocess.run(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x64:d=2:r=10",
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

    shots = detect_shots(str(clip))
    assert len(shots) == 1
    assert shots[0].id == "shot_000"
    assert shots[0].t_start == 0.0
    assert shots[0].t_end == pytest.approx(2.0, abs=0.1)

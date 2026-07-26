"""Unit tests for T001 — ``elvideo.index.probe``.

Subprocess is mocked; no fixture video needed (per the T001 acceptance criteria).
"""

from __future__ import annotations

import json
import subprocess
from typing import Any
from unittest.mock import patch

import pytest

from elvideo.index.probe import probe

_FFPROBE_JSON = json.dumps(
    {
        "streams": [{"width": 1080, "height": 1920, "r_frame_rate": "30000/1001"}],
        "format": {"duration": "428.110000"},
    }
)


def _completed(stdout: str = _FFPROBE_JSON, returncode: int = 0, stderr: str = "") -> Any:
    return subprocess.CompletedProcess(
        args=["ffprobe"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_missing_file_raises_with_path(tmp_path: Any) -> None:
    missing = str(tmp_path / "nope.mp4")
    with pytest.raises(FileNotFoundError, match="nope.mp4"):
        probe(missing)


def test_num_den_fps_parse_and_fields(tmp_path: Any) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"\x00")
    with patch("elvideo.index.probe.subprocess.run", return_value=_completed()):
        meta = probe(str(video))
    assert meta.fps == pytest.approx(29.97, abs=0.001)
    assert meta.duration_s == pytest.approx(428.11)
    # Vertical video: no silent transposition.
    assert (meta.w, meta.h) == (1080, 1920)
    assert meta.path == str(video)


def test_ffprobe_missing_binary_actionable_message(tmp_path: Any) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"\x00")
    with (
        patch("elvideo.index.probe.subprocess.run", side_effect=FileNotFoundError),
        pytest.raises(FileNotFoundError, match="ffprobe not on PATH"),
    ):
        probe(str(video))


def test_ffprobe_nonzero_exit_raises_valueerror_with_stderr(tmp_path: Any) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"\x00")
    bad = _completed(stdout="", returncode=1, stderr="moov atom not found")
    with (
        patch("elvideo.index.probe.subprocess.run", return_value=bad),
        pytest.raises(ValueError, match="moov atom not found"),
    ):
        probe(str(video))


def test_unparseable_output_raises_valueerror(tmp_path: Any) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"\x00")
    with (
        patch("elvideo.index.probe.subprocess.run", return_value=_completed(stdout="not json")),
        pytest.raises(ValueError, match="could not parse"),
    ):
        probe(str(video))

"""Tests for T005 — ``elvideo.index.quality``.

Two layers:

* Synthetic frames — no video needed. Sharp vs blurred, blown vs crushed, the ``ValueError``
  paths, and determinism.
* Integration on the real gitignored ``in.mp4`` A/B clip when present (D-003), for
  :func:`score_shot`'s seek + keyframe behaviour.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from elvideo.index.quality import (
    CLIP_HIGH,
    CLIP_LOW,
    CLIP_SATURATION,
    EXPOSURE_TARGET,
    ROUND_DIGITS,
    SAMPLE_POSITION,
    SHARPNESS_SATURATION,
    W_EXPOSURE,
    W_SHARPNESS,
    score_frame,
    score_shot,
)

IN_MP4 = Path(__file__).resolve().parent.parent / "in.mp4"


def _sharp_frame(size: int = 240) -> np.ndarray:
    """A mid-exposed frame full of hard edges — a deterministic checkerboard plus noise-free bars.

    Built arithmetically rather than loaded from a fixture file so the pair below differs only by
    the blur, and so the test carries no binary.
    """
    frame = np.full((size, size, 3), 128, dtype=np.uint8)
    block = 8
    ys, xs = np.mgrid[0:size, 0:size]
    checker = ((ys // block + xs // block) % 2).astype(bool)
    frame[checker] = 60
    frame[~checker] = 190
    return frame


def test_constants_are_recorded() -> None:
    """D-002/D-017: the formula Path A must match is explicit module constants, not inline magic."""
    assert SHARPNESS_SATURATION == 1000.0
    assert W_SHARPNESS == 0.7
    assert W_EXPOSURE == 0.3
    assert pytest.approx(1.0) == W_SHARPNESS + W_EXPOSURE
    assert EXPOSURE_TARGET == 0.5
    assert CLIP_LOW == 8
    assert CLIP_HIGH == 247
    assert CLIP_SATURATION == 0.5
    assert SAMPLE_POSITION == 0.5
    assert ROUND_DIGITS == 4


def test_score_in_unit_range_and_is_a_float() -> None:
    score = score_frame(_sharp_frame())
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_blur_scores_lower_than_sharp() -> None:
    """The headline criterion, asserted against a fixture pair rather than eyeballed."""
    sharp = _sharp_frame()
    blurred = cv2.GaussianBlur(sharp, (15, 15), 0)
    assert score_frame(blurred) < score_frame(sharp)
    # Not a hairline difference: blur is the failure this field exists to catch.
    assert score_frame(sharp) - score_frame(blurred) > 0.1


def test_deterministic_across_repeated_calls() -> None:
    frame = _sharp_frame()
    first = score_frame(frame)
    assert all(score_frame(frame) == first for _ in range(5))
    # Same pixels through a different array object -> same number.
    assert score_frame(frame.copy()) == first


def test_blown_out_frame_scores_low() -> None:
    white = np.full((120, 160, 3), 255, dtype=np.uint8)
    score = score_frame(white)
    assert not np.isnan(score)
    assert score == 0.0


def test_crushed_frame_scores_low() -> None:
    black = np.zeros((120, 160, 3), dtype=np.uint8)
    score = score_frame(black)
    assert not np.isnan(score)
    assert score == 0.0


def test_flat_mid_gray_scores_on_exposure_only() -> None:
    """No edges at all -> sharpness 0, but a well-exposed frame still earns the exposure weight.

    This is the documented content-dependence of Laplacian variance, pinned as behaviour: a plain
    wall is not sharp, and the score says so without going to zero.
    """
    gray = np.full((120, 160, 3), 128, dtype=np.uint8)
    score = score_frame(gray)
    assert 0.0 < score <= W_EXPOSURE
    assert score == pytest.approx(W_EXPOSURE, abs=0.02)


def test_grayscale_and_bgra_accepted() -> None:
    bgr = _sharp_frame()
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
    assert score_frame(gray) == score_frame(bgra) == pytest.approx(score_frame(bgr), abs=1e-4)


@pytest.mark.parametrize(
    ("bad", "match"),
    [
        (np.empty((0, 0, 3), dtype=np.uint8), "empty"),
        (np.zeros((4, 4, 5), dtype=np.uint8), "shape"),
        (np.zeros((2, 2, 2, 3), dtype=np.uint8), "shape"),
        (np.zeros((4, 4, 3), dtype=np.float32), "8-bit"),
    ],
)
def test_bad_arrays_raise_value_error(bad: np.ndarray, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        score_frame(bad)


def test_non_array_raises_value_error() -> None:
    with pytest.raises(ValueError, match="not an image array"):
        score_frame("not a frame")  # type: ignore[arg-type]


def test_score_shot_missing_file(tmp_path: Any) -> None:
    with pytest.raises(FileNotFoundError, match="nope.mp4"):
        score_shot(str(tmp_path / "nope.mp4"), 0.0, 1.0, str(tmp_path))


def test_score_shot_rejects_bad_range(tmp_path: Any) -> None:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"\x00")
    with pytest.raises(ValueError, match="t_end"):
        score_shot(str(clip), 5.0, 5.0, str(tmp_path))
    with pytest.raises(ValueError, match="t_start"):
        score_shot(str(clip), -1.0, 5.0, str(tmp_path))


def test_score_shot_unreadable_video(tmp_path: Any) -> None:
    """A file that exists but is not decodable -> ValueError, not a silent 0.0."""
    junk = tmp_path / "junk.mp4"
    junk.write_bytes(b"not a video at all")
    with pytest.raises(ValueError, match="cannot open video|no frame readable"):
        score_shot(str(junk), 0.0, 1.0, str(tmp_path))


def _lavfi_clip(tmp_path: Any) -> Path:
    """A tiny deterministic clip, or skip if ffmpeg is unavailable."""
    import subprocess

    clip = tmp_path / "flat.mp4"
    proc = subprocess.run(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            "testsrc=s=160x120:d=2:r=10",
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
    return clip


def test_keyframe_written_with_shot_id(tmp_path: Any) -> None:
    clip = _lavfi_clip(tmp_path)
    work = tmp_path / "work"
    score = score_shot(str(clip), 0.0, 2.0, str(work), shot_id="shot_007")

    keyframe = work / "keyframes" / "shot_007.png"
    assert keyframe.is_file()
    assert 0.0 <= score <= 1.0
    # The written PNG is the frame that was scored.
    assert score_frame(cv2.imread(str(keyframe))) == score


def test_keyframe_name_falls_back_to_timestamp(tmp_path: Any) -> None:
    """No shot_id -> a unique timestamp-derived name, so two shots cannot collide."""
    clip = _lavfi_clip(tmp_path)
    work = tmp_path / "work"
    score_shot(str(clip), 0.0, 1.0, str(work))
    score_shot(str(clip), 1.0, 2.0, str(work))

    names = sorted(p.name for p in (work / "keyframes").iterdir())
    assert names == ["shot_at_00000500ms.png", "shot_at_00001500ms.png"]


def test_score_shot_samples_the_midpoint(tmp_path: Any) -> None:
    """SAMPLE_POSITION is fixed at the midpoint — the extracted frame must prove it."""
    clip = _lavfi_clip(tmp_path)
    work = tmp_path / "work"
    score_shot(str(clip), 0.0, 2.0, str(work), shot_id="shot_000")
    extracted = cv2.imread(str(work / "keyframes" / "shot_000.png"))

    capture = cv2.VideoCapture(str(clip))
    capture.set(cv2.CAP_PROP_POS_MSEC, 1000.0)  # (0.0 + 2.0) * SAMPLE_POSITION
    ok, expected = capture.read()
    capture.release()
    assert ok
    assert np.array_equal(extracted, expected)


@pytest.mark.slow
@pytest.mark.skipif(not IN_MP4.is_file(), reason="A/B test video not present (D-003, gitignored)")
def test_real_video_scores_spread(tmp_path: Any) -> None:
    """117 real shots: scores must spread, not cluster — a metric that returns ~0.8 for
    everything is as broken as a model that scores everything 0.8 (D-017)."""
    from elvideo.index.scenes import detect_shots

    shots = detect_shots(str(IN_MP4))
    scores = [
        score_shot(str(IN_MP4), s.t_start, s.t_end, str(tmp_path), shot_id=s.id) for s in shots
    ]

    assert len(scores) == len(shots)
    assert all(0.0 <= q <= 1.0 for q in scores)
    assert max(scores) - min(scores) > 0.3
    assert len({round(q, 2) for q in scores}) > 20
    assert len(list((tmp_path / "keyframes").glob("shot_*.png"))) == len(shots)

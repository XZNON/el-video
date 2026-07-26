"""Per-shot technical quality scoring — OpenCV, deterministic.

Shared with Path A. **No LLM involved, by design**: this number has to be reproducible so the two
paths' indexes are byte-comparable on it, and so a quality regression is attributable to the
footage rather than to sampling.

Laplacian variance (focus/sharpness) combined with an exposure term. See ``docs/IDEA.md``
§ *Shared contract* — the ``quality`` field — and § *Storage & speed* for the keyframe path.

The formula, pinned as module constants the same way ``scenes.py`` pins the detector (D-012) and
``transcribe.py`` pins the ASR settings (D-015). Path A must use the identical constants or the
field is not comparable across the A/B (D-002). Recorded in ``state/decisions-log.md`` D-017::

    sharpness = min(sqrt(laplacian_variance / SHARPNESS_SATURATION), 1.0)
    exposure  = brightness_term * clipping_term
    quality   = round(W_SHARPNESS * sharpness + W_EXPOSURE * exposure, ROUND_DIGITS)

**Why the square root.** Laplacian *variance* is quadratic in contrast: doubling a frame's edge
contrast quadruples it. Its square root is the Laplacian standard deviation, which is in gray
levels — the same units as the pixels — so it is linear in contrast and spreads real footage
across the range instead of piling it against a ceiling. Measured on the 117 shots of ``in.mp4``:
linear normalization put 22% of shots at exactly 1.0, the square root put none there (D-017).

**Known limitation, inherited equally by both paths:** Laplacian variance is content-dependent. A
low-detail scene — a plain wall, fog, a dark night shot — scores like a blurred one, because it
genuinely has no edge energy. That is what the metric measures, not a bug to fix here.
"""

from __future__ import annotations

import logging
import math
import time
from pathlib import Path

import cv2
import numpy as np

__all__ = [
    "CLIP_HIGH",
    "CLIP_LOW",
    "CLIP_SATURATION",
    "EXPOSURE_TARGET",
    "KEYFRAME_PNG_COMPRESSION",
    "ROUND_DIGITS",
    "SAMPLE_POSITION",
    "SHARPNESS_SATURATION",
    "W_EXPOSURE",
    "W_SHARPNESS",
    "score_frame",
    "score_shot",
]

logger = logging.getLogger(__name__)

SHARPNESS_SATURATION = 1000.0
"""Laplacian variance treated as fully sharp — i.e. a Laplacian std of ~31.6 gray levels.

Not a magic number: on ``in.mp4`` the 117 shot keyframes span variance 1.7–832.7 (median 169.2),
so the sharpest real frame in the clip lands at 0.91 and nothing clips. Headroom is deliberate —
a genuinely crisper camera should be able to score higher than the best frame of the test clip,
otherwise the metric stops discriminating on better footage. See D-017 for the full distribution.
"""

W_SHARPNESS = 0.7
"""Sharpness weight. Focus is the more decisive usability failure — a dark shot can be graded, an
out-of-focus one cannot be recovered."""

W_EXPOSURE = 0.3
"""Exposure weight. Complements :data:`W_SHARPNESS`; the two sum to 1.0."""

EXPOSURE_TARGET = 0.5
"""Ideal mean luma, normalized. Mid-gray. Distance from it is penalized linearly in both
directions, so an all-black and an all-white frame both score 0 on the brightness term."""

CLIP_LOW = 8
"""At or below this 8-bit level, a pixel is crushed — no shadow detail is recoverable."""

CLIP_HIGH = 247
"""At or above this 8-bit level, a pixel is blown — no highlight detail is recoverable."""

CLIP_SATURATION = 0.5
"""Clipped-pixel fraction at which the clipping term hits 0.

Half the frame. Well-exposed footage routinely clips *some* pixels — specular highlights, dark
corners; on ``in.mp4`` the worst shot clips 37.6% and the median 1.8% — so a low tolerance would
punish normal footage. At half the frame there is genuinely nothing left to grade.
"""

SAMPLE_POSITION = 0.5
"""Where inside ``[t_start, t_end)`` the keyframe is taken from — the midpoint, fixed.

Fixed rather than chosen per shot because the sampling point *is* part of the score: a different
frame is a different number, and reproducibility is the whole point of this module. The midpoint
also dodges the two worst places to sample — the frames adjacent to a cut, which may carry motion
blur or the tail of a transition.
"""

ROUND_DIGITS = 4
"""Scores are rounded to this many decimals.

OpenCV dispatches :func:`cv2.Laplacian` to different SIMD kernels depending on the CPU, so the
raw float64 can differ in its last bits between machines. Rounding at 4 decimals is far coarser
than that noise and far finer than any decision made on this field, which makes "bit-identical
across runs and machines" true in practice rather than aspirational.
"""

KEYFRAME_PNG_COMPRESSION = 3
"""Pinned so the same frame always produces the same PNG bytes. PNG is lossless either way, so
this affects file size and write speed only — never the score, which is computed from the decoded
frame, not from the file."""


def _to_gray(img: np.ndarray) -> np.ndarray:
    """Validate a frame and return it as single-channel 8-bit.

    Raises:
        ValueError: If ``img`` is not a non-empty 8-bit 2D/3D image array.
    """
    if not isinstance(img, np.ndarray):
        raise ValueError(f"not an image array: {type(img).__name__}")
    if img.size == 0:
        raise ValueError(f"empty image array: shape {img.shape}")
    if img.dtype != np.uint8:
        # cv2.imread and VideoCapture.read both yield uint8; anything else would silently
        # invalidate CLIP_LOW / CLIP_HIGH, which are 8-bit levels.
        raise ValueError(f"expected an 8-bit image, got dtype {img.dtype}")
    if img.ndim == 2:
        return img
    if img.ndim == 3 and img.shape[2] == 1:
        return img[:, :, 0]
    if img.ndim == 3 and img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.ndim == 3 and img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    raise ValueError(f"not an image array: shape {img.shape}")


def score_frame(img: np.ndarray) -> float:
    """Score a single frame for technical quality.

    Deterministic: the same pixels always give the same number.

    Sharpness is the Laplacian standard deviation normalized against
    :data:`SHARPNESS_SATURATION`; exposure is the distance of mean luma from
    :data:`EXPOSURE_TARGET`, scaled down by how much of the frame is crushed or blown. The two
    combine at :data:`W_SHARPNESS` / :data:`W_EXPOSURE`. See the module docstring and
    ``docs/IDEA.md`` § *Shared contract* — the ``quality`` field.

    Args:
        img: Frame as a BGR array, as returned by ``cv2.imread`` / ``cv2.VideoCapture.read``.
            Grayscale and BGRA are accepted too; 8-bit only.

    Returns:
        Quality in ``0.0``–``1.0``, combining Laplacian variance (sharpness) and exposure.

    Raises:
        ValueError: If ``img`` is empty or not a 2D/3D 8-bit image array.
    """
    gray = _to_gray(img)

    variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sharpness = min(math.sqrt(variance / SHARPNESS_SATURATION), 1.0)

    # Brightness: 1.0 at EXPOSURE_TARGET, falling linearly to 0.0 at pure black and pure white.
    brightness = float(gray.mean()) / 255.0
    span = max(EXPOSURE_TARGET, 1.0 - EXPOSURE_TARGET)
    brightness_term = max(1.0 - abs(brightness - EXPOSURE_TARGET) / span, 0.0)

    clipped = int(np.count_nonzero(gray <= CLIP_LOW) + np.count_nonzero(gray >= CLIP_HIGH))
    clipped_fraction = clipped / gray.size
    clipping_term = max(1.0 - clipped_fraction / CLIP_SATURATION, 0.0)

    exposure = brightness_term * clipping_term
    quality = W_SHARPNESS * sharpness + W_EXPOSURE * exposure
    # Clamped as well as rounded: Shot.quality is declared 0 <= q <= 1 and must never fail
    # validation because of float drift at the ends.
    return round(min(max(quality, 0.0), 1.0), ROUND_DIGITS)


def score_shot(
    path: str,
    t_start: float,
    t_end: float,
    work_dir: str,
    *,
    shot_id: str | None = None,
) -> float:
    """Score a shot by sampling a keyframe from inside it.

    Extracts the frame at :data:`SAMPLE_POSITION` through ``[t_start, t_end)`` — the midpoint — to
    ``{work_dir}/keyframes/{shot_id}.png`` and runs :func:`score_frame` on it. Seeks straight to
    the timestamp rather than decoding sequentially: 100–300 shots must cost seconds, not minutes
    (``docs/IDEA.md`` § *Storage & speed*).

    Args:
        path: Path to the source video.
        t_start: Shot start, seconds — from PySceneDetect.
        t_end: Shot end, seconds — from PySceneDetect.
        work_dir: Directory for extracted keyframes. Gitignored runtime output.
        shot_id: Shot id, e.g. ``"shot_007"``, used as the keyframe filename so keyframes match
            the ids in the index. Keyword-only with a ``None`` default: ``docs/IDEA.md`` fixes the
            positional signature and does not pass the id, so it is threaded the same way D-012
            and D-010 extended fixed signatures. When omitted the filename falls back to the
            sampled timestamp (``shot_at_00042100ms.png``), which is unique per shot and cannot
            collide.

    Returns:
        Quality in ``0.0``–``1.0`` for the shot.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the range is not ``t_end > t_start >= 0``, if the video cannot be opened,
            or if no frame can be read from the range.
    """
    if not Path(path).is_file():
        raise FileNotFoundError(f"video not found: {path}")
    if t_start < 0:
        raise ValueError(f"t_start must be >= 0, got {t_start}")
    if t_end <= t_start:
        raise ValueError(f"t_end ({t_end}) must be > t_start ({t_start})")

    started = time.perf_counter()
    sample_t = t_start + (t_end - t_start) * SAMPLE_POSITION

    capture = cv2.VideoCapture(path)
    try:
        if not capture.isOpened():
            raise ValueError(f"cannot open video: {path}")
        frame = _read_at(capture, sample_t)
        if frame is None:
            # A seek can land past the last decodable frame on a shot that ends at the tail of
            # the file; t_start is inside the range too, so it is a legitimate second try.
            frame = _read_at(capture, t_start)
        if frame is None:
            raise ValueError(f"no frame readable in [{t_start}, {t_end}) of {path}")
    finally:
        capture.release()

    name = shot_id if shot_id is not None else f"shot_at_{int(round(sample_t * 1000)):08d}ms"
    keyframe_path = Path(work_dir) / "keyframes" / f"{name}.png"
    keyframe_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(
        str(keyframe_path), frame, [cv2.IMWRITE_PNG_COMPRESSION, KEYFRAME_PNG_COMPRESSION]
    )

    quality = score_frame(frame)
    # Per-shot timing at DEBUG, not INFO: this runs 100-300 times per video. The stage total is
    # logged once by build.py (T007), which is the number the <5 min budget is measured against.
    logger.debug(
        "quality %s t=%.3fs -> %.4f in %.3fs",
        name,
        sample_t,
        quality,
        time.perf_counter() - started,
    )
    return quality


def _read_at(capture: cv2.VideoCapture, t: float) -> np.ndarray | None:
    """Seek to ``t`` seconds and decode one frame, or return ``None`` if it cannot be read."""
    capture.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
    ok, frame = capture.read()
    if not ok or frame is None or frame.size == 0:
        return None
    return frame

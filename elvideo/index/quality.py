"""Per-shot technical quality scoring — OpenCV, deterministic.

Shared with Path A. **No LLM involved, by design**: this number has to be reproducible so the two
paths' indexes are byte-comparable on it, and so a quality regression is attributable to the
footage rather than to sampling.

Laplacian variance (focus/sharpness) combined with an exposure term. See ``docs/IDEA.md``
§ *Shared contract* — the ``quality`` field.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

__all__ = ["score_frame", "score_shot"]


def score_frame(img: np.ndarray) -> float:
    """Score a single frame for technical quality.

    Deterministic: the same pixels always give the same number.

    Args:
        img: Frame as a BGR array, as returned by ``cv2.imread`` / ``cv2.VideoCapture.read``.

    Returns:
        Quality in ``0.0``–``1.0``, combining Laplacian variance (sharpness) and exposure.

    Raises:
        ValueError: If ``img`` is empty or not a 2D/3D image array.
    """
    raise NotImplementedError("see tasks/T005-quality.md")


def score_shot(path: str, t_start: float, t_end: float, work_dir: str) -> float:
    """Score a shot by sampling a keyframe from inside it.

    Extracts a representative frame from ``[t_start, t_end)`` to
    ``{work_dir}/keyframes/shot_###.png`` and runs :func:`score_frame` on it.

    Args:
        path: Path to the source video.
        t_start: Shot start, seconds — from PySceneDetect.
        t_end: Shot end, seconds — from PySceneDetect.
        work_dir: Directory for extracted keyframes. Gitignored runtime output.

    Returns:
        Quality in ``0.0``–``1.0`` for the shot.

    Raises:
        ValueError: If no frame can be read from the range.
    """
    raise NotImplementedError("see tasks/T005-quality.md")

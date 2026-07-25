"""Shot boundary detection — PySceneDetect.

Shared with Path A, and deliberately **classical**: these timings are the frame-accurate ones the
whole index is built on. Gemini's timestamps are second-granular and are never used for
``t_start`` / ``t_end``.

See ``docs/IDEA.md`` § *Architecture (Path B)* and § *Definition of done*.
"""

from __future__ import annotations

from elvideo.schema.models import Shot

__all__ = ["detect_shots"]


def detect_shots(path: str) -> list[Shot]:
    """Detect shot boundaries and return them as partially-populated shots.

    Only ``id``, ``t_start``, and ``t_end`` are set. Understanding, transcript, and quality
    fields keep their defaults until :func:`elvideo.index.build.build_index` fills them —
    see ``state/decisions-log.md`` D-005.

    Ids are zero-padded ordinals (``shot_000``, ``shot_001``, …) assigned in ``t_start`` order.

    Args:
        path: Path to the source video.

    Returns:
        Shots in chronological order, covering the video with no gaps.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
    """
    raise NotImplementedError("see tasks/T002-scenes.md")

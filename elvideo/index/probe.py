"""ffprobe wrapper — fills the ``video`` block of ``footage_index.json``.

Shared with Path A. Deterministic, no model involved.

``ffprobe`` ships with ffmpeg and must be on PATH; it is the one dependency ``uv sync`` will not
install. See ``docs/IDEA.md`` § *Scope* step 1.
"""

from __future__ import annotations

from elvideo.schema.models import VideoMeta

__all__ = ["probe"]


def probe(path: str) -> VideoMeta:
    """Read duration, frame rate, and dimensions from a video file.

    Shells out to ``ffprobe``. The returned ``fps`` is the **container** frame rate — it is not
    the sampling rate handed to Gemini, which lives in ``IndexMeta.sample_fps``.

    Args:
        path: Path to the source video.

    Returns:
        A :class:`~elvideo.schema.models.VideoMeta` — the ``video`` block of the index.

    Raises:
        FileNotFoundError: If ``path`` does not exist, or ``ffprobe`` is not on PATH.
        ValueError: If ``ffprobe`` exits non-zero or returns unparseable output.
    """
    raise NotImplementedError("see tasks/T001-probe.md")

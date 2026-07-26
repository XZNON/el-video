"""ffprobe wrapper — fills the ``video`` block of ``footage_index.json``.

Shared with Path A. Deterministic, no model involved.

``ffprobe`` ships with ffmpeg and must be on PATH; it is the one dependency ``uv sync`` will not
install. See ``docs/IDEA.md`` § *Scope* step 1.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from elvideo.schema.models import VideoMeta

__all__ = ["probe"]

_FFPROBE_ARGS = [
    "ffprobe",
    "-v",
    "error",
    "-select_streams",
    "v:0",
    "-show_entries",
    "stream=width,height,r_frame_rate",
    "-show_entries",
    "format=duration",
    "-of",
    "json",
]


def _parse_fps(r_frame_rate: str) -> float:
    """Parse ffprobe's ``r_frame_rate`` ``num/den`` form (``30000/1001`` -> 29.97...).

    The container rate is kept as a float, never rounded to an int — see the T001 acceptance
    criteria and ``docs/IDEA.md`` § *Shared contract* (the ``video`` block).
    """
    num_s, sep, den_s = r_frame_rate.partition("/")
    num = float(num_s)
    den = float(den_s) if sep else 1.0
    if den == 0:
        raise ValueError(f"zero denominator in r_frame_rate {r_frame_rate!r}")
    return num / den


def probe(path: str) -> VideoMeta:
    """Read duration, frame rate, and dimensions from a video file.

    Shells out to ``ffprobe``. The returned ``fps`` is the **container** frame rate — it is not
    the sampling rate handed to Gemini, which lives in ``IndexMeta.sample_fps``.
    See ``docs/IDEA.md`` § *Scope* step 1 and § *Shared contract*.

    Args:
        path: Path to the source video.

    Returns:
        A :class:`~elvideo.schema.models.VideoMeta` — the ``video`` block of the index.

    Raises:
        FileNotFoundError: If ``path`` does not exist, or ``ffprobe`` is not on PATH.
        ValueError: If ``ffprobe`` exits non-zero or returns unparseable output.
    """
    if not Path(path).is_file():
        raise FileNotFoundError(f"video not found: {path}")

    try:
        result = subprocess.run(
            [*_FFPROBE_ARGS, path],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError("ffprobe not on PATH - install ffmpeg") from exc

    if result.returncode != 0:
        raise ValueError(f"ffprobe failed on {path}: {result.stderr.strip()}")

    try:
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        return VideoMeta(
            path=path,
            duration_s=float(data["format"]["duration"]),
            fps=_parse_fps(stream["r_frame_rate"]),
            w=int(stream["width"]),
            h=int(stream["height"]),
        )
    except (KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"could not parse ffprobe output for {path}: {exc}\nstderr: {result.stderr.strip()}"
        ) from exc

"""Shot boundary detection — PySceneDetect.

Shared with Path A, and deliberately **classical**: these timings are the frame-accurate ones the
whole index is built on. Gemini's timestamps are second-granular and are never used for
``t_start`` / ``t_end``.

Detector settings are pinned here (``state/decisions-log.md`` D-012) so Path A can match them
exactly — a threshold difference would contaminate the A/B diff (D-002):

* Detector: ``ContentDetector`` (hard cuts only; crossfades need ``AdaptiveDetector``)
* Threshold: **27.0** — a per-video knob like ``fps``, never edited globally to fix one clip.

See ``docs/IDEA.md`` § *Architecture (Path B)* and § *Definition of done*.
"""

from __future__ import annotations

from pathlib import Path

from scenedetect import ContentDetector, SceneManager, open_video

from elvideo.schema.models import Shot

__all__ = ["DEFAULT_DETECTOR", "DEFAULT_THRESHOLD", "detect_shots"]

DEFAULT_DETECTOR = "ContentDetector"
"""Detector name, recorded for cross-repo reproducibility (D-002, D-012)."""

DEFAULT_THRESHOLD = 27.0
"""HSV content delta past which a cut is called. PySceneDetect's own default; adopted in D-012."""


def detect_shots(path: str, threshold: float = DEFAULT_THRESHOLD) -> list[Shot]:
    """Detect shot boundaries and return them as partially-populated shots.

    Only ``id``, ``t_start``, and ``t_end`` are set. Understanding, transcript, and quality
    fields keep their defaults until :func:`elvideo.index.build.build_index` fills them —
    see ``state/decisions-log.md`` D-005.

    Boundaries are frame-accurate: derived from PySceneDetect frame numbers and the container
    frame rate via ``FrameTimecode.seconds``, never from model timestamps
    (``docs/IDEA.md`` § *Definition of done*, bullet 3). Coverage is gapless — a video with no
    cuts yields exactly one shot spanning the whole duration.

    Ids are zero-padded ordinals (``shot_000``, ``shot_001``, …) assigned in ``t_start`` order.

    Args:
        path: Path to the source video.
        threshold: ``ContentDetector`` threshold — a per-video knob (D-012), surfaced on the
            CLI in T008. Lower splits within shots on fast motion; higher misses cuts in dark
            footage.

    Returns:
        Shots in chronological order, covering the video with no gaps.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
    """
    if not Path(path).is_file():
        raise FileNotFoundError(f"video not found: {path}")

    video = open_video(path)
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=threshold))
    manager.detect_scenes(video)
    # start_in_scene=True guarantees a single whole-video scene when no cuts are detected,
    # rather than an empty list.
    scenes = manager.get_scene_list(start_in_scene=True)

    return [
        Shot(id=f"shot_{i:03d}", t_start=start.seconds, t_end=end.seconds)
        for i, (start, end) in enumerate(scenes)
    ]

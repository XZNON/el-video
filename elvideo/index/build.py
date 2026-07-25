"""Orchestrator — run the stages, join them, validate, write.

Four producers feed this: ``probe``, ``scenes``, ``transcribe``, ``gemini``. ``quality`` needs
shot boundaries first. ``build_index`` joins all five into one ``footage_index.json`` and
validates it against the shared JSON Schema before writing.

Two things this module owns that nothing else does:

* **Alignment.** Gemini returns its own shot list with second-granular timings. Those are hints
  for matching only — every ``t_start`` / ``t_end`` written to the index comes from
  PySceneDetect. See ``docs/architecture.md`` § *Division of labour*.
* **Per-stage timing.** The <5 min budget is a per-stage claim, so "total: 4m12s" is not an
  acceptable log line. The A/B compares *where* each path spends time.

See ``docs/IDEA.md`` § *Architecture (Path B)* and § *Definition of done*.
"""

from __future__ import annotations

from typing import Any

from elvideo.index.gemini import DEFAULT_MEDIA_RESOLUTION, DEFAULT_SAMPLE_FPS
from elvideo.schema.models import MediaResolution, Shot, ShotUnderstanding

__all__ = ["align_understanding", "build_index"]


def build_index(
    path: str,
    work_dir: str = "work",
    fps: float = DEFAULT_SAMPLE_FPS,
    media_resolution: MediaResolution = DEFAULT_MEDIA_RESOLUTION,
) -> dict[str, Any]:
    """Run the full pipeline and return a validated ``footage_index.json`` document.

    Stages, in order: probe → shots → transcript → Gemini understanding → per-shot quality →
    join → validate. Each stage's wall-clock time is logged separately.

    Exactly one Gemini call is made, regardless of shot count.

    Args:
        path: Path to the source video.
        work_dir: Directory for keyframes and the output file. Gitignored.
        fps: Frames per second sampled for the Gemini call. Per-video knob.
        media_resolution: Token cost per frame for the Gemini call.

    Returns:
        The index as plain JSON-compatible data, already validated against
        ``footage_index.schema.json``.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        jsonschema.ValidationError: If the assembled document violates the shared contract.
    """
    raise NotImplementedError("see tasks/T007-build-orchestrator.md")


def align_understanding(shots: list[Shot], understanding: list[ShotUnderstanding]) -> list[Shot]:
    """Merge the model's judgment onto the frame-accurate shot list.

    The two lists need not be the same length — the model segments the video its own way. Match
    on temporal overlap using the ``*_hint`` fields, then copy ``caption``, ``editorial_score``,
    ``moment_reason``, and ``tags`` across.

    **``t_start`` and ``t_end`` are never touched.** They stay exactly as PySceneDetect returned
    them. Shots with no match keep their defaults (empty caption, ``editorial_score=None``).

    Args:
        shots: Frame-accurate shots from :func:`elvideo.index.scenes.detect_shots`.
        understanding: Per-shot judgment from :func:`elvideo.index.gemini.understand`.

    Returns:
        The same shots, with understanding fields populated where a match was found.
    """
    raise NotImplementedError("see tasks/T007-build-orchestrator.md")

"""Gemini-native understanding pass — **the Path B core**.

This is the analogue of El-Video's pluggable ``caption.py``: same role in the graph, different
backend (whole-video Gemini vs per-frame moondream2). Swapping this module out is exactly what
the A/B measures.

**The one rule that makes free-tier work: one Gemini call per video, never per shot.** A 10-min
video is 100–300 shots; per-shot calls blow the 10 RPM cap instantly, and they throw away the
thing that makes this path interesting — the model seeing the clip as continuous time, with
audio, and judging each moment *relative to the rest of the video*.

Settings are locked in ``docs/IDEA.md`` § *Gemini call settings*. Don't loosen them casually:
the whole point is that a 10-min video costs ~30K tokens against a 250K TPM cap, so iteration is
free all day.

The video is uploaded to the **Gemini File API**, which holds it for 48h at no cost. We don't
store it; Google does, temporarily.
"""

from __future__ import annotations

from elvideo.schema.models import MediaResolution, ShotUnderstanding

__all__ = [
    "DEFAULT_MEDIA_RESOLUTION",
    "DEFAULT_SAMPLE_FPS",
    "MODEL",
    "understand",
]

MODEL = "gemini-3.5-flash"
"""Pinned model string, free tier. Do not swap this for another model name."""

DEFAULT_SAMPLE_FPS = 0.5
"""One frame every 2s. A **per-video** knob: raise to 1–2 for action-heavy footage (gyms), lower
for static talking-head. Never change this default globally to fix one clip."""

DEFAULT_MEDIA_RESOLUTION: MediaResolution = "low"
"""66 tok/frame instead of 258 — 3× cheaper. SMB b-roll doesn't need fine-text reading."""


def understand(
    path: str,
    fps: float = DEFAULT_SAMPLE_FPS,
    media_resolution: MediaResolution = DEFAULT_MEDIA_RESOLUTION,
) -> list[ShotUnderstanding]:
    """Watch the whole video in **one** Gemini call and return per-shot judgment.

    Exactly one request to the model per invocation — this is asserted in T009 against the call
    log, not merely intended. The response is forced to strict JSON via a response schema (no
    prose), and the request is wrapped in exponential backoff on HTTP 429.

    What comes back is *judgment only*: caption, editorial score, reason, tags. Timings in the
    response are second-granular hints used for alignment and nothing else — ``t_start`` and
    ``t_end`` in the index always come from PySceneDetect.

    Args:
        path: Path to the source video. Uploaded to the Gemini File API for the call.
        fps: Frames per second sampled from the video. Per-video knob; see
            :data:`DEFAULT_SAMPLE_FPS`.
        media_resolution: Token cost per frame. See :data:`DEFAULT_MEDIA_RESOLUTION`.

    Returns:
        One :class:`~elvideo.schema.models.ShotUnderstanding` per shot the model identified, in
        chronological order. The count need not match PySceneDetect's shot count —
        :func:`elvideo.index.build.build_index` owns alignment.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        RuntimeError: If ``GEMINI_API_KEY`` is unset, or the model returns unparseable JSON
            after retries.
    """
    raise NotImplementedError("see tasks/T004-gemini-understanding.md")

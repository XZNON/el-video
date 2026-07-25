"""Audio transcription with word-level timing — WhisperX.

Shared with Path A. Word-level (not segment-level) timing is the requirement: it is what drives
precise cuts and filler removal downstream, and what :func:`words_in_range` slices per shot.

Typically the slowest stage, and one of the two the <5 min wall-clock budget is spent on (the
other being the single Gemini call). See ``docs/IDEA.md`` § *Storage & speed*.
"""

from __future__ import annotations

from elvideo.schema.models import Word

__all__ = ["transcribe", "words_in_range"]


def transcribe(path: str) -> list[Word]:
    """Transcribe the audio track, returning one entry per word with timing.

    Args:
        path: Path to the source video.

    Returns:
        Words in chronological order — the flat top-level ``words`` list of the index. Empty
        list if the video has no audio track.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
    """
    raise NotImplementedError("see tasks/T003-transcribe.md")


def words_in_range(words: list[Word], t_start: float, t_end: float) -> list[Word]:
    """Slice the flat word list to those falling inside a shot.

    Half-open on the right (``t_start <= w.t < t_end``) so a word on a cut boundary lands in
    exactly one shot and never both.

    Args:
        words: The full chronological word list from :func:`transcribe`.
        t_start: Shot start, seconds — from PySceneDetect.
        t_end: Shot end, seconds — from PySceneDetect.

    Returns:
        The words inside the range, in order. Empty list when the shot is silent.
    """
    raise NotImplementedError("see tasks/T003-transcribe.md")

"""Audio transcription with word-level timing — WhisperX.

Shared with Path A. Word-level (not segment-level) timing is the requirement: it is what drives
precise cuts and filler removal downstream, and what :func:`words_in_range` slices per shot.

Typically the slowest stage, and one of the two the <5 min wall-clock budget is spent on (the
other being the single Gemini call). See ``docs/IDEA.md`` § *Storage & speed*.

Settings are pinned as module constants so Path A can match them exactly (``D-002``). A different
model size or compute type changes the transcript, and a transcript difference would then pollute
the A/B diff with noise that has nothing to do with Understanding:

* Model: **base** — the largest size that keeps a 7-minute clip well inside the budget on CPU.
* Compute type: **int8** on CPU, **float16** on CUDA.
* Language: **en**, pinned rather than auto-detected — detection is a per-run guess, and a
  language flip would silently swap the alignment model too.
* Device: machine-dependent, so it is resolved by :func:`pick_device` and logged with the timing.

Two passes run here, and both are needed: faster-whisper produces *segment*-level text, and
WhisperX's wav2vec2 alignment pass is what turns that into per-word timing.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Any

from elvideo.schema.models import Word

__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_COMPUTE_TYPE",
    "DEFAULT_LANGUAGE",
    "DEFAULT_MODEL_SIZE",
    "pick_device",
    "transcribe",
    "words_in_range",
]

logger = logging.getLogger(__name__)

DEFAULT_MODEL_SIZE = "base"
"""Whisper model size, recorded for cross-repo reproducibility (D-002)."""

DEFAULT_COMPUTE_TYPE = "int8"
"""faster-whisper quantization. ``int8`` is the CPU-friendly one; ``float16`` suits CUDA."""

DEFAULT_LANGUAGE = "en"
"""Pinned, not auto-detected — a detection flip would change both transcript and align model."""

DEFAULT_BATCH_SIZE = 16
"""Segments per forward pass. Throughput knob only; does not change the output."""

_FFPROBE_AUDIO_ARGS = [
    "ffprobe",
    "-v",
    "error",
    "-select_streams",
    "a:0",
    "-show_entries",
    "stream=codec_type",
    "-of",
    "csv=p=0",
]


def pick_device() -> str:
    """Return ``"cuda"`` when torch sees a GPU, else ``"cpu"``.

    Device selection is the single biggest fork on transcription speed, so the resolved value is
    logged alongside the stage timing — an A/B speed comparison across the two repos is
    meaningless without it (T003 notes, D-002).
    """
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def _has_audio(path: str) -> bool:
    """True when the file carries at least one audio stream.

    Checked up front because a video with no audio must yield ``[]`` rather than raising, and
    WhisperX's ffmpeg-backed loader errors out on a silent container instead.
    """
    try:
        result = subprocess.run(
            [*_FFPROBE_AUDIO_ARGS, path],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError("ffprobe not on PATH - install ffmpeg") from exc

    return result.returncode == 0 and bool(result.stdout.strip())


def transcribe(
    path: str,
    *,
    model_size: str = DEFAULT_MODEL_SIZE,
    compute_type: str | None = None,
    language: str = DEFAULT_LANGUAGE,
    device: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[Word]:
    """Transcribe the audio track, returning one entry per word with timing.

    Runs faster-whisper for the text, then WhisperX's alignment pass for the per-word timing.
    The alignment pass is not optional: without it the output is segment-level, which is useless
    for precise cuts (``docs/IDEA.md`` § *Scope* step 3, § *Shared contract*).

    Args:
        path: Path to the source video.
        model_size: Whisper model size. Defaults to :data:`DEFAULT_MODEL_SIZE`; a deviation must
            be mirrored in Path A (D-002).
        compute_type: faster-whisper quantization. ``None`` resolves to
            :data:`DEFAULT_COMPUTE_TYPE` on CPU and ``"float16"`` on CUDA.
        language: Language code, pinned rather than detected.
        device: ``"cpu"`` or ``"cuda"``. ``None`` resolves via :func:`pick_device`.
        batch_size: Segments per forward pass — throughput only.

    Returns:
        Words in chronological order — the flat top-level ``words`` list of the index. Empty
        list if the video has no audio track.

    Raises:
        FileNotFoundError: If ``path`` does not exist, or ``ffprobe`` is not on PATH.
    """
    if not Path(path).is_file():
        raise FileNotFoundError(f"video not found: {path}")

    if not _has_audio(path):
        logger.info("transcribe: %s has no audio track - returning 0 words", path)
        return []

    import whisperx

    device = device or pick_device()
    if compute_type is None:
        compute_type = "float16" if device == "cuda" else DEFAULT_COMPUTE_TYPE

    t0 = time.perf_counter()
    audio = whisperx.load_audio(path)

    model = whisperx.load_model(
        model_size, device=device, compute_type=compute_type, language=language
    )
    result = model.transcribe(audio, batch_size=batch_size, language=language)
    t_asr = time.perf_counter() - t0

    t1 = time.perf_counter()
    align_model, metadata = whisperx.load_align_model(language_code=language, device=device)
    aligned = whisperx.align(
        result["segments"],
        align_model,
        metadata,
        audio,
        device,
        return_char_alignments=False,
    )
    t_align = time.perf_counter() - t1

    words = _to_words(aligned["word_segments"])

    # Device / model / compute type are logged *with* the numbers on purpose: timings from two
    # machines are not comparable without them (T003 notes, D-002).
    # ASCII only: a cp1252 Windows console mangles non-ASCII log output (see tasks/T008-cli.md).
    logger.info(
        "transcribe: %d words in %.1fs (asr %.1fs + align %.1fs) | "
        "model=%s device=%s compute_type=%s language=%s",
        len(words),
        t_asr + t_align,
        t_asr,
        t_align,
        model_size,
        device,
        compute_type,
        language,
    )
    return words


def _to_words(word_segments: list[dict[str, Any]]) -> list[Word]:
    """Convert WhisperX word segments to :class:`~elvideo.schema.models.Word`, chronologically.

    WhisperX omits ``start`` / ``end`` on words it could not align to any character — digits and
    symbols outside the wav2vec2 dictionary, typically. Those carry no timing, so they are
    dropped rather than emitted with a fabricated one.
    """
    words: list[Word] = []
    for seg in word_segments:
        start, end, text = seg.get("start"), seg.get("end"), str(seg.get("word", "")).strip()
        if start is None or end is None or not text:
            continue
        t = max(0.0, float(start))
        words.append(Word(t=t, d=max(0.0, float(end) - t), w=text))
    words.sort(key=lambda word: word.t)
    return words


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
    return [word for word in words if t_start <= word.t < t_end]

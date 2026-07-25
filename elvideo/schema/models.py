"""Pydantic models for the ``footage_index.json`` contract.

**This file is the single source of truth for the index types.** Every other module imports
from here — no ad hoc dicts anywhere in the pipeline.

It is one of two artifacts that define the contract, and they must stay in lockstep:

* this file — for Python
* ``elvideo/schema/footage_index.schema.json`` — language-independent, diffable against Path A

``tests/test_schema.py`` guards that they agree.

The contract is **shared with a separate repo** (Path A / El-Video, local-VLM understanding).
Changing the shape here is a two-repo change: log it in ``state/decisions-log.md`` and sync it
manually with the co-founder. See ``docs/IDEA.md`` § *Shared contract* and ``docs/schema.md``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "FootageIndex",
    "IndexMeta",
    "MediaResolution",
    "PathVariant",
    "Shot",
    "ShotUnderstanding",
    "VideoMeta",
    "Word",
]

PathVariant = Literal["gemini", "local"]
"""The A/B discriminator. This repo always emits ``"gemini"``."""

MediaResolution = Literal["low", "medium", "high"]
"""Gemini media resolution. Path B is locked to ``"low"`` — 66 tok/frame, not 258."""


class _Strict(BaseModel):
    """Base: reject unknown fields, mirroring ``additionalProperties: false`` in the JSON Schema."""

    model_config = ConfigDict(extra="forbid")


class VideoMeta(_Strict):
    """The ``video`` block — ffprobe output, uninterpreted.

    Produced by :func:`elvideo.index.probe.probe` (T001).
    See ``docs/IDEA.md`` § *Shared contract*.
    """

    path: str = Field(min_length=1, description="Path to the source video, as given on the CLI.")
    duration_s: float = Field(gt=0, description="Duration in seconds.")
    fps: float = Field(
        gt=0,
        description=(
            "Container frame rate. NOT the Gemini sampling rate — see "
            ":attr:`IndexMeta.sample_fps` for that."
        ),
    )
    w: int = Field(gt=0, description="Width in pixels.")
    h: int = Field(gt=0, description="Height in pixels.")


class IndexMeta(_Strict):
    """The ``index_meta`` block — provenance for this index.

    Must reflect what *actually ran*, not the defaults. This is what makes two indexes of the
    same footage comparable, and it is the A/B's label.
    """

    path_variant: PathVariant = Field(
        description="The A/B discriminator. This repo always emits 'gemini'."
    )
    model: str = Field(
        min_length=1,
        description=(
            "Understanding model that produced the captions. Path B pins 'gemini-3.5-flash'; "
            "Path A puts its local model name here."
        ),
    )
    media_resolution: MediaResolution = Field(
        description="Gemini media resolution. Path B uses 'low' — 66 tok/frame, not 258."
    )
    sample_fps: float = Field(
        gt=0,
        description=(
            "Frames per second fed to the understanding model. Path B default 0.5; a per-video "
            "knob, so record the value actually used."
        ),
    )


class Word(_Strict):
    """One word with timing, from WhisperX (T003).

    Lives in the flat top-level ``words`` list, not nested under a shot. Keys are short on
    purpose — there are thousands of these per video.
    """

    t: float = Field(ge=0, description="Word start time, seconds.")
    d: float = Field(ge=0, description="Word duration, seconds.")
    w: str = Field(description="The word.")

    @property
    def t_end(self) -> float:
        """End time in seconds — convenience for range slicing, not a serialized field."""
        return self.t + self.d


class Shot(_Strict):
    """One entry in ``shots[]`` — the payload of the index.

    **Populated in stages, by different owners.** :func:`elvideo.index.scenes.detect_shots`
    (T002) returns ``Shot`` objects with only ``id`` / ``t_start`` / ``t_end`` set; the
    understanding, transcript, and quality fields carry their defaults until
    :func:`elvideo.index.build.build_index` (T007) fills them in. That is why everything except
    the timings has a default — see ``state/decisions-log.md`` D-005 for why the type isn't
    split in two.

    Who decides what (``docs/IDEA.md`` § *Shared contract*):

    * ``t_start`` / ``t_end`` — **PySceneDetect**, frame-accurate. *Never* the model's own
      timestamps: those are second-granular and unusable for cuts.
    * ``transcript`` — **WhisperX**, via ``words_in_range()``.
    * ``quality`` — **OpenCV** Laplacian + exposure, deterministic.
    * ``caption`` / ``editorial_score`` / ``moment_reason`` / ``tags`` — the model's judgment.
    * ``is_candidate`` — derived from ``editorial_score``, not a model output.
    """

    id: str = Field(
        pattern=r"^shot_[0-9]{3,}$",
        description="Zero-padded ordinal, e.g. 'shot_007'. Ordered by t_start.",
    )
    t_start: float = Field(
        ge=0,
        description=(
            "Shot start, seconds. Frame-accurate, from PySceneDetect. NEVER from the "
            "understanding model."
        ),
    )
    t_end: float = Field(gt=0, description="Shot end, seconds. Frame-accurate, from PySceneDetect.")
    transcript: str = Field(
        default="",
        description="Words inside [t_start, t_end), joined. Empty string when silent — not None.",
    )
    caption: str = Field(
        default="", description="What is visually happening. From the understanding model."
    )
    editorial_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "How good a moment, 0–1. Path B's edge. Path A may leave this null — that gap IS "
            "the A/B signal."
        ),
    )
    moment_reason: str | None = Field(
        default=None,
        description="Why that editorial_score. Path B's edge. Path A may leave this null.",
    )
    is_candidate: bool = Field(
        default=False,
        description="Flagged good-moment. A derived view over editorial_score, not a model output.",
    )
    tags: list[str] = Field(
        default_factory=list, description="Free-form lowercase tags from the understanding model."
    )
    quality: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="OpenCV Laplacian + exposure, 0–1. Deterministic, no LLM involved.",
    )
    embedding: list[float] | None = Field(
        default=None,
        description=(
            "RESERVED — stays null in v1, no code computes it. Exists so Phase-2 cross-video "
            "search is not a schema break. See docs/IDEA.md § Non-goals."
        ),
    )

    @model_validator(mode="after")
    def _end_after_start(self) -> Shot:
        if self.t_end <= self.t_start:
            raise ValueError(f"{self.id}: t_end ({self.t_end}) must be > t_start ({self.t_start})")
        return self

    @property
    def duration_s(self) -> float:
        """Shot length in seconds — convenience, not a serialized field."""
        return self.t_end - self.t_start


class ShotUnderstanding(_Strict):
    """One shot's worth of *judgment*, as returned by the single Gemini call (T004).

    This is the model's output **before** it is merged onto the PySceneDetect shot list — it is
    not itself part of ``footage_index.json``. :func:`elvideo.index.build.build_index` aligns it
    to the real shots and copies these fields across.

    ``t_start`` / ``t_end`` here are the **model's own** second-granular guesses. They exist only
    to help align this record to the right :class:`Shot`, and they must never be written into the
    index. See ``docs/IDEA.md`` § *Gemini call settings* and ``docs/architecture.md``
    § *Division of labour*.
    """

    shot_index: int = Field(
        ge=0, description="0-based position in the shot list the model was asked to describe."
    )
    caption: str = Field(description="What is visually happening in the shot.")
    editorial_score: float = Field(ge=0, le=1, description="How good a moment, 0–1.")
    moment_reason: str = Field(description="Why that score — the justification, one clause.")
    tags: list[str] = Field(default_factory=list, description="Free-form lowercase tags.")
    t_start_hint: float | None = Field(
        default=None,
        ge=0,
        description=(
            "The model's own second-granular start guess. ALIGNMENT ONLY — never written to "
            "Shot.t_start."
        ),
    )
    t_end_hint: float | None = Field(
        default=None,
        ge=0,
        description=(
            "The model's own second-granular end guess. ALIGNMENT ONLY — never written to "
            "Shot.t_end."
        ),
    )


class FootageIndex(_Strict):
    """The whole ``footage_index.json`` document — the s1 deliverable.

    ``model_dump(mode="json")`` on this is what gets written to ``work/footage_index.json`` and
    validated against ``footage_index.schema.json``.
    """

    video: VideoMeta
    index_meta: IndexMeta
    shots: list[Shot] = Field(
        description=(
            "FULL index, not top-N: 'best moments' is a filter on is_candidate / a sort on "
            "editorial_score. Keeps both A/B paths schema-identical. See decisions-log D-001."
        )
    )
    words: list[Word] = Field(
        description="Flat word-level timing for the whole video, not nested under shots."
    )

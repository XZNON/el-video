"""The ``footage_index.json`` contract — pydantic models plus the JSON Schema they mirror.

Shared with Path A (El-Video). See ``docs/schema.md`` before changing anything here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elvideo.schema.models import (
    FootageIndex,
    IndexMeta,
    MediaResolution,
    PathVariant,
    Shot,
    ShotUnderstanding,
    VideoMeta,
    Word,
)

SCHEMA_PATH = Path(__file__).parent / "footage_index.schema.json"
"""Absolute path to the JSON Schema file — the language-independent half of the contract."""

__all__ = [
    "SCHEMA_PATH",
    "FootageIndex",
    "IndexMeta",
    "MediaResolution",
    "PathVariant",
    "Shot",
    "ShotUnderstanding",
    "VideoMeta",
    "Word",
    "load_schema",
    "validate_index",
]


def load_schema() -> dict[str, Any]:
    """Load the JSON Schema document from disk.

    Returns:
        The parsed contents of ``footage_index.schema.json``.
    """
    import json

    with SCHEMA_PATH.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def validate_index(doc: dict[str, Any]) -> None:
    """Validate an index document against the JSON Schema.

    This is the cross-repo check — deliberately independent of the pydantic types, so that an
    index produced by Path A can be validated with the same call.

    Args:
        doc: A ``footage_index.json`` document as plain JSON-compatible data.

    Raises:
        jsonschema.ValidationError: If the document does not satisfy the contract.

    See ``docs/IDEA.md`` § *Definition of done* — "validates against the shared schema".
    """
    raise NotImplementedError("see tasks/T006-schema-and-models.md")

"""The ``footage_index.json`` contract — pydantic models plus the JSON Schema they mirror.

Shared with Path A (El-Video). See ``docs/schema.md`` before changing anything here.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema.exceptions import ValidationError
from jsonschema.protocols import Validator
from jsonschema.validators import validator_for

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
    with SCHEMA_PATH.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


@lru_cache(maxsize=1)
def _validator() -> Validator:
    """The compiled validator for the contract, built once per process.

    ``build_index`` validates one document per run, but the tests validate dozens, and reading
    plus compiling the schema every time is pure overhead. The dialect comes from the schema's
    own ``$schema`` key rather than being hardcoded, so changing the dialect is a one-line edit
    to the JSON file.
    """
    schema = load_schema()
    cls = validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


def validate_index(doc: dict[str, Any]) -> None:
    """Validate an index document against the JSON Schema.

    This is the cross-repo check — deliberately independent of the pydantic types, so that an
    index produced by Path A can be validated with the same call. Validating through
    :class:`~elvideo.schema.models.FootageIndex` instead would only prove that pydantic agrees
    with itself, and would never catch the two artifacts drifting apart (D-009) — which is the
    failure this function exists to catch.

    Two checks run, in order:

    1. the JSON Schema, which covers types, enums, ranges, required keys and
       ``additionalProperties: false``;
    2. ``t_end > t_start`` on every shot, which JSON Schema cannot express — see
       :func:`_check_shot_timings` and D-022.

    Args:
        doc: A ``footage_index.json`` document as plain JSON-compatible data.

    Raises:
        jsonschema.ValidationError: If the document does not satisfy the contract. The message
            is prefixed with a JSON path into the document (``$.shots[42].editorial_score``), so
            a failure names the offending shot and field rather than only the document.

    See ``docs/IDEA.md`` § *Definition of done* — "validates against the shared schema".
    """
    errors = sorted(_validator().iter_errors(doc), key=_path_sort_key)
    if errors:
        raise _located(errors[0], total=len(errors))
    _check_shot_timings(doc)


def _path_sort_key(error: ValidationError) -> tuple[tuple[int, int, str], ...]:
    """Order errors by position in the document, so the one reported first is the first one.

    Path elements are ``int`` for array indices and ``str`` for object keys, and the two are not
    comparable — hence the per-element discriminator tuple, which also keeps ``shots[2]`` ahead
    of ``shots[10]`` instead of sorting them as strings.
    """
    return tuple(
        (0, part, "") if isinstance(part, int) else (1, 0, part) for part in error.absolute_path
    )


def _located(error: ValidationError, *, total: int) -> ValidationError:
    """Prefix an error's message with its JSON path, and say how many others there were.

    The error object itself is returned (not a copy) so ``absolute_path``, ``schema_path`` and
    ``context`` survive for callers that inspect them; only the human-facing message changes.
    ``ValidationError.message`` on its own reads "'x' is not of type 'number'", which does not
    say *where* — and 'where' is the whole point when the document holds 117 shots.
    """
    suffix = f" ({total} schema violations in total)" if total > 1 else ""
    error.message = f"{error.json_path}: {error.message}{suffix}"
    return error


def _check_shot_timings(doc: dict[str, Any]) -> None:
    """Enforce ``t_end > t_start`` on every shot.

    **This is the one contract rule the JSON Schema cannot carry.** Draft 2020-12 has no way to
    compare two sibling properties, so a document with a zero-length or backwards shot passes
    ``jsonschema`` cleanly. :class:`~elvideo.schema.models.Shot` enforces the rule on the pydantic
    side; this is the dict side, so a document that never went through pydantic — Path A's, or one
    read back off disk — is still checked. See D-022.

    Runs only after the schema check has passed, so the keys exist and are numbers.

    Raises:
        jsonschema.ValidationError: On the first shot whose ``t_end`` is not past its ``t_start``.
    """
    for i, shot in enumerate(doc["shots"]):
        t_start, t_end = shot["t_start"], shot["t_end"]
        if t_end <= t_start:
            path: list[str | int] = ["shots", i, "t_end"]
            raise ValidationError(
                message=(
                    f"$.shots[{i}].t_end: t_end ({t_end}) must be greater than t_start "
                    f"({t_start}) - shot {shot['id']!r} has zero or negative duration"
                ),
                validator="exclusiveMinimum",
                validator_value=t_start,
                instance=t_end,
                path=path,
                schema_path=["properties", "shots", "items", "properties", "t_end"],
            )

"""Guard the shared contract.

Placeholder-level on purpose: there is no real pipeline output yet to validate, so these tests
check that the schema file *itself* is well-formed and that the pydantic models haven't drifted
away from it at the field level. Real round-trip validation lands with T007/T009.

See ``docs/schema.md`` — the two artifacts must stay in lockstep.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from jsonschema.validators import validator_for

from elvideo.schema import SCHEMA_PATH
from elvideo.schema.models import FootageIndex, Shot, VideoMeta, Word


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    """The raw JSON Schema document."""
    with SCHEMA_PATH.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def test_schema_file_is_valid_json(schema: dict[str, Any]) -> None:
    """The contract file parses and is a JSON object."""
    assert isinstance(schema, dict)
    assert schema["title"] == "footage_index"


def test_schema_is_a_valid_json_schema(schema: dict[str, Any]) -> None:
    """The contract is itself a legal JSON Schema, per its declared ``$schema`` dialect."""
    cls = validator_for(schema)
    cls.check_schema(schema)


def test_top_level_keys_match_pydantic(schema: dict[str, Any]) -> None:
    """``FootageIndex`` and the JSON Schema agree on the top-level shape."""
    assert set(schema["properties"]) == set(FootageIndex.model_fields)
    assert set(schema["required"]) == set(FootageIndex.model_fields)


@pytest.mark.parametrize(
    ("pointer", "model"),
    [
        ("video", VideoMeta),
        ("shots", Shot),
        ("words", Word),
    ],
)
def test_block_fields_match_pydantic(
    schema: dict[str, Any], pointer: str, model: type[Any]
) -> None:
    """Each block's field names match its pydantic model — catches one-sided edits."""
    node = schema["properties"][pointer]
    props = node["items"]["properties"] if node["type"] == "array" else node["properties"]
    assert set(props) == set(model.model_fields), f"{pointer} drifted from {model.__name__}"


def test_embedding_is_reserved_and_nullable(schema: dict[str, Any]) -> None:
    """``embedding`` stays null in v1 — the field exists so Phase 2 isn't a schema break."""
    embedding = schema["properties"]["shots"]["items"]["properties"]["embedding"]
    assert "null" in embedding["type"]
    assert Shot.model_fields["embedding"].default is None


def test_path_variant_is_the_ab_discriminator(schema: dict[str, Any]) -> None:
    """Both A/B paths must be expressible in the same contract."""
    variants = schema["properties"]["index_meta"]["properties"]["path_variant"]["enum"]
    assert set(variants) == {"gemini", "local"}

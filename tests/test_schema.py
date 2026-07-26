"""Guard the shared contract.

Two halves. The first checks that the schema file *itself* is well-formed and that the pydantic
models haven't drifted away from it at the field level. The second exercises ``validate_index()``
against hand-written documents — deliberately built as plain dicts, with no pydantic involved,
because the JSON Schema is the interoperability artifact (D-009) and validating through pydantic
would only prove pydantic agrees with itself.

See ``docs/schema.md`` — the two artifacts must stay in lockstep.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError
from jsonschema.validators import validator_for

from elvideo.schema import SCHEMA_PATH, validate_index
from elvideo.schema.models import FootageIndex, IndexMeta, Shot, VideoMeta, Word


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
        ("index_meta", IndexMeta),
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


def test_index_meta_records_how_shots_were_cut(schema: dict[str, Any]) -> None:
    """D-013: shot boundaries are the index's spine, so the detector settings are provenance.

    Both fields are required, with no default — ``index_meta`` must reflect what actually ran.
    """
    required = schema["properties"]["index_meta"]["required"]
    assert {"scene_detector", "scene_threshold"} <= set(required)
    for name in ("scene_detector", "scene_threshold"):
        assert IndexMeta.model_fields[name].is_required(), f"{name} must not have a default"


def test_no_code_writes_the_embedding_field() -> None:
    """``embedding`` is RESERVED — it stays null in v1 and **no code computes it**.

    Enforced rather than asserted in prose: anything that assigns ``embedding=`` or emits an
    ``"embedding":`` key outside the schema package is writing to a reserved field. Mentioning
    the name in prose is fine; writing to it is not.
    """
    src = Path(__file__).resolve().parents[1] / "elvideo"
    writes = re.compile(r"""embedding\s*=|["']embedding["']\s*:""")
    offenders = [
        str(p.relative_to(src))
        for p in src.rglob("*.py")
        if p.parent.name != "schema" and writes.search(p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"embedding is reserved but written in: {offenders}"


# --------------------------------------------------------------------------------------------
# validate_index() — T006
# --------------------------------------------------------------------------------------------


def _shot(**overrides: Any) -> dict[str, Any]:
    """One minimal valid shot as a plain dict. No pydantic — that is the point of these tests."""
    shot: dict[str, Any] = {
        "id": "shot_000",
        "t_start": 0.0,
        "t_end": 2.5,
        "transcript": "",
        "caption": "",
        "editorial_score": None,
        "moment_reason": None,
        "is_candidate": False,
        "tags": [],
        "quality": 0.0,
        "embedding": None,
    }
    shot.update(overrides)
    return shot


@pytest.fixture
def doc() -> dict[str, Any]:
    """A hand-written minimal valid document, fresh per test so mutations don't leak."""
    return {
        "video": {"path": "in.mp4", "duration_s": 428.106, "fps": 25.0, "w": 1280, "h": 720},
        "index_meta": {
            "path_variant": "gemini",
            "model": "gemini-3.5-flash",
            "media_resolution": "low",
            "sample_fps": 0.5,
            "scene_detector": "ContentDetector",
            "scene_threshold": 27.0,
        },
        "shots": [
            _shot(),
            _shot(
                id="shot_001",
                t_start=2.5,
                t_end=9.0,
                transcript="so this is our weekend brunch special",
                caption="chef plating a dosa, steam rising",
                editorial_score=0.86,
                moment_reason="hero food shot, clean framing",
                is_candidate=True,
                tags=["food", "hero"],
                quality=0.79,
            ),
        ],
        "words": [{"t": 0.928, "d": 0.22, "w": "so"}],
    }


def test_minimal_document_validates(doc: dict[str, Any]) -> None:
    """The hand-written document passes — and ``validate_index`` returns nothing on success."""
    assert validate_index(doc) is None


def test_path_a_shaped_document_validates(doc: dict[str, Any]) -> None:
    """A Path A index — no ``editorial_score``, no ``moment_reason`` — passes the same schema.

    That permission is the A/B measurement, not a loophole (``docs/schema.md`` § *Path A's edge
    vs Path B's edge*).
    """
    for shot in doc["shots"]:
        shot["editorial_score"] = None
        shot["moment_reason"] = None
        shot["is_candidate"] = False
    doc["index_meta"]["path_variant"] = "local"
    doc["index_meta"]["model"] = "moondream2"
    validate_index(doc)


def test_pydantic_round_trip_validates(doc: dict[str, Any]) -> None:
    """The two artifacts agree in practice, not just field-for-field.

    ``FootageIndex.model_dump(mode="json")`` is exactly what T007 writes to disk, so this is the
    check that the pydantic half can actually produce a document the JSON Schema half accepts.
    """
    validate_index(FootageIndex.model_validate(doc).model_dump(mode="json"))


def test_extra_top_level_key_fails(doc: dict[str, Any]) -> None:
    """``additionalProperties: false`` is deliberate — an unknown top-level key is a contract
    break, not an extension point."""
    doc["best_moments"] = [{"id": "shot_001"}]
    with pytest.raises(ValidationError) as excinfo:
        validate_index(doc)
    assert "best_moments" in str(excinfo.value)


def test_extra_shot_key_fails(doc: dict[str, Any]) -> None:
    """Same rule inside a shot, and the error names which shot."""
    doc["shots"][1]["confidence"] = 0.9
    with pytest.raises(ValidationError) as excinfo:
        validate_index(doc)
    assert excinfo.value.json_path == "$.shots[1]"
    assert "confidence" in str(excinfo.value)


def test_t_end_before_t_start_fails(doc: dict[str, Any]) -> None:
    """The invariant JSON Schema cannot express (D-022) — enforced in code instead."""
    doc["shots"][1]["t_start"] = 9.0
    doc["shots"][1]["t_end"] = 2.5
    with pytest.raises(ValidationError) as excinfo:
        validate_index(doc)
    assert list(excinfo.value.absolute_path) == ["shots", 1, "t_end"]
    assert "shot_001" in excinfo.value.message


def test_zero_length_shot_fails(doc: dict[str, Any]) -> None:
    """``t_end == t_start`` is a zero-frame shot — rejected on the same rule."""
    doc["shots"][0]["t_end"] = doc["shots"][0]["t_start"]
    with pytest.raises(ValidationError, match=r"shots\[0\]"):
        validate_index(doc)


def test_schema_alone_does_not_catch_backwards_timings(doc: dict[str, Any]) -> None:
    """Pins *why* the timing check exists in code: raw ``jsonschema`` passes this document.

    If a future dialect ever lets the schema express it, this test fails and the code check can
    be deleted — which is the only way anyone would notice.
    """
    doc["shots"][0]["t_start"] = 9.0
    doc["shots"][0]["t_end"] = 2.5
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator_for(schema)(schema).validate(doc)


def test_error_names_the_shot_and_the_field(doc: dict[str, Any]) -> None:
    """"Document invalid" is useless at 117 shots. The message carries the JSON path."""
    doc["shots"][1]["editorial_score"] = 1.5
    with pytest.raises(ValidationError) as excinfo:
        validate_index(doc)
    assert excinfo.value.json_path == "$.shots[1].editorial_score"
    assert excinfo.value.message.startswith("$.shots[1].editorial_score:")


def test_missing_required_shot_field_fails(doc: dict[str, Any]) -> None:
    """Every shot field is required in the JSON Schema, even the ones pydantic defaults."""
    del doc["shots"][0]["quality"]
    with pytest.raises(ValidationError) as excinfo:
        validate_index(doc)
    assert excinfo.value.json_path == "$.shots[0]"
    assert "quality" in excinfo.value.message


def test_first_error_is_reported_in_document_order(doc: dict[str, Any]) -> None:
    """Deterministic reporting: earliest path wins, and the total is stated rather than hidden."""
    doc["video"]["w"] = 0
    doc["shots"][1]["quality"] = 2.0
    with pytest.raises(ValidationError) as excinfo:
        validate_index(doc)
    assert excinfo.value.json_path == "$.shots[1].quality"
    assert "2 schema violations in total" in excinfo.value.message


def test_shot_id_pattern_accommodates_more_than_999_shots(doc: dict[str, Any]) -> None:
    """The test clip has 117 shots, so 3-or-more digits is load-bearing, not hypothetical."""
    doc["shots"][1]["id"] = "shot_1000"
    validate_index(doc)


@pytest.mark.parametrize("bad_id", ["shot_07", "shot_", "SHOT_007", "shot_007a", "007"])
def test_malformed_shot_id_fails(doc: dict[str, Any], bad_id: str) -> None:
    """Ids are the join key to ``work/keyframes/`` (D-018), so the format is not cosmetic."""
    doc["shots"][0]["id"] = bad_id
    with pytest.raises(ValidationError, match=r"shots\[0\]\.id"):
        validate_index(doc)


def test_index_meta_without_detector_settings_fails(doc: dict[str, Any]) -> None:
    """D-013: an index that doesn't say how its shots were cut is not a valid index."""
    del doc["index_meta"]["scene_threshold"]
    with pytest.raises(ValidationError, match="scene_threshold"):
        validate_index(doc)


def test_silent_shot_transcript_must_be_empty_string_not_null(doc: dict[str, Any]) -> None:
    """``transcript`` is ``""`` when silent — ``null`` is a different claim and is rejected."""
    doc["shots"][0]["transcript"] = None
    with pytest.raises(ValidationError, match=r"shots\[0\]\.transcript"):
        validate_index(doc)


def test_unknown_path_variant_fails(doc: dict[str, Any]) -> None:
    """The A/B discriminator is a closed set — a third value would silently escape the A/B."""
    doc["index_meta"]["path_variant"] = "vertex"
    with pytest.raises(ValidationError, match="path_variant"):
        validate_index(doc)

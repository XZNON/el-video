# T006 — `schema/`: the shared contract + validator

**Status:** `done` (2026-07-26) — scaffold seeded a first cut; this task **locked** it.
`validate_index()` is implemented; see D-022 for the one invariant that lives in code rather than
in the schema file.

## Goal

Finalize the `footage_index.json` contract as two artifacts that agree with each other and with
Path A: pydantic models for Python, and a JSON Schema for cross-repo validation. Then implement
`validate_index()`.

The bootstrap session already wrote `models.py`, `footage_index.schema.json`, and
`tests/test_schema.py` — those are declarative, not pipeline logic, so they were seeded rather
than stubbed.

**Status update 2026-07-26:** the shape is now **locked** — D-001 confirmed, D-013 shipped, and
the co-founder sign-off criterion is N/A on a solo repo (D-016). **All that remains is
`validate_index()`.**

## Reads / depends on

- `docs/IDEA.md` § *Shared contract — `footage_index.json` (extended)* — the field-for-field
  source of truth
- `docs/schema.md` — the prose version, including which fields are Path B's edge
- `state/decisions-log.md` **D-001** (full index vs top-N) — this task can't close until it does
- Tasks: T010 shares D-001 with this task.

## Inputs / outputs

**In:** `docs/IDEA.md`'s JSON example; whatever Path A actually emits.
**Out:**
- `elvideo/schema/models.py` — pydantic, the single source of truth every module imports
- `elvideo/schema/footage_index.schema.json` — language-independent, diffable against Path A
- `validate_index(doc) -> None` — raises on violation
- `tests/test_schema.py` — guards that the two artifacts haven't drifted apart

## Acceptance criteria

- [x] Pydantic models mirror `docs/schema.md` **exactly** — same field names, same types, same
      nullability. `tests/test_schema.py::test_block_fields_match_pydantic` enforces this.
      Confirmed unchanged this session; all four blocks covered since D-013.
- [x] `embedding` is present, typed nullable, defaults to `None`, and **no code writes to it** —
      the second half is now enforced, not asserted in prose:
      `test_no_code_writes_the_embedding_field` scans `elvideo/` outside `schema/` for
      `embedding=` / `"embedding":` and fails on a hit.
- [x] `editorial_score` and `moment_reason` are nullable, so a Path A index validates against the
      same schema. That permission is the A/B measurement, not a loophole.
      `test_path_a_shaped_document_validates` runs a `path_variant="local"` document with both
      fields null through the same call.
- [x] `validate_index()` is implemented on `jsonschema`, works on a plain dict (no pydantic
      involvement), and raises `ValidationError` with a useful path into the document — messages
      are prefixed with the JSON path (`$.shots[1].editorial_score: ...`), the first error in
      document order is the one reported, and the total violation count is stated.
- [x] A hand-written minimal valid document passes; a document with an extra top-level key fails
      (`additionalProperties: false` is deliberate); a document with `t_end < t_start` fails —
      the last one via a Python check, because JSON Schema cannot express it. **See D-022.**
- [x] `Shot.id` pattern accommodates 100+ shots (`^shot_[0-9]{3,}$`, not exactly-3).
      `shot_1000` validates; `shot_07`, `SHOT_007`, `shot_007a`, `007` all fail.
- [x] **D-001 resolved and logged** (2026-07-26) — full index + `is_candidate`. No code change;
      the scaffold already implemented the assumption.
- [x] **D-013 resolved and logged** (2026-07-26) — **shipped.** `index_meta` gained
      `scene_detector` and `scene_threshold`, both required with no defaults, in `models.py` and
      `footage_index.schema.json`. `tests/test_schema.py` gained a guard, and `index_meta` was
      added to the field-parity parametrize, which had been missing the block.
- [ ] ~~The schema file is shared with the co-founder and confirmed against what Path A emits~~ —
      **N/A, solo repo (D-016).** The remaining check is local: the two artifacts agree
      field-for-field, which `test_block_fields_match_pydantic` now covers for all four blocks.
- [x] `uv run pytest tests/test_schema.py` passes clean — **31 tests** (was 8).

## Constraints that bite here

- **This is a two-repo change surface.** This repo has no automated way to know if Path A
  changed too. Every edit to the shape gets logged in `state/decisions-log.md` **and** manually
  synced. Treat the schema as an interface, not as a private data model.
- **Both paths must emit this identically.** `docs/IDEA.md` says: *"Lock it before either of us
  codes further."* T001–T005 are already coding against it, so locking it is now urgent, not
  ceremonial.
- Pydantic models, never raw dicts, everywhere in the pipeline.

## Notes

The two artifacts existing separately is deliberate and slightly redundant: pydantic can generate
JSON Schema, but its output is verbose, includes `$defs` indirection, and drifts in shape between
pydantic versions — which makes it useless for a clean `diff` against another repo's output. The
hand-written schema is the interoperability artifact; the tests are what keep the redundancy
honest.

`Shot` carries defaults for everything except the timings because it's populated in stages by
different owners (T002 sets timings, T004/T007 set understanding, T005 sets quality). See D-005
for why it isn't split into two types.

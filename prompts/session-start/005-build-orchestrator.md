# Session 005 — T006 then T007: `validate_index()`, then `build.py`

**Two tasks, in this order.** T006 is one function and T007 has a criterion that depends on it
("output validates via `validate_index()` **before** it is written"), so T006 lands first and
closes — it is not a footnote to T007.

## Read these first, in this order

1. `state/progress.json` — what's live, what's blocked
2. Last ~3 entries of `state/session-log.md` — what the previous sessions left behind
3. `.claude/CLAUDE.md` — hard constraints and session protocol
4. `tasks/T006-schema-and-models.md`, then `tasks/T007-build-orchestrator.md` — both in full
5. `docs/IDEA.md` § *Shared contract*, § *Architecture (Path B)*, § *Storage & speed*,
   § *Definition of done*
6. `state/decisions-log.md` — **D-005, D-009, D-010, D-013, D-014, D-018, D-021** specifically

Run `/start-task T006` first. Only after it closes, `/start-task T007`.

## Where things stand

Every input stage is implemented and measured on the real test clip `in.mp4` (7:08, 117 shots,
gitignored, at the repo root): `probe.py`, `scenes.py` (117 shots in 25.3s), `transcribe.py` (1436
words in 102.7s warm on CPU), `quality.py` (117 scores in 18.8s, mean 0.465), and now `gemini.py`.
The schema is locked in `elvideo/schema/models.py` + `footage_index.schema.json`; only
`validate_index()` is still a stub (T006, `partial`).

**`gemini.py` is code-complete but never ran against the real API** — the `GEMINI_API_KEY` in
`.env` returns `429 RESOURCE_EXHAUSTED — "prepayment credits are depleted"` on every request,
including a 5-token text-only one (**D-021**). That does **not** block this session: 47 fast tests
pin `understand()`'s request and output shape, so `build.py` is written and tested against a mocked
understanding pass. Gates at last checkpoint: `pytest -m "not slow"` 101 passed, `ruff` clean,
`mypy elvideo` strict clean.

## First: T006 — `validate_index()`

**Goal:** implement the last stub in `elvideo/schema/`. The contract's *shape* is already locked
(D-001 confirmed, D-013 shipped, the Path A sign-off criterion struck as N/A under D-016); what is
missing is the function that enforces it on a plain dict.

**Where it goes:** `elvideo/schema/` — `validate_index(doc) -> None`, raising on violation.
`jsonschema` is already a dependency.

**Remaining acceptance criteria** (the rest of the task file's list is already `[x]` or struck N/A —
do not redo them, but do confirm the boxes still hold):

- [ ] Pydantic models mirror `docs/schema.md` exactly — same field names, types, nullability.
      `tests/test_schema.py::test_block_fields_match_pydantic` enforces this; it now covers all four
      blocks including `index_meta`.
- [ ] `embedding` is present, typed nullable, defaults to `None`, and **no code writes to it**.
- [ ] `editorial_score` and `moment_reason` are nullable, so a Path A index validates against the
      same schema. That permission is the A/B measurement, not a loophole.
- [ ] `validate_index()` is implemented on **`jsonschema`**, works on a **plain dict with no
      pydantic involvement**, and raises `ValidationError` with a **useful path into the document**
      (which shot, which field — not just "document invalid").
- [ ] A hand-written minimal valid document passes; a document with an extra top-level key fails
      (`additionalProperties: false` is deliberate); a document with `t_end < t_start` fails.
- [ ] `Shot.id` pattern accommodates 100+ shots — `^shot_[0-9]{3,}$`, not exactly-3. The test clip
      has 117 shots, so this is load-bearing, not hypothetical.
- [ ] `uv run pytest tests/test_schema.py` passes clean.

**Why it validates the dict and not the pydantic object:** the JSON Schema is the interoperability
artifact (D-009). Validating through pydantic would only prove pydantic agrees with itself, and
would never catch the two artifacts drifting apart — which is the failure this function exists to
catch.

## Then: T007 — `build.py`, the orchestrator

**Goal:** run every stage, join the results into one `footage_index.json`, validate it against the
shared schema, write it to `work/`, and log **per-stage** timing. This is where the two hard joins
happen — Gemini's judgment onto PySceneDetect's boundaries, and the flat word list into per-shot
transcripts.

**Signatures:** `build_index(path, work_dir="work", fps=..., media_resolution=...) -> dict[str, Any]`,
and it also owns `align_understanding(shots, understanding) -> list[Shot]`.

**Acceptance criteria** (restated in full — `tasks/T007-build-orchestrator.md` is authoritative if
they disagree):

- [ ] Stage order: probe → shots → transcript → Gemini → quality → join → validate → write.
- [ ] **Exactly one Gemini call**, whatever the shot count. Assert the counter from T004 —
      `elvideo.index.gemini.generate_call_count()`, with `reset_call_count()` at the start of the
      run.
- [ ] `align_understanding()` copies `caption`, `editorial_score`, `moment_reason`, `tags` onto the
      frame-accurate shots and **never touches `t_start` / `t_end`**.
- [ ] Alignment survives a length mismatch: the model returning 40 segments for 120 detected shots
      must not crash, drop shots, or shift the mapping. Unmatched shots keep their defaults
      (`caption=""`, `editorial_score=None`).
- [ ] **D-010 is resolved (option 2): alignment is an index lookup on `shot_index`, not an overlap
      match.** A `shot_index` outside the real range fails loudly — it means the model ignored the
      boundaries it was given, and silently dropping it yields captions on the wrong shots with no
      error anywhere.
- [ ] Every detected shot appears in the output — **full index, not top-N** (D-001).
- [ ] `is_candidate` is derived from `editorial_score`, with the threshold documented and recorded,
      not a magic number buried in a comparison.
- [ ] `transcript` is `words_in_range()` joined; silent shots get `""`, not `None`.
- [ ] `index_meta` records what **actually ran** — the real `sample_fps` and `media_resolution` used
      for this run, not the defaults. `path_variant` is `"gemini"`.
- [ ] `index_meta.scene_detector` / `.scene_threshold` carry the values **actually passed to
      `detect_shots()`** (D-013). Both are required with no schema default, so an index that
      doesn't set them fails `validate_index()` — read them off the call, don't re-read the module
      constants.
- [ ] Output validates via `validate_index()` **before** it is written. A validation failure leaves
      no partial file behind.
- [ ] **Per-stage timing logged** — one line per stage plus a total. "Total: 4m12s" alone fails this
      criterion.
- [ ] `embedding` is `null` on every shot.
- [ ] Full run on a 10-min video completes in **<5 min wall-clock**.

## Constraints that bite on this task specifically

- **One Gemini call per video, never per shot.** This module is exactly where a well-meaning
  refactor ("just re-ask for the shots it missed") would break the rule. Don't. Assert the counter
  instead.
- **PySceneDetect owns the timings.** Gemini's `t_start_hint` / `t_end_hint` are second-granular and
  are for matching only — they never reach `Shot.t_start` / `t_end`.
- **Per-stage timing, not just total.** The A/B compares *where* each path spends its time.
- **`score_shot()` must be called with `shot_id=shot.id`** (D-018), or the PNGs in
  `work/keyframes/` stop matching the ids in the index and the folder is useless for debugging.
- **Container duration ≠ video-stream duration** (D-014): on `in.mp4`, `probe().duration_s` is
  428.106 but the last shot's `t_end` is 428.04, a 0.066s gap — wider than one frame. Do not assert
  `shots[-1].t_end == video.duration_s` to frame precision, and expect `words[]` to legitimately
  outlast the final shot.
- **Local filesystem only.** Write to `work/`. No GCS, no Firestore, no embeddings.
- **`validate_index()` must already exist** — that is why T006 runs first in this session.

## Blockers and open decisions affecting this

- **D-021 (open, needs the owner) — the `GEMINI_API_KEY` has no quota.** Does not block writing or
  unit-testing `build.py`; it does block the last criterion (a real <5 min end-to-end run) and all
  of T009. Unblocks with a key from an AI Studio project with **billing not enabled** (the free
  tier), then `uv run pytest tests/test_gemini.py -m slow --log-cli-level=INFO`.
- **D-010 / D-013 / D-018** are resolved and each imposes a criterion above — implement them as
  written, they are not open questions.
- No other open decisions. `docs/IDEA.md` conflicts get logged in `state/decisions-log.md`, never
  silently resolved.

## Definition of done for the session

**T006 closes** — `validate_index()` implemented, every criterion above ticked, T006 moves from
`partial` to `done` in `progress.json` and `tasks/backlog.md`. It is a small task; if it somehow
consumes the session, stopping there with T006 closed is a better outcome than two half-tasks.

**T007:** `uv run python -m elvideo index in.mp4` is not required yet (that's T008), but
`build_index("in.mp4")` produces a document that passes `validate_index()`, covers all 117 shots
with no gaps, carries per-stage timing in the log, and writes `work/footage_index.json` — with the
Gemini stage mocked if D-021 is still open, and the mocking said plainly in the log rather than
glossed. Alignment has its own tests on synthetic inputs (exact 1:1, fewer segments than shots,
more, none at all, out-of-range index). `uv run pytest`, `uv run ruff check .`, and
`uv run mypy elvideo` all clean.

End with `/checkpoint`.

# T007 — `build.py`: orchestrator

**Status:** `not_started`

## Goal

Run every stage, join the results into one `footage_index.json`, validate it against the shared
schema, and write it to disk — logging **per-stage** timing along the way.

This is where the two hard joins happen: aligning Gemini's judgment onto PySceneDetect's
boundaries, and slicing the flat word list into per-shot transcripts.

## Reads / depends on

- `docs/IDEA.md` § *Architecture (Path B)*, § *Storage & speed*, § *Definition of done*
- `docs/architecture.md` § *Division of labour*
- Tasks: T001, T002, T003, T004, T005, T006 — **all of them**. This is the join point.

## Inputs / outputs

**In:** `path: str`, `work_dir: str = "work"`, `fps: float`, `media_resolution: MediaResolution`.
**Out:** `dict[str, Any]` — a validated index document, also written to
`{work_dir}/footage_index.json`.

Also owns `align_understanding(shots, understanding) -> list[Shot]`.

## Acceptance criteria

- [ ] Stage order: probe → shots → transcript → Gemini → quality → join → validate → write.
- [ ] **Exactly one Gemini call**, whatever the shot count. Assert the counter from T004.
- [ ] `align_understanding()` copies `caption`, `editorial_score`, `moment_reason`, `tags` onto
      the frame-accurate shots and **never touches `t_start` / `t_end`**.
- [ ] Alignment survives a length mismatch: the model returning 40 segments for 120 detected
      shots must not crash, drop shots, or shift the mapping. Unmatched shots keep their
      defaults (`caption=""`, `editorial_score=None`).
- [ ] Every detected shot appears in the output — **full index, not top-N** (D-001).
- [ ] `is_candidate` is derived from `editorial_score`, with the threshold documented and
      recorded, not a magic number buried in a comparison.
- [ ] `transcript` is `words_in_range()` joined; silent shots get `""`, not `None`.
- [ ] `index_meta` records what **actually ran** — the real `sample_fps` and `media_resolution`
      used for this run, not the defaults. `path_variant` is `"gemini"`.
- [ ] Output validates via `validate_index()` **before** it is written. A validation failure
      leaves no partial file behind.
- [ ] **Per-stage timing logged** — one line per stage plus a total. "Total: 4m12s" alone fails
      this criterion.
- [ ] `embedding` is `null` on every shot.
- [ ] Full run on a 10-min video completes in **<5 min wall-clock**.

## Constraints that bite here

- **Per-stage timing, not just total.** The A/B compares *where* each path spends its time; a
  single total number tells the writeup nothing.
- **One Gemini call.** This module is where a well-meaning refactor ("just re-ask for the shots
  it missed") would break the rule. Don't.
- **PySceneDetect owns the timings.** Gemini's hints are for matching only.
- **Local filesystem only.** Write to `work/`. No GCS, no Firestore.

## Notes

Alignment is the genuinely hard part and deserves its own tests with synthetic inputs — no video
needed. Cases worth covering: exact 1:1 match; model returns fewer segments than shots; model
returns more; model's hints are shifted by a second or two throughout; model returns none at all.

The last case matters more than it looks: if the Gemini call succeeds but returns nothing usable,
the pipeline should still emit a valid index with empty captions rather than fail. A structurally
valid index with no judgment is a legible result; a crash is not.

Stage independence: probe/shots/transcript/gemini don't depend on each other and could run
concurrently. Don't do that in s1 — get the sequential version correct and timed first, then
decide whether the budget even needs it.

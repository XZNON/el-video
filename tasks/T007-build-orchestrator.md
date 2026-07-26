# T007 — `build.py`: orchestrator

**Status:** `done` (2026-07-26) — implemented, 33 tests, every criterion met. The last one, the
<5 min wall-clock, was closed by the first live CLI run once T008 landed: **234.7s end to end on
`in.mp4` with a real Gemini call**, 78% of the 300s budget.

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

- [x] Stage order: probe → shots → transcript → Gemini → quality → join → validate → write.
      `test_stage_order` checks it twice: the order the producers were called in, **and** the
      order of the stage log lines a human reads after a real run.
- [x] **Exactly one Gemini call**, whatever the shot count. Assert the counter from T004 —
      `_assert_one_call()` reads `generate_call_count()` back after the stage and aborts on
      anything but 1. `test_wrong_gemini_call_count_aborts_the_run` covers 0, 2 and 117, and
      asserts nothing is written when it fires.
- [x] `align_understanding()` copies `caption`, `editorial_score`, `moment_reason`, `tags` onto
      the frame-accurate shots and **never touches `t_start` / `t_end`** —
      `test_alignment_never_touches_timings_or_ids` snapshots `(id, t_start, t_end)` across a
      call whose judgments carry deliberately wrong hints.
- [x] Alignment survives a length mismatch: the model returning 40 segments for 120 detected
      shots must not crash, drop shots, or shift the mapping. Unmatched shots keep their
      defaults (`caption=""`, `editorial_score=None`) — tested at 3 judgments for 120 shots,
      and at zero.
- [x] **D-010 is resolved (option 2): alignment is an index lookup on `shot_index`, not an
      overlap match.** A `shot_index` outside the real range fails loudly — it means the model
      ignored the boundaries it was given, and silently dropping it yields captions on the wrong
      shots with no error anywhere. Duplicates raise too, for the same reason.
- [x] Every detected shot appears in the output — **full index, not top-N** (D-001). Checked at
      120 synthetic shots with 2 judgments, and at 117 real ones.
- [x] `is_candidate` is derived from `editorial_score`, with the threshold documented and
      recorded, not a magic number buried in a comparison — `CANDIDATE_THRESHOLD = 0.65`, the
      floor of the rubric's **strong** band, reasoned in **D-023**. A null score is never a
      candidate.
- [x] `transcript` is `words_in_range()` joined; silent shots get `""`, not `None`.
- [x] `index_meta` records what **actually ran** — the real `sample_fps` and `media_resolution`
      used for this run, not the defaults. `path_variant` is `"gemini"`.
      `test_index_meta_records_what_actually_ran` passes non-default values on every axis.
- [x] `index_meta.scene_detector` / `.scene_threshold` carry the values **actually passed to
      `detect_shots()`** (D-013). `threshold` is a keyword-only parameter on `build_index`, and
      the test asserts the same number reached `detect_shots()` and `index_meta`.
- [x] Output validates via `validate_index()` **before** it is written. A validation failure
      leaves no partial file behind — and the write itself goes through a temp file plus
      `os.replace`, so a crash mid-write can't truncate a good index either.
- [x] **Per-stage timing logged** — one line per stage plus a total. All eight stages log their
      own line; the summary line repeats the breakdown alongside the total.
- [x] `embedding` is `null` on every shot.
- [x] Full run on a 10-min video completes in **<5 min wall-clock**. **Measured live 2026-07-26
      via `python -m elvideo index in.mp4`: 234.7s** on `in.mp4` (7:08, 117 shots) — probe 0.05s,
      shots 21.0s, transcript 107.8s, **understand 86.8s (real call: upload 18.7s + call 64.9s,
      38,956 tokens)**, quality 19.0s, join 0.01s, validate 0.06s, write 0.02s. 78% of the 300s
      budget. The earlier 158.5s mocked figure was a floor and is superseded.
      **Caveat worth carrying into the writeup:** `in.mp4` is 7:08, not 10:00. Transcription and
      quality scale with duration, so a true 10-min clip projects to roughly 300-330s — at or
      just over the budget. The criterion says "a 10-min video"; what was measured is a 7-min one.

## Measured on `in.mp4` (2026-07-26, Gemini mocked)

| | |
|---|---|
| Shots | **117**, gapless, `t_start=0.0` → `t_end=428.04` |
| Words | 1436, 7 silent shots of 117 |
| Keyframes | 117 in `work/keyframes/`, names match index ids exactly (D-018) |
| Output | `work/footage_index.json`, 177 KB, passes `validate_index()` |
| `index_meta` | `gemini` / `gemini-3.5-flash` / `low` / `0.5` / `ContentDetector` / `27.0` |
| Wall-clock | **158.5s**, Gemini stage excluded |

Container/stream skew is as D-014 describes: `duration_s` 428.106 vs last `t_end` 428.04.
Captions in that file read `[MOCKED] no live Gemini call was made for shot N` — the artifact
cannot be mistaken for a real Path B index.

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

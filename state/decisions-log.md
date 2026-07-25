# Decisions log

Append-only. Every decision that isn't already settled in `docs/IDEA.md` lands here — especially
anything touching the shared `footage_index.json` contract, since **this repo has no automated
way to know whether Path A changed too.**

Format: id, status, the decision, the reasoning, the date.

---

## D-001 — Output shape: full index vs top-N

**Status:** `unresolved` · **Owner:** needs the co-founder · **Blocks:** T006, T007 · **Resolved in:** T010

Emit every shot with an `is_candidate` flag, or emit a separate top-N "best moments" list?

`docs/IDEA.md` § *Shared contract* assumes **full index + flag**: "best moments" becomes
`filter(is_candidate)` / `sort(editorial_score)`, and both paths stay schema-identical. The
scaffold implements that assumption.

**What resolving it requires:** a yes from the co-founder. This is a 10-minute message, not a
solo call — an assumption confirmed by yourself is still an assumption.

---

## D-002 — Shared vs vendored PySceneDetect + WhisperX

**Status:** `unresolved` · **Owner:** needs the co-founder · **Affects:** T002, T003 · **Resolved in:** T010

One shared module for shot detection and transcription, or each path vendors its own?

`docs/IDEA.md` recommends **shared**, to isolate the experimental variable to Understanding only.
If vendored, shot boundaries and transcripts can differ between paths — and then a caption
difference might be caused by a detector threshold, so the A/B answers nothing.

**What resolving it requires:** agreement plus the *concrete settings* written into both repos —
detector type and threshold (T002); WhisperX model size, compute type, device (T003). "We'll both
use PySceneDetect" is not enough resolution to make the diff clean.

---

## D-003 — The A/B test video

**Status:** `unresolved` · **Owner:** needs the co-founder · **Blocks:** T009 entirely · **Resolved in:** T010

One agreed ~10-min clip both paths run on, checked into the repo or on a shared drive link.

`docs/IDEA.md`: *"Pick it before coding so 'done' is comparable."*

**What resolving it requires:** picking a file. Criteria worth agreeing on: ~10 min;
representative footage (SMB b-roll, not a stock demo reel); has speech, or `words[]` goes
untested; has real cuts, or shot detection goes untested; legally shareable if it lands in a
hackathon writeup.

---

## D-004 — Spec filename is `docs/IDEA.md`, not `docs/idea.md`

**Status:** `resolved` · **Date:** 2026-07-25 · **Scope:** local, no cross-repo impact

The bootstrap prompt refers to `docs/idea.md` throughout; the file on disk is `docs/IDEA.md`
(uppercase). Same file.

**Decision:** keep the on-disk name as authored and reference `docs/IDEA.md` everywhere in
generated docs and docstrings. Windows resolves either case, but a co-founder on macOS/Linux or
a link on GitHub would not — so consistency with the real filename wins over consistency with the
prompt's spelling.

---

## D-005 — `Shot` is one type populated in stages, not two types

**Status:** `resolved` · **Date:** 2026-07-25 · **Scope:** local (Python types only — the emitted JSON is unaffected)

`docs/IDEA.md` § *Module layout* fixes the signature `detect_shots(path) -> [Shot]`, but a `Shot`
in the emitted contract also carries `caption`, `editorial_score`, `quality`, and the rest —
fields PySceneDetect cannot possibly know.

**Options considered:** (a) a separate `ShotBoundary` type that `build.py` promotes to `Shot`, or
(b) one `Shot` with defaults on everything except the timings.

**Decision: (b).** It keeps the signature in `docs/IDEA.md` literally true and keeps a single
type flowing through the pipeline. Cost: a `Shot` mid-pipeline may have an empty caption, so the
staging is documented on the model itself.

**Note the interaction with D-001:** if the answer there turns out to be top-N rather than full
index, revisit this — a top-N list would want the two types separated.

---

## D-006 — Added `elvideo/__main__.py`, not in the bootstrap tree

**Status:** `resolved` · **Date:** 2026-07-25 · **Scope:** local

The bootstrap directory listing doesn't include `elvideo/__main__.py`, but the Definition of Done
requires `python -m elvideo index in.mp4`, which Python cannot resolve without it.

**Decision:** added, as a two-line delegation to `elvideo.cli.main`. Deviation from the specified
tree, in service of a stated DoD criterion.

---

## D-007 — `scenedetect[opencv]` extra doesn't exist

**Status:** `resolved` · **Date:** 2026-07-25 · **Scope:** local

The bootstrap prompt specifies `scenedetect[opencv]`. `uv` warned: *"The package
`scenedetect==0.7.1` does not have an extra named `opencv`"* — in 0.7.x, OpenCV is a core
dependency rather than an extra.

**Decision:** depend on plain `scenedetect`, with `opencv-python` listed explicitly (T005 needs
it directly anyway). No functional difference; avoids a dead extra in `pyproject.toml`.

---

## D-008 — Deps locked but not installed at scaffold time

**Status:** `resolved` · **Date:** 2026-07-25 · **Scope:** local · **Recorded as a blocker in `progress.json`**

All deps were added with `uv add --no-sync`: resolved and written to `uv.lock`, but not
downloaded. `whisperx` pulls torch, which is a multi-GB download that would have dominated a
scaffolding session that runs no code.

**Consequence:** `uv run pytest` will not work until someone runs `uv sync`. The next session
should do that first. The resolution itself is verified — 151 packages, no conflicts on
Python 3.11–3.12.

---

## D-009 — Two schema artifacts kept in lockstep, deliberately redundant

**Status:** `resolved` · **Date:** 2026-07-25 · **Scope:** contract-adjacent — see T006

Pydantic can generate JSON Schema, so maintaining `footage_index.schema.json` by hand is
redundant.

**Decision:** keep both anyway. Pydantic's generated schema is verbose, uses `$defs` indirection,
and its shape shifts between pydantic versions — which makes it useless for a clean `diff`
against Path A's output. The hand-written schema is the interoperability artifact;
`tests/test_schema.py` asserts field-name parity so the redundancy can't silently drift.

---

## D-010 — Does `understand()` see the shot list? (open design question)

**Status:** `unresolved` · **Owner:** whoever does T004 · **Affects:** T004, T007

`docs/IDEA.md` fixes `understand(path, fps, res) -> [ShotUnderstanding]` — no shot list
parameter. So Gemini segments the video its own way, and `build.py` must align two lists that may
differ in length, using second-granular hints.

**Option 1:** keep it. Alignment by temporal overlap. Preserves the Path A seam exactly.
**Option 2:** pass the PySceneDetect boundaries into the *prompt text* (not the signature). The
model describes our shots by index; alignment becomes trivial and captions get sharper. Costs
almost nothing in tokens and doesn't change the signature — but couples the module to T002's
output.

**Leaning: option 2.** Decide it deliberately during T004 and record the outcome here rather than
letting the implementation settle it by accident.

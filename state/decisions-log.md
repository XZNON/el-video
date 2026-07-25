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

**Status:** `resolved` · **Date:** 2026-07-25 · **Unblocks:** T009

One clip, agreed with the co-founder, both paths run on it. Sits at repo root as `in.mp4` and is
gitignored (`*.mp4`) — it is **not** distributed via this repo, both sides hold the same file.

Measured on this machine, so "done" is comparable:

| | |
|---|---|
| Duration | 428.11s (7:08) |
| Video | h264, 1280×720, 25 fps, 10,701 frames |
| Audio | AAC stereo, 44.1 kHz — present, so `words[]` gets exercised |
| Size | 48 MB |
| Shots | **117** at `ContentDetector(threshold=27.0)` — see D-012 |

Satisfies every criterion in `docs/IDEA.md` § *Open decisions*: under 10 min, has speech, has
real cuts, dense enough to be non-trivial (117 is inside the spec's 100–300 band).

**Deviation from the assumed footage:** 1280×720 landscape, not the vertical 1080×1920 the spec
sketches for SMB b-roll. Irrelevant to the pipeline — no code branches on orientation — but worth
knowing when reading the A/B writeup.

**Budget implications, recomputed for 7:08 rather than 10:00:** 214 sampled frames at 0.5 fps ×
66 tok ≈ **~14K visual tokens**, roughly half the 30K target. Room to raise `--fps` to 1.0 if 0.5
proves too coarse for this footage.

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

## D-011 — mypy checks against 3.12, not the 3.11 floor

**Status:** `resolved` · **Date:** 2026-07-25 · **Scope:** local (tooling config only)

`uv sync` installed numpy 2.5.1, whose bundled stubs use PEP 695 `type` statements. mypy refuses
to parse those below 3.12: `numpy/__init__.pyi:737: error: Type statement is only supported in
Python 3.12 and greater [syntax]`, and it is fatal — *"errors prevented further checking"*.
Neither `ignore_missing_imports` nor `follow_imports = "skip"` suppresses it, because the failure
happens at parse time, before per-module rules apply.

`quality.py` imports numpy under `TYPE_CHECKING` for `score_frame(img: np.ndarray)`, so the stub
gets pulled in.

**Decision:** set `[tool.mypy] python_version = "3.12"`.

**What this costs:** mypy no longer catches 3.12-only syntax leaking into our own code, while
`requires-python` still claims `>=3.11`. `ruff`'s `target-version = "py311"` remains the guard
for that. Runtime 3.11 support is unaffected — this is purely a stub-parsing gate.

**Revisit if:** the project is ever actually run on 3.11 in anger, or numpy's stubs stop needing
it. Pinning numpy below 2.5 would be the alternative, and is not worth it.

---

## D-012 — Shot detector settings: `ContentDetector(threshold=27.0)`

**Status:** `resolved` for this repo · **Date:** 2026-07-25 · **Feeds:** T002 · **Cross-repo:** must be matched by Path A (D-002)

Measured on `in.mp4` with a throwaway script — **not** T002's implementation, which still has to
be written:

| | |
|---|---|
| Detector | `ContentDetector` |
| Threshold | **27.0** (PySceneDetect's own default) |
| Result | 117 shots over 428.04s, gapless |
| Distribution | median 2.68s · mean 3.66s · shortest 0.64s · longest 23.84s |
| Sub-1s shots | 4 |
| Detect wall-clock | 20.8s |

**Decision:** adopt `ContentDetector(threshold=27.0)` as the default, and treat the threshold the
same way `docs/IDEA.md` treats `fps` — a **per-video CLI knob**, never edited globally to fix one
clip.

**What the threshold actually does,** so nobody tunes it blind: `ContentDetector` compares HSV
content between adjacent frames and calls a cut past the delta. Lower (~20) is more sensitive and
starts splitting *within* a shot on fast pans, flashes, or someone crossing frame; higher (~35)
misses real cuts in dark or low-contrast footage.

**Known blind spot, independent of the value:** it detects **hard cuts**. Crossfades and
dissolves are gradual and get missed. Footage cut with transitions needs `AdaptiveDetector` — a
detector change, not a threshold change. Not an issue on the current test clip.

**Cross-repo:** Path A must use the identical detector *and* threshold, or shot boundaries differ
and a caption difference in the A/B could just be a dial difference. See D-002.

---

## D-013 — `index_meta` does not record how the shots were cut

**Status:** `unresolved` · **Affects:** T006, T007 · **Cross-repo:** schema change, needs the co-founder

`index_meta` currently captures `path_variant`, `model`, `media_resolution`, `sample_fps` — every
setting that changes the *understanding* output. It captures **nothing** about shot detection.

So two `footage_index.json` files can disagree on shot count, and neither file explains why.
Since shot boundaries are the spine the whole index hangs off, that is a bigger provenance hole
than any of the fields currently recorded. It surfaced while measuring D-012: 27.0 produced 117
shots, and nothing in the emitted document would say so.

**Proposal:** add `scene_detector` (string) and `scene_threshold` (number) to `index_meta`.

**Cost:** `index_meta` is the shared contract, so this is a two-repo change with no automated
sync — exactly the risk `docs/IDEA.md` flags. It also touches both schema artifacts
(`models.py` + `footage_index.schema.json`) and `tests/test_schema.py`.

**Argument for doing it anyway:** the contract's job is to make two indexes comparable. Right now
it records the easy half.

**Argument against:** every field added is another thing both repos must agree on, and the values
could equally live in the session log rather than the artifact.

**Resolve during T006**, alongside D-001, before the schema is locked.

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

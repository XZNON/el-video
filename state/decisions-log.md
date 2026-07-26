# Decisions log

Append-only. Every decision that isn't already settled in `docs/IDEA.md` lands here — especially
anything touching the shared `footage_index.json` contract, since **this repo has no automated
way to know whether Path A changed too.**

Format: id, status, the decision, the reasoning, the date.

---

## D-001 — Output shape: full index vs top-N

**Status:** `resolved` — **full index + `is_candidate` flag** · **Date:** 2026-07-26 · **Unblocks:** T006, T007

Emit every shot with an `is_candidate` flag, or emit a separate top-N "best moments" list?

`docs/IDEA.md` § *Shared contract* assumes **full index + flag**: "best moments" becomes
`filter(is_candidate)` / `sort(editorial_score)`, and both paths stay schema-identical. The
scaffold implements that assumption.

**Decision: keep the full index.** Owner-locked rather than co-founder-confirmed — see **D-016**;
there is no second repo to get a yes from.

**Why it stands on its own merits, independent of who signs it off:** a top-N list throws away
data the index was built to hold. Every downstream question — "what else was in this scene",
"give me a B-roll cutaway near 4:10", "why was this rejected" — needs the shots that *didn't*
make the cut. "Best moments" is a view over the index, not a different artifact, and a view costs
nothing to compute. Going top-N would also reopen D-005 (the single staged `Shot` type).

**Revisit if:** output size becomes a real problem. It won't at 117 shots.

---

## D-002 — Shared vs vendored PySceneDetect + WhisperX

**Status:** `resolved` — **vendored in practice, settings pinned and published** · **Date:** 2026-07-26 · **Affects:** T002, T003

One shared module for shot detection and transcription, or each path vendors its own?

`docs/IDEA.md` recommends **shared**, to isolate the experimental variable to Understanding only.
If vendored, shot boundaries and transcripts can differ between paths — and then a caption
difference might be caused by a detector threshold, so the A/B answers nothing.

**Decision:** the question as posed is moot — there is no second repo to share *with* (**D-016**).
This repo vendors both stages, and what survives of the requirement is the half that actually
does the work: **the concrete settings are pinned in code, exposed as module constants, and
guarded by tests.**

| Stage | Pinned in | Settings |
|---|---|---|
| Shot detection | `elvideo/index/scenes.py` | `ContentDetector`, threshold `27.0` (**D-012**) |
| Transcription | `elvideo/index/transcribe.py` | `base` / `int8` / `cpu` / `en` (**D-015**) |

From T007 the detector settings also land *in the artifact itself* via `index_meta`
(**D-013**), so a `footage_index.json` explains its own shot count without reference to this log.

**If Path A ever becomes real:** this is the entry it has to match. Nothing here changes; the
requirement just gains a counterparty.

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

**Status:** `resolved` — **shipped** · **Date:** 2026-07-26 · **Affects:** T006, T007

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

**Decision: add both fields.** `scene_detector: str` and `scene_threshold: float`, required, no
defaults — `index_meta` records what *ran*, not what the constants say. The argument against was
mostly cross-repo agreement cost, and D-016 removes that. The session-log alternative fails the
actual use case: the artifact has to be readable on its own, by a downstream agent that never
sees this repo.

**Landed in all four places, in lockstep:**

- `elvideo/schema/models.py` — `IndexMeta.scene_detector` / `.scene_threshold`
- `elvideo/schema/footage_index.schema.json` — same two, both in `required`
- `tests/test_schema.py` — `test_index_meta_records_how_shots_were_cut`, plus `index_meta` added
  to the field-parity parametrize, which had been **missing** the block entirely (so a one-sided
  edit to `index_meta` would not have been caught before now)
- **T007 must populate them** from `scenes.DEFAULT_DETECTOR` / the threshold actually passed —
  the schema now rejects an index without them.

---

## D-014 — Container duration ≠ video-stream duration on the test clip

**Status:** `resolved` (observation recorded) · **Date:** 2026-07-25 · **Affects:** T007 validation

Measured while landing T001+T002 on `in.mp4`:

- `probe().duration_s` = **428.106304** — ffprobe *format* (container) duration, which includes
  the audio stream's tail.
- `detect_shots()` final `t_end` = **428.04** — video stream length, 10,701 frames ÷ 25 fps.

Gap: **0.066s**, more than one frame (0.04s at 25 fps). Both numbers are correct for what they
measure; the audio track simply outlives the last video frame.

**Consequence:** T002's "final `t_end` equals the video duration within one frame" criterion holds
against the **video stream** duration and cannot hold against `video.duration_s` on this clip.
T007's assembly/validation must not assert `shots[-1].t_end == video.duration_s` to frame
precision — tolerance needs to cover container/stream skew (~0.1s), or compare against frame
count × fps instead. `words[]` may also legitimately end after the last shot's `t_end`.

---

## D-015 — WhisperX settings: `base` / `int8` / `cpu` / `en`

**Status:** `resolved` for this repo · **Date:** 2026-07-26 · **Feeds:** T003 · **Cross-repo:** must be matched by Path A (D-002)

D-002 says "we'll both use WhisperX" is not enough resolution. These are the concrete settings,
now encoded as module constants in `elvideo/index/transcribe.py` and guarded by a test:

| | |
|---|---|
| Model size | **base** |
| Compute type | **int8** on CPU (`float16` if a CUDA box is ever used) |
| Language | **en**, pinned — not auto-detected |
| Device | **cpu** — torch here is `2.8.0+cpu`, `torch.cuda.is_available()` is `False` |
| Batch size | 16 (throughput only, does not change output) |
| Alignment model | torchaudio `WAV2VEC2_ASR_BASE_960H`, WhisperX's default for `en` |

Measured on `in.mp4` (428s, D-003), second run with all models cached:

| | |
|---|---|
| Words | **1436** |
| Wall-clock | **102.7s** — ASR 49.5s + alignment 53.2s |
| First / last word | `t=0.928` / `t=427.017` |
| Mean word duration | 0.18s (max 2.02s) — word-level, not segment spans |
| Dropped by `words_in_range` across all 117 shots | **0** |
| Silent shots | 7 of 117 |

**Why `base` and not `small`:** transcription plus the one Gemini call is the entire <5 min
budget. At 103s, `base` spends about a third of it; `small` is roughly 2–3× slower on CPU and
would leave no room. Revisit if a CUDA machine becomes the reference.

**Why language is pinned rather than detected:** detection is a per-run guess, and a flip would
silently swap the alignment model too — the two repos could then disagree for a reason nothing
in the artifact records.

**Cold-start caveat, not part of the budget:** the *first* run took 202.5s because it downloads
the 360 MB wav2vec2 alignment checkpoint. Cached thereafter in `~/.cache/torch/hub`. Path A's
first run pays the same toll; do not compare a cold number against a warm one.

**Known environment noise:** `pyannote.audio` warns that `torchcodec` can't load its DLLs on this
box. Harmless here — WhisperX decodes audio through ffmpeg, not torchcodec — but it prints a wall
of text on every run.

---

## D-010 — Does `understand()` see the shot list?

**Status:** `resolved` — **option 2, boundaries in the prompt text** · **Date:** 2026-07-26 · **Affects:** T004, T007

`docs/IDEA.md` fixes `understand(path, fps, res) -> [ShotUnderstanding]` — no shot list
parameter. So Gemini segments the video its own way, and `build.py` must align two lists that may
differ in length, using second-granular hints.

**Option 1:** keep it. Alignment by temporal overlap. Preserves the Path A seam exactly.
**Option 2:** pass the PySceneDetect boundaries into the *prompt text* (not the signature). The
model describes our shots by index; alignment becomes trivial and captions get sharper. Costs
almost nothing in tokens and doesn't change the signature — but couples the module to T002's
output.

**Decision: option 2.**

**Why:** option 1's alignment is a fuzzy match between a 117-entry frame-accurate list and
whatever Gemini decides the shots were, using timestamps the constraints already declare
untrustworthy (second-granular, never used for `t_start`/`t_end`). That is a silent-failure
surface in the middle of the pipeline: a mis-alignment yields a plausible-looking index with
captions attached to the wrong shots, and nothing errors. Option 2 deletes the problem — the
model returns `shot_index`, and `ShotUnderstanding.shot_index` already exists for exactly that.

**Cost, accepted:** ~117 lines of `idx t_start-t_end` in the prompt, well under 2K tokens against
a ~14K-token budget for this clip (D-003). Couples `gemini.py` to T002's output — but T007
already couples them, so the dependency is real either way.

**How it's threaded without changing the signature:** the boundaries reach `understand()` as an
optional keyword argument with a `None` default, the same pattern `detect_shots(path, threshold=)`
uses (D-012). `understand(path, fps, media_resolution)` stays literally callable as
`docs/IDEA.md` writes it.

**T007 consequence:** `align_understanding()` becomes an index lookup with a length check, not an
overlap matcher. It must still fail loudly — a returned `shot_index` outside the real range is an
error, not something to silently drop.

---

## D-016 — There is no Path A counterparty; contract decisions are owner-locked

**Status:** `resolved` · **Date:** 2026-07-26 · **Scope:** governance — supersedes the "needs the co-founder" status on D-001, D-002, D-013

Stated by the repo owner on 2026-07-26: **this is a solo repo.** There is no separate El-Video /
Path A repo with a second person coding against `footage_index.json` today.

Three decisions were parked as `unresolved · needs the co-founder`, and T010 was written as *"a
10-minute message, not a solo call."* With no counterparty, waiting is not caution — it is a
permanent block. The decisions are now made by the owner, on their merits, and logged with
reasoning: D-001, D-002, D-013 above, and D-010 (never a cross-repo question) alongside them.

**What this does NOT change:**

- **The schema stays the shared contract in shape.** `path_variant: "gemini" | "local"` and the
  nullable `editorial_score` / `moment_reason` stay exactly as they are. They cost nothing and
  they are what makes a Path A possible later. Designing the A/B out of the schema now would be
  a one-way door.
- **Settings stay pinned and published** (D-012, D-015). Reproducibility was always the real
  requirement; a second reader was only ever the motivation.
- **Changes still get logged here.** The discipline is worth keeping on its own.

**What it does change:** `.claude/CLAUDE.md` hard constraint 6 and `docs/IDEA.md` both describe
the co-founder repo as a live counterparty and a manual-sync risk. That framing is now
aspirational rather than current. Flagged here rather than silently edited, per CLAUDE.md's own
instruction to log conflicts instead of picking one. **The owner should decide whether to soften
constraint 6 or leave it as the intended future state.**

**Reversal condition:** if a Path A repo does appear, D-001 / D-002 / D-013 become proposals
again and must be re-confirmed against what it actually emits. The A/B claim in the writeup
depends on that, and nothing in this repo can detect it automatically.

---

## D-017 — Quality formula and its normalization constants

**Status:** `resolved` for this repo · **Date:** 2026-07-26 · **Feeds:** T005 · **Cross-repo:** must be matched by Path A (D-002)

`docs/IDEA.md` says only *"OpenCV Laplacian + exposure, deterministic"*. These are the concrete
numbers behind that phrase, now module constants in `elvideo/index/quality.py` and guarded by
`tests/test_quality.py::test_constants_are_recorded`:

```
sharpness = min(sqrt(laplacian_variance / 1000.0), 1.0)
brightness_term = max(1 - |mean_luma/255 - 0.5| / 0.5, 0)
clipping_term   = max(1 - clipped_fraction / 0.5, 0)      # clipped = px <= 8 or px >= 247
quality = round(0.7 * sharpness + 0.3 * brightness_term * clipping_term, 4)
```

| Constant | Value | Why |
|---|---|---|
| `SHARPNESS_SATURATION` | 1000.0 | Variance treated as fully sharp — Laplacian std ≈ 31.6 gray levels |
| `W_SHARPNESS` / `W_EXPOSURE` | 0.7 / 0.3 | Focus is unrecoverable; exposure is gradeable |
| `EXPOSURE_TARGET` | 0.5 | Mid-gray; penalized linearly in both directions |
| `CLIP_LOW` / `CLIP_HIGH` | 8 / 247 | 8-bit levels past which no detail is recoverable |
| `CLIP_SATURATION` | 0.5 | Half the frame clipped scores 0 on that term |
| `SAMPLE_POSITION` | 0.5 | Midpoint of `[t_start, t_end)`, fixed |
| `ROUND_DIGITS` | 4 | Coarser than cross-machine SIMD float noise |
| `KEYFRAME_PNG_COMPRESSION` | 3 | Same frame, same PNG bytes; does not touch the score |

**Why `sqrt`, not raw variance.** Laplacian variance is quadratic in contrast — doubling edge
contrast quadruples it — so a linear normalization either crushes everything toward 0 or pins
the top quartile at exactly 1.0. Its square root is the Laplacian *standard deviation*, in gray
levels, linear in contrast. Measured on the 117 keyframes of `in.mp4`:

| Normalization | mean | p10 | p50 | p90 | at ceiling |
|---|---|---|---|---|---|
| linear, sat 300 | 0.576 | 0.095 | 0.564 | 1.000 | **26/117** |
| linear, sat 1000 | 0.219 | 0.029 | 0.169 | 0.503 | 0/117 |
| **sqrt, sat 1000** | **0.425** | **0.169** | **0.411** | **0.709** | **0/117** |

**Why saturation is 1000 and not the clip's own maximum.** Raw variance on `in.mp4` spans
1.7–832.7 (median 169.2), so the sharpest real frame lands at 0.91 with headroom left. Pinning
the constant to this clip's maximum would make the metric stop discriminating on better footage —
a crisper camera has to be able to outscore the test clip.

**Measured distribution of the final score, all 117 shots of `in.mp4`:**

| | |
|---|---|
| Stage wall-clock | **18.8s** for 117 shots (0.161s/shot), including PNG keyframe writes |
| min / p25 / median / p75 / max | 0.061 / 0.355 / 0.480 / 0.555 / 0.857 |
| mean / stdev | 0.465 / 0.169 |
| Distinct values at 2 decimals | 55 of 117 |
| Frames at the 1.0 ceiling | 0 |

That spread is the point of the measurement: a metric that returned ~0.8 for everything would be
as broken as a model that scores everything 0.8. Asserted, not just eyeballed —
`test_real_video_scores_spread` fails if the range collapses below 0.3 or distinct 2-dp values
drop below 20.

**Known limitation, inherited equally by both paths:** Laplacian variance is content-dependent. A
plain wall, fog, or a dark night shot scores like a blurred frame because it genuinely carries no
edge energy. That is the metric, not a bug — but it belongs in the A/B writeup, because a caption
difference between paths must not be blamed on a `quality` field that both paths compute
identically.

**Speed note, not a blocker:** `score_shot()` opens its own `VideoCapture` per call, which costs
~0.1s of the 0.161s per shot; a shared capture across shots measured 0.045s/shot (5.3s total).
18.8s is 6% of the 300s budget, so the simpler signature wins for now. Worth a `/new-task` only
if the budget tightens.

---

## D-018 — `score_shot()` takes an optional `shot_id`, so keyframes match index ids

**Status:** `resolved` · **Date:** 2026-07-26 · **Scope:** local · **Feeds:** T005, T007

`docs/IDEA.md` § *Storage & speed* wants keyframes at `work/keyframes/shot_###.png`, but the
signature it fixes — `score_shot(path, t_start, t_end, work_dir)` — **is never given the shot id**.
Left alone, the filename scheme would have emerged by accident.

**Decision:** `shot_id: str | None = None` as a keyword-only argument — the same
extend-a-fixed-signature pattern as `detect_shots(path, threshold=)` (D-012) and `understand()`'s
boundaries kwarg (D-010). The positional call in `docs/IDEA.md` stays literally valid.

**Fallback when omitted:** `shot_at_{sampled_ms:08d}ms.png`. Derived from the sampled timestamp,
so it is unique per shot and two shots cannot overwrite each other — which a naive counter or a
fixed name would.

**T007 consequence:** `build.py` must pass `shot_id=shot.id`, or the keyframes on disk stop
matching the ids in `footage_index.json` and the folder becomes unusable for debugging.

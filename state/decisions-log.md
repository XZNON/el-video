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

---

## D-019 — Gemini call settings and the prompt version

**Status:** `resolved` for this repo · **Date:** 2026-07-26 · **Feeds:** T004 · **Verified live 2026-07-26 — D-021 cleared; prompt is now `p2`, see D-024**

`docs/IDEA.md` § *Gemini call settings (locked)* fixes the model, `media_resolution`, `fps`,
structured output, and backoff. It says nothing about the sampling parameters, which change the
output just as much. Pinned as module constants in `elvideo/index/gemini.py`, guarded by
`tests/test_gemini.py::test_settings_are_recorded`, in the same house style as D-012 / D-015 / D-017:

| Constant | Value | Why |
|---|---|---|
| `MODEL` | `gemini-3.5-flash` | From the spec. Not parameterized. |
| `DEFAULT_MEDIA_RESOLUTION` | `low` | 66 tok/frame, not 258. From the spec. |
| `DEFAULT_SAMPLE_FPS` | 0.5 | From the spec. Per-video knob, overridable per call. |
| `TEMPERATURE` | **0.4** | New. See below. |
| `SEED` | **7** | New. Removes run-to-run jitter as an A/B variable. Best-effort — the API does not promise identical output across model revisions. |
| `THINKING_LEVEL` | **LOW** | New. See below. |
| `RETRY_MAX_ATTEMPTS` / wait | **5** / 4s → 60s | Bounded. Free tier is 10 RPM, so a single video that keeps tripping the cap is a key problem, not a timing problem. |
| `UPLOAD_TIMEOUT_S` | 300 | Server-side File API processing, not the transfer. |
| `PROMPT_VERSION` | **`p1`** | See below. |

**Why temperature 0.4 and not 0.0.** The task's own failure mode — "a model that scores everything
0.8 is a prompt bug" — is exactly what near-greedy decoding encourages: it collapses toward a few
round numbers. But 1.0 makes the understanding stage non-repeatable, and the A/B needs to be able
to re-run it. 0.4 is the compromise, and it is falsifiable rather than a matter of taste: every run
logs the score spread and warns below stdev 0.05, and the slow test fails if the range collapses.

**Why thinking level LOW.** Per-shot judgment against an explicit rubric, not a reasoning puzzle.
High thinking spends the free-tier budget on tokens that never reach the index and adds minutes to
a <5 min wall-clock target. `thoughts_token_count` is logged separately so this is re-litigable
with a number.

**Why a `PROMPT_VERSION` constant.** The prompt is the part of this module that gets iterated on,
and `index_meta` has no field for it (adding one is a contract change — D-013's cost applies). The
constant plus the per-call log line is the record, and the A/B writeup quotes it.

**Prompt shape.** Two constants: `SYSTEM_INSTRUCTION` carries the rubric — five scoring bands
(0.85+ hero … below 0.15 unusable), scores calibrated *within this video*, an explicit instruction
that a run of identical scores is a failure of the task, `moment_reason` as the evidence for the
score in ≤15 words and never a restatement of the caption, and a reminder to use the audio (this
stage is the only one that sees picture and sound together). The user half is either the numbered
boundary list (D-010) or the free-segmentation instruction.

**Response schema is not `ShotUnderstanding`.** Two wire models, `_Judgment` and
`_JudgmentWithHints`, converted after validation. `ShotUnderstanding` has optional hint fields —
nullable branches in a generated schema — and forbids extras, which is a constraint on our side of
the wire, not the model's. Splitting them also lets the hints be **dropped from the schema entirely
when boundaries are supplied**: echoing 117 pairs of numbers we already know is output tokens spent
on nothing.

---

## D-020 — 429 backoff wraps the File API upload too, not only `generate_content`

**Status:** `resolved` · **Date:** 2026-07-26 · **Scope:** local · **Feeds:** T004

T004's criterion says "exponential backoff on HTTP 429", and the natural reading is the
`generate_content` call — that is the request the rate limit is about.

**Found by running it:** with a key whose quota is gone, the 429 arrives at
`client.files.upload()`, before any generation happens. Unwrapped, that surfaces as a raw
`google.genai.errors.ClientError` traceback out of the SDK — no retry, and none of the actionable
text the unset-key path gets.

**Decision:** both API-touching steps go through one `_with_backoff()` helper. The upload is
genuinely retryable (a transient per-minute cap clears), and the failure message now names which
step failed and quotes the server's own text.

**Not counted as a call.** `generate_call_count()` still counts `generate_content` requests only —
it is the instrument behind the *one call per video* rule, and folding uploads into it would make
that number mean nothing. A 429 retry of the generate call *does* increment it, deliberately:
hidden retries would defeat the instrument.

---

## D-021 — The `GEMINI_API_KEY` has no quota; T004 is code-complete but unverified

**Status:** **`resolved` 2026-07-26** — the owner supplied a free-tier key and the live run passed.
Kept in full below because the diagnosis is the reusable part: if this recurs, it is the *project's
billing mode*, not the code. · **Was blocking:** T004 sign-off, T009 — both now clear.

Every request on the key in `.env` returns:

```
429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Your prepayment credits are depleted.
Please go to AI Studio at https://ai.studio/projects to manage your project and billing.'}}
```

**Isolated, not assumed:** a 5-token text-only `generate_content` on `gemini-3.5-flash` fails the
same way, so it is not the video, not the file size, not the request shape, and not a transient
per-minute cap. Retrying cannot fix it — the message is about credits, not rate. An earlier run
with a *stale* key failed differently (`400 API_KEY_INVALID`), which confirms the key in `.env` is
now being read and accepted; it is the project behind it that has nothing left.

**What this repo assumed:** `docs/IDEA.md` says "free tier, zero credits" throughout. This key's
project is on **prepay billing**, which is a different quota pool — a prepay project with a zero
balance does not fall back to the free tier.

**Owner action:** create an API key in an AI Studio project **without billing enabled** (the free
tier), put it in `.env`, and run:

```
uv run pytest tests/test_gemini.py -m slow --log-cli-level=INFO
```

That single command settles every unverified criterion in T004 and produces the token number the
~30K target is supposed to be checked against.

**What is unverified until then** (all four are marked `[~]` in the task file, not ticked):
real token usage; whether `editorial_score` actually spreads under prompt `p1`; whether
`moment_reason` reads as evidence rather than a second caption; and whether the free-segmentation
(`shots=None`) path behaves against the real model. The instrumentation for all of them is in
place and asserted against mocks — what is missing is one call.

**Deliberately not worked around.** Switching model, provider, or tier would break the pinned
`gemini-3.5-flash` constraint and make the A/B measure something else.

**Resolution (2026-07-26):** new key, first live run passed —
`gemini generate_content request #1 model=gemini-3.5-flash fps=0.5 media_resolution=low prompt=p1`,
117 shots, one call, upload deleted. The four unverified criteria are settled in **D-024**
(score spread, `moment_reason` quality) and **D-025** (token budget). The free-segmentation
`shots=None` path is still only unit-tested live-wise — it costs a second call on the same clip and
was judged not worth the quota while the boundary path is the one every task uses.

---

## D-024 — Prompt iterated `p1` → `p2` after the first live run clustered

**Status:** `resolved` · **Date:** 2026-07-26 · **Feeds:** T004 · **Supersedes the `p1` half of D-019**

The first real run technically passed, and that was the problem. Measured on `in.mp4`, 117 shots,
identical settings, prompt the only variable:

| | p1 | p2 |
|---|---|---|
| Distinct scores at 2dp | **11** | **37** |
| Scores landing on the 0.05 grid | **117/117** | **32/117** |
| Range (min–max) | 0.10–0.75 | 0.10–0.85 |
| Median | 0.60 | 0.61 |
| Hero band (≥0.85) used | **never** | yes |

`p1` produced 97 of 117 shots inside 0.50–0.65, every score a multiple of 0.05, and a ceiling of
0.75 — the model quietly refused the top band on ordinary footage and picked from about a dozen
round numbers. That is the "everything is 0.8" failure the task names, in a form that slips past a
naive check: the scores *are* different, they are just not judgments.

**What `p2` changes** (rubric bands unchanged — the fix is procedural, not a new scale):

1. **Rank, then score.** Pick the few shots you would build the edit around and the few you would
   never use *first*, let those anchor the ends, then place everything else between. Scoring shot
   by shot in isolation is what produces a video where every shot is a 0.6.
2. **The top band is not withheld for ordinary footage.** "Whatever the strongest moment here is,
   it IS the strongest moment here."
3. **Two decimals, and use the digits** — 0.58 and 0.63 are different judgments; 0.60 for both is
   a refusal to choose. No score shared by more than ~10 shots.
4. **A category label is not evidence.** "Standard b-roll" / "connective tissue" / "establishing
   shot" say nothing a reader could disagree with. "Third exterior pan of the same car" is
   evidence; "standard exterior b-roll" is not.

**Caption quality was never the problem** — `p1`'s captions were already specific and correct
("presenter holding a tablet showing a tiger, explaining the name Tiguan"). Only the scoring and
the reasons needed the work.

**Run-to-run variance is real and `seed` does not remove it.** Three `p2` runs of the same clip
gave min-scores of 0.10, 0.50, 0.50 and distinct counts of 37, ?, 26 — the model's willingness to
call the outro frames unusable moves between runs. This is why the slow test asserts **granularity**
(distinct ≥ 15, fewer than 90% on the 0.05 grid) as the primary anti-clustering guard and keeps the
range threshold at a loose 0.3: `p1` fails the granularity assertions on every run, which is what a
regression guard has to do.

**Not fixed by `p2`, accepted:** a handful of `moment_reason` values still open with a category
label ("Standard b-roll showing the exterior profile") — 4 of 117, versus 3 under `p1`. Below the
threshold where another prompt round is worth a quota call; revisit if a downstream consumer
actually trips on it.

---

## D-025 — Real token cost is ~38K, not the ~30K the spec targets

**Status:** `resolved` — **measured, target restated** · **Date:** 2026-07-26 · **Affects:** T004, T009, the A/B writeup

`docs/IDEA.md` § *Gemini call settings* budgets **≈30K tokens per 10-min video**, and D-003
recomputed that as ~14K for this 7:08 clip: 214 frames at 0.5 fps × 66 tok/frame at `low`.

**Measured, three runs on `in.mp4` (7:08):**

| | |
|---|---|
| Prompt tokens | **27,404 / 27,693 / 27,693** |
| Output tokens | 11,280 / 11,481 / 10,697 |
| **Total** | **38,684 / 39,174 / 38,390** |
| Wall-clock | 103.0s / 108.8s / 96.8s (upload ~25s, call ~70s) |

**Why D-003's estimate was low: it counted video frames and forgot the audio.** Gemini tokenizes
the soundtrack as well as the sampled frames, and audio is charged per second of duration
regardless of `fps` or `media_resolution` — the two knobs the spec offers only move the visual
half. Roughly: ~14K visual + ~12K audio + ~2K for the 117-line boundary list and the rubric.

**Consequences, none of them blocking:**

- A **10-min** clip should land near **~54K total**, not 30K. Still far under the 250K/min TPM cap,
  so the "iterate freely all day" claim in the spec survives intact — it is the stated *number*
  that was wrong, not the conclusion.
- Output tokens (~11K) are a third of the bill and scale with **shot count**, not duration. A
  300-shot video costs meaningfully more to describe than a 100-shot one of the same length.
- `thoughts_token_count` comes back `None` despite `THINKING_LEVEL=LOW`, so thinking is either not
  billed separately here or not reported. Logged either way; do not silently assume it is zero.

**Not treated as a regression.** Nothing was tuned to chase 30K: lowering `fps` would only touch
the visual half, and raising the target to match reality is more honest than trimming the input
until an estimate that omitted audio comes true. **T009 should assert against ~40K for this clip,
not 30K**, and the A/B writeup should quote the measured number with the audio breakdown.

---

## D-022 — `t_end > t_start` is enforced in `validate_index()`, not in the JSON Schema

**Status:** `resolved` · **Date:** 2026-07-26 · **Feeds:** T006, T007 · **Contract-adjacent — read this before diffing the schema against another repo**

T006's acceptance criteria require that *"a document with `t_end < t_start` fails"*. **JSON Schema
draft 2020-12 cannot express it.** There is no way to compare two sibling properties of the same
object; `exclusiveMinimum` takes a constant, not a reference to another field. So a document with
a backwards or zero-length shot validates cleanly against `footage_index.schema.json`.

**Decision:** `validate_index()` runs two checks in order — the JSON Schema first, then
`_check_shot_timings()` in Python — and raises the same `jsonschema.ValidationError` type from
both, with `path = ["shots", i, "t_end"]`, so callers cannot tell which half rejected the
document.

**The cost, stated plainly:** the two artifacts are no longer equivalent. Anyone validating
`footage_index.json` with a generic JSON Schema tool (`ajv`, `check-jsonschema`, a Path A repo in
another language) gets a **weaker** check than `validate_index()` does. That is the exact
asymmetry D-009 exists to prevent, so it is written down here rather than left to be discovered.

**Why not drop the criterion instead:** the invariant is real. `Shot` already enforces it as a
pydantic `model_validator`, and PySceneDetect cannot emit a backwards shot — but the whole point
of validating a plain dict is to catch a document that *never went through pydantic*: one read
back off disk, hand-edited, or produced by Path A.

**Pinned by a test that fails if the situation changes.**
`test_schema_alone_does_not_catch_backwards_timings` asserts that raw `jsonschema` *accepts* the
backwards document. If a future dialect or a schema rewrite ever makes the constraint expressible,
that test goes red — which is the only way anyone would notice that the Python half is now
redundant.

**Also landed here:** `validate_index()` prefixes every error message with its JSON path
(`$.shots[42].editorial_score: 1.5 is greater than the maximum of 1`) and reports the
document-order-first error plus a total count. At 117 shots, `ValidationError.message` alone
("1.5 is greater than the maximum of 1") does not say which shot.

**Tooling note:** `jsonschema` ships no inline types, so `types-jsonschema` was added as a dev
dependency to keep `mypy --strict` clean. Stub-only package, matched to the runtime version
(4.26).

---

## D-023 — `is_candidate` threshold is `editorial_score >= 0.65`

**Status:** `resolved` for this repo · **Date:** 2026-07-26 · **Feeds:** T007 · **Cross-repo:** Path A must match, or `is_candidate` is not comparable

T007 requires `is_candidate` to be *"derived from `editorial_score`, with the threshold documented
and recorded, not a magic number buried in a comparison."* `docs/IDEA.md` says only that
`is_candidate` is a "flagged good-moment" and a derived view (D-001); it never names a number.

**Decision:** `CANDIDATE_THRESHOLD = 0.65` in `elvideo/index/build.py`, compared with `>=`.

**Why 0.65 specifically — it is read off the rubric, not chosen by feel.** The scoring bands in
`gemini.SYSTEM_INSTRUCTION` (D-019) are:

| Band | Meaning |
|---|---|
| 0.85–1.00 | hero moment — the shot you would open or close on |
| **0.65–0.84** | **strong — clear subject, purposeful motion, or a sound bite that stands alone** |
| 0.40–0.64 | useful connective tissue, real but replaceable. *Most shots land here.* |
| 0.15–0.39 | weak |
| 0.00–0.14 | unusable |

0.65 is the floor of **strong**, so `is_candidate` means exactly "the model called this strong or
better". Any other value would cut a band in half and stop corresponding to anything the model was
asked to do. **If the rubric bands are ever re-cut, this constant moves with them** — they are one
decision, not two.

**A null score is not a candidate.** `editorial_score is None` means the shot was never judged —
the model returned nothing for it, or the index came from Path A, where the field is legitimately
null (`docs/schema.md`). Unknown is not good, and a bare `>=` against `None` would be a
`TypeError` anyway.

**Cheap to revisit, deliberately.** Because the index is full rather than top-N (D-001), changing
the threshold is one pass over `shots[]` — no re-run, no second Gemini call. That is the payoff
D-001 was argued on.

**Not recorded in the artifact.** `index_meta` has no field for it, and adding one is a contract
change with D-013's cost. The constant plus this entry is the record. Revisit if the A/B writeup
needs two indexes at different thresholds to be told apart from the file alone.

---

## D-026 — The CLI exposes `--threshold`, and preflights the API key before the slow stages

**Status:** `resolved` · **Date:** 2026-07-26 · **Feeds:** T008 · **Scope:** local (no schema change)

Three small calls made while implementing `elvideo/cli.py`, none of them in T008's acceptance
criteria, all of them visible to a user.

**1. `--threshold` is exposed, though the task file does not list it.** D-012 calls the
`ContentDetector` threshold a **per-video** knob in the same breath as `fps`, and `build_index`
already takes it keyword-only. A per-video knob reachable only from Python is not a per-video knob
— the person who needs it is the person running the CLI on a clip that over- or under-cuts. The
value used is already recorded in `index_meta.scene_threshold` (D-013), so an index built with
`--threshold 20` says so. **Cost:** one more option to keep in step with `scenes.DEFAULT_THRESHOLD`.

**2. `gemini.check_api_key()` is now public, and the CLI calls it before `build_index`.** The
understanding stage is *fourth*: probe, shots and WhisperX run first and cost ~2.5 minutes on
`in.mp4`. Without a preflight, a missing `GEMINI_API_KEY` produces the right exit code and the
right message **two and a half minutes late**. The function is a four-line wrapper over the
existing private `_api_key()`; the real read still happens inside `understand()`, so there is one
source of the message and no way for the two to disagree. `work_dir` and `work_dir/keyframes` are
created up front for the same reason — an unwritable `--work-dir` should fail at second zero, not
after the whole pipeline has run.

**3. Per-stage timing is rendered by attaching a `RichHandler`, not by re-timing anything.**
`build_index` already logs one line per stage plus a total. The alternative — returning a timings
dict — changes `build.py`'s signature to serve the CLI's output format, which is backwards: the
orchestrator has to stay callable without inheriting our presentation. Root logger stays at
WARNING and only `elvideo` is raised to INFO, because torch, whisperx and google-genai are all
chatty at INFO and would bury the eight lines that matter.

**Tooling note, same session:** `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls =
["typer.Argument", "typer.Option"]` added to `pyproject.toml`. B008 ("no function call in an
argument default") already ignored `typer.Option` on `str`- and `float`-annotated parameters but
fired on the enum-annotated `--media-resolution`, which is an arbitrary line: in Typer the call
*is* the parameter spec, not a shared mutable default. Listing the two calls keeps B008 live for
real mutable defaults everywhere else rather than suppressing the rule or scattering `# noqa`.

---

## D-027 — Gemini's per-shot judgments are attached to the wrong `shot_index`

**Status:** `resolved` — **both hypotheses measured; 1 supported, 2 rejected; a residual ceiling remains and is documented** · **Date:** 2026-07-26 · **Found by:** T009 · **Affects:** T004, the A/B writeup · **See the two Updates at the end of this entry**

T009's hand spot-check — the one acceptance criterion that requires a human to look at frames —
found that **most captions do not describe the shot they are stored on.** 17 shots sampled across
`in.mp4`, each compared against its extracted keyframe (the midpoint of `[t_start, t_end)`):

| | |
|---|---|
| Clean match | **2** (`shot_000`, `shot_075`) |
| Partial | **2** (`shot_040`, `shot_116`) |
| Mismatch | **13** |

The worst case is `shot_059`, the clip's **top-scored shot at 0.85**: captioned "Three men sit
side-by-side in the back seat and give a thumbs up", `moment_reason` "Hero shot demonstrating
real-world rear seat width with three adults". The frame is the presenter standing at an open boot
with the rear seats up and nobody in them. An agent asked for the hero moment would cut to that.

**What was ruled out before blaming the model.** Frames re-extracted with
`ffmpeg -ss <midpoint> -frames:v 1` for shots 025, 059 and 105 are the same images the pipeline
wrote, so `quality.score_shot()` samples where it claims to and the boundaries are right. All 234
boundary values are exact multiples of 1/25s and the shots are contiguous over 10,701 of 10,701
frames. `transcript` is unaffected — it joins by **time window** from WhisperX, and it matches the
picture on the same shots that the caption gets wrong. **The classical half of the pipeline is
sound. The failure is entirely in which index each LLM judgment lands on.**

**Not a constant offset, so not repairable by shifting.** `shot_022`'s caption appears on
`shot_025` (+3); `shot_048`'s caption describes what `shot_033`'s frame shows (−15); most have no
visible partner nearby. The misassignment is per-shot.

**Not a captioning failure.** The captions are accurate, specific English about things that
genuinely happen in this video — a three-across rear seat test, a child seat, a 12V socket. The
model watched the whole clip and understood it. Long-context understanding, the thing this path
exists to prove, works. Attribution to a shot is what does not.

**Two hypotheses, neither tested — this entry records a measurement, not a diagnosis:**

1. **Timestamp granularity.** `understand()` passes the shot list as numbered text (D-010) and asks
   for a `shot_index` back. Gemini's own timestamps are second-granular (CLAUDE.md hard constraint
   4) while the median shot here is **2.68s** and **36 of 117 are under 2s**. The model may be
   unable to resolve the boundary list at the granularity the index requires.
2. **Frame starvation.** At `fps=0.5` there are ~214 sampled frames for 117 shots — 1.8 per shot,
   and the sub-2s shots get one frame or none. A shot the model never saw still gets a row in the
   response, and the `p2` rubric asks for a confident judgment on it.

**Why nothing caught it, and what that says.** The schema validates, `validate_index()` passes,
`t_end > t_start` holds, and the slow test's anti-clustering assertions pass (37 distinct scores at
2dp — a genuine `p1 → p2` improvement, D-024). **Every automated gate in this repo checks shape,
and a caption on the wrong shot has the right shape.** D-024 concluded "caption quality was never
the problem", which was true and beside the point: nobody had yet asked whether the captions were
on the right *shots*. A score distribution is not evidence of correctness — it is evidence of
differentiation, and the two came apart here.

**Deferred deliberately.** T009's contract is to measure, and its own Notes section says a failing
criterion is a legitimate outcome. Fixing this inside T009 would have meant spending free-tier
quota on prompt experiments under a task that exists to report numbers. Filed as **T011**, which
starts with a repeatable measurement against the existing index rather than a change — 17
hand-checked shots establish that the problem is real and are not enough to attribute a cause.

**Constraint that shapes any fix:** one Gemini call per video (hard constraint 1). Asking about
each shot separately is the design this project exists to avoid and would blow the 10 RPM cap on a
117-shot clip. Whatever fixes this stays inside a single call.

**Update, 2026-07-26 (T011).** Cause **partly attributed**, entry stays `open`. Hypothesis 1 is
supported and hypothesis 2 is still untested:

- **The model was not locating shots by timestamp — it was counting them.** Adding one instruction
  ("find each shot by its timestamp, not by counting; this detector cuts more finely than a person
  would, so several listed shots can look like one continuous action") moved clean caption/frame
  agreement from **2/17 to 13/17** on the first run. Nothing else changed: same boundaries, same
  `fps=0.5`, same rubric, one call.
- **It did not replicate.** The identical configuration scored **6/17** on a second run. `p3` is
  therefore "2/17 → 6–13/17, n=2", not a fix.
- **Run-to-run variance is larger than the effect being measured.** `seed=7` and `temperature=0.4`
  do not stabilise alignment any more than they stabilise scores (D-024). A single run cannot rank
  two prompts; 2–3 runs per configuration are needed, ~42K tokens each.
- **The model's own timestamps cannot detect the failure.** `p3` requires `t_start_hint` /
  `t_end_hint` on the shot-list path, and `hint_drift()` reports **0 of 117** drifted on every run
  — including runs where two-thirds of the sampled captions describe other footage. The model
  echoes the numbers we gave it back verbatim regardless of where it looked. This closes off the
  most obvious detection idea: **self-report is not independent evidence.**
- **Frame starvation (hypothesis 2) remains untested.** `fps` was never raised. That is the one
  lever with a plausible mechanism that has not been pulled, ~+14K tokens to test.

Full numbers: `docs/run-report.md` § *T011*. Ships as `p3` because both of its runs beat the
baseline; T011's ≥12/17 criterion is recorded as **failed**.

**Update 2, 2026-07-26 (T011 session 009). Hypothesis 2 is measured and REJECTED. This entry moves
to `resolved`** — not because the defect is fixed, but because its closure condition ("closes when
hypothesis 2 is measured or the fix is stable at ≥12/17") is met and the cause is now attributed as
far as this design can attribute it.

**Frame starvation is not the cause.** Three runs at `fps=1.0` against three at `fps=0.5`, `p3`
throughout, one call each, graded on the frozen sample:

| `fps` | Clean matches /17 | Mean | Tokens (mean) |
|---|---|---:|---:|
| 0.5 | 13, 6, 13 | **10.7** | 42,553 |
| 1.0 | 9, 8, 9 | **8.7** | 55,500 |

Doubling the frames the model sees — from ~1.8 per shot to ~3.7 — **does not improve attribution**,
costs +30% tokens, and degrades the score spread (the `stdev < 0.05` warning fired on 2 of 3
`fps=1.0` runs and on none at `fps=0.5`). The mechanism was plausible and it is wrong: the model
was not failing for lack of pixels. See **D-030** for the resulting default.

**A finding that reframes the variance, and corrects Update 1.** Session 009's `fps=0.5` run
reproduced session 008's run 1 **bit-identically** — all 117 captions, all 117 scores, the total
token count (42,764) and the grading call's token count (7,721), hours apart. `seed=7` is therefore
**exactly reproducible**, not merely best-effort-with-jitter. The 6/17 replicate was not a noisy
draw around a mean; it was a *second deterministic outcome*. At `fps=0.5` exactly two outcomes have
been seen: **A** (13/17, 42,764 tok) twice and **B** (6/17, 42,131 tok) once.

The practical rule is unchanged — a single run still cannot rank two configurations — but the
reason is different, and worth stating so nobody reasons about it as Gaussian noise: **repeated
runs sample how many distinct outcomes the service will serve, not a distribution around a true
value.** A mean over three runs summarises a small discrete set.

**What is actually left.** Between the two updates, the defect is bounded from both sides: prompt
anchoring is worth ~9 matches out of 17, frame budget is worth none, and the model's self-report
detects nothing. `gemini-3.5-flash` attributing a moment to one of **117 sub-3-second intervals**
across 7 minutes is roughly **60% reliable**, and neither lever available inside one call closes
the rest. The one untested class of fix is **asking a different question**: merge adjacent very
short shots before the call so the model chooses among ~60 distinguishable intervals rather than
117 near-identical ones. That changes `shots[]` itself, so it is a product decision (and a
`--threshold` change), not a prompt tweak. Recorded here as the successor idea, not scheduled.

---

## D-028 — `p3`: the prompt anchors on timestamps, and hints are requested on both paths

**Status:** `resolved` — **shipped, improvement measured, not a cure** · **Date:** 2026-07-26 · **Task:** T011 · **Supersedes the shot-list half of D-024** · **Affects:** T004, D-010, the A/B writeup

D-010 chose to pass PySceneDetect's boundaries as numbered text and take a `shot_index` back,
reasoning that this "deletes the problem" of fuzzy temporal alignment. D-027 is the bill for that
reasoning: an index lookup is only as good as the index the model puts in the field, and **nothing
in the design ever asked the model to demonstrate it had looked where it claimed.**

**What changed in the prompt (`p2` → `p3`):**

1. **Locate by timestamp, do not count.** Stated with the mechanism, because the mechanism is the
   persuasive part: this detector cuts far more finely than a person would — several listed shots
   can be one continuous-looking action, and 36 of 117 shots here are under 2s — so a model
   counting cuts as it watches drifts out of step with the list.
2. **Hints on the shot-list path too**, reversing `p2`'s judgment that echoing numbers we already
   know is output tokens for nothing. It is not a number we already know: it is the model's account
   of where it looked.
3. **A self-check**, telling the model to re-describe from the listed times if the moment it
   described falls outside interval *k*.
4. **An honest-uncertainty escape** — "brief, indistinct frame" and a low score beat borrowing a
   neighbour's content.

**Measured** (`in.mp4`, 117 shots, one call each, `fps=0.5`, grader `g1`): `p2` **2/17** →
`p3` **13/17** → `p3` replicate **6/17**. Tokens 38,956 → ~42,100 (+8%), well under the 250K TPM
cap. Call count 1 on every run, from the counter.

**`p4` was tried and reverted.** It added one paragraph re-asserting the ranking rubric, to repair
the score flattening seen on `p3`'s first run (range 0.27, which fails D-024's `>0.3` guard). It
worked on scores (range 0.60, 39 distinct) and **collapsed alignment to 4/17**. The two
instructions compete for the model's attention. `p3`'s replicate then produced range 0.48 unaided,
so the flattening was substantially run variance rather than a property of `p3` — which is why the
paragraph was removed rather than kept.

**Kept despite not closing T011** because both `p3` runs beat the baseline and the token cost is
trivial against the cap. Recorded as an improvement with a measured range, not as a fix.

**Two smaller changes ride along:**

- **`gemini.is_rate_limited()` is public.** `elvideo.eval.alignment` builds its own retryer over
  the same predicate and constants; it must not route through `_generate_with_backoff`, which
  increments the one-call-per-video counter.
- **`hint_drift()` is public** and `_check_hints()` warns above 25% drift. It is a **regression
  guard, not the detector T011 wanted** — see D-027's update for why the model's self-report is
  worthless here.

---

## D-029 — Caption/frame agreement is measured by a Gemini judge over a frozen 17-shot sample

**Status:** `resolved` · **Date:** 2026-07-26 · **Task:** T011 · **Affects:** T009's spot-check criterion, any future prompt work

T009's spot-check was a human reading keyframes. It found the repo's worst defect and **could not
be re-run**, so no fix could be shown to have worked. T011 needed a number that survives the
session that produced it.

**Decision: `elvideo/eval/alignment.py` — one Gemini call grades all 17 `(keyframe, caption)`
pairs as match / partial / mismatch, against the frozen sample in `alignment_sample.json`.**

**Why a model grader and not a human, given a model is what failed.** The two tasks are not the
same task: the index call watches 7 minutes of video and must attribute a moment to one of 117
intervals; the grader looks at one still beside one sentence and says whether they agree. The
second is the easy half of the first. It was validated before being trusted — on the T009 index
the grader returned 2 match / 1 partial / 14 mismatch and **agreed with the human column on 16 of
17**, without being shown it. That calibration, not the architecture, is the argument.

**Why the sample is the same 17 shots and not a rule-generated grid.** T011's criterion 1 asks for
a fixed rule and mildly disfavours hand-picking; criterion 2 asks for ≥12 **of 17** against a
published 2/2/13 baseline. Those pull opposite ways and comparability won: a rule-based sample
would have required re-grading the old index to get a comparable denominator, and the T009 17 span
the timeline and the score range anyway. **Recorded as the known weakness of this measurement**, in
the sample file and in the report, rather than smoothed over.

**Design points worth keeping:**

- **One request for the whole sample**, frames interleaved after their own captions. The
  measurement obeys the same one-call rule as the thing it measures.
- **It never touches `generate_call_count()`.** Hard constraint 1 is enforced by that counter, and
  a measurement that inflated it would break the criterion it exists to check.
- **`temperature=0.0`**, unlike the index call's 0.4 (D-019): grading wants no spread.
- **Frames are downscaled to 768px JPEG** before sending — 17 full-size PNGs are ~16 MB base64
  against a 20 MB inline ceiling, and `MEDIA_RESOLUTION_LOW` renders them to a small tile anyway.
- **A partial or padded response is refused, not tallied.** A ratio over an unknown denominator is
  the exact kind of number this task exists to stop trusting.

**Cost:** ~3K tokens per grading call, seconds of wall clock. Cheap enough that it should run on
every future prompt change — and per D-027's update, **2–3 times per configuration**, because
run-to-run variance on this measure is larger than most of the effects being chased.

---

## D-030 — `fps` default stays 0.5; raising it is measured and rejected

**Status:** `resolved` · **Date:** 2026-07-26 · **Task:** T011 · **Closes:** T011 criterion 7 · **Affects:** D-019, `docs/IDEA.md` § *Gemini call settings (locked)*

`docs/IDEA.md` pins `fps: 0.5` as the default and calls it a per-video knob. D-027 hypothesis 2
argued the default was starving the model of frames on a clip where 36 of 117 shots are under 2s.
T011 criterion 7 requires that any change to it be justified with **measured agreement and token
cost at both values** — so it was measured at both, three runs each, rather than argued.

**Decision: the default stays `DEFAULT_SAMPLE_FPS = 0.5`. No code change.**

| `fps` | Agreement (mean of 3) | Tokens (mean) | Score spread |
|---|---:|---:|---|
| **0.5** | **10.7 / 17** | **42,553** | stdev 0.058, 27–30 distinct; clustering warning never fired |
| 1.0 | 8.7 / 17 | 55,500 (+30%) | stdev 0.043–0.080, 21–26 distinct; warning fired on 2 of 3 |

`fps=1.0` costs 30% more tokens, aligns no better (the 8–9 band sits inside `fps=0.5`'s 6–13 band),
and measurably flattens the editorial scoring it was not supposed to touch. There is no reading of
these numbers that justifies moving a pinned default.

**The knob is unchanged and still worth having.** `--fps` remains exposed on the CLI (T008) and is
still the right lever for footage genuinely unlike this clip — a static talking head downward, fast
action upward. What is now recorded is that **it is not a fix for attribution**, so nobody spends
another 55K tokens rediscovering that.

**Rides along: the slow test's score-range assertion is lowered 0.3 → 0.2.** This was left as a
known coin-flip in session 008 on two samples; six `p3` runs now bound it. Measured ranges:
0.27 / 0.48 / 0.27 at `fps=0.5`, 0.32 / 0.65 / 0.25 at `fps=1.0`. At 0.3 the assertion fails **4 of
6** — and it never caught what it was written for: **`p1`'s range was 0.65** (0.10–0.75, D-024),
comfortably over 0.3, so `p1`-style clustering has always been caught by the granularity assertions
(`distinct ≥ 15`, `<90%` on the 0.05 grid), never by this one. 0.2 sits below the measured floor of
0.25 with margin and still fails a genuinely collapsed distribution. The reasoning is in the test
body, not just here.

---

## D-031 — The binding free-tier limit is 20 requests/day/model, not the TPM cap

**Status:** `resolved` — **a session-planning constraint; no code change** · **Date:** 2026-07-26 · **Task:** T011 · **Affects:** every future live session, `docs/IDEA.md` § *Gemini call settings*, D-025

`docs/IDEA.md` says "TPM cap is 250K/min → iterate freely all day", and D-025 re-anchored the token
budget to that cap. Both are about **tokens**. Session 009 budgeted 5 index runs, ran 4, and the
fifth was refused:

```
Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests,
limit: 20, model: gemini-3.5-flash
quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier
```

**The real ceiling on iteration is 20 `generate_content` requests per project per model per day.**
Not 10 RPM (that is a per-minute cap the backoff already handles), not 250K TPM. At ~42K tokens a
run, 20 requests is ~840K tokens — so **the request count runs out long before the token budget
does**, and every token-based budget in this repo has been measuring the non-binding resource.

**What this changes, concretely:**

- **Grading calls come out of the same pool as index calls.** `elvideo.eval.alignment` is
  deliberately not counted by `generate_call_count()` (D-029, hard constraint 1) — that is correct
  for the one-call-per-video rule and misleading for quota. A measured index run costs **2**
  requests, not 1.
- **A session gets ~10 measured runs per day, shared with anything else on the key.** Session 008
  spent 7 requests and session 009 spent 8, the same day, which is where the 20 went.
- **"2–3 runs per configuration" (D-027) is expensive in the resource that actually binds.**
  Comparing two settings properly is 12 requests — over half a day's quota.

**No code change, deliberately.** The backoff already retries 429 and already emits an actionable
message; it simply cannot retry its way past a daily cap, and it correctly gave up after 5
attempts. The fix is to **plan sessions in requests, not tokens** — state the request count up
front the way session 009 stated the token count, and stop at the cap rather than discovering it.

**`docs/IDEA.md` is left unedited**, per `.claude/CLAUDE.md`'s rule that a conflict with the spec is
logged rather than silently resolved. Its "iterate freely all day" is optimistic; this entry is the
correction. Flagged for the owner alongside the D-016 follow-up.

---

## D-032 — T011 closes as `partial` **by design**; the coarser-intervals experiment is its named successor

**Status:** `resolved` — **scope decision, not a pass. No code change, no live requests.** · **Date:** 2026-07-27 · **Task:** T011 → T012 · **Affects:** `tasks/T011-caption-shot-alignment.md`, `tasks/backlog.md`, `docs/run-report.md`, `state/progress.json`

Session 010 had exactly two legitimate moves and had to pick one before spending anything:
**(A)** change *what is asked* — merge adjacent sub-2s shots via `--threshold` so the model chooses
among ~60 distinguishable intervals instead of 117 near-identical ones; **(B)** accept the measured
ceiling, close T011, and write the A/B up precisely. **B was chosen.**

**The decision: T011 is closed at `partial`, and `partial` is the correct final state — it does not
become `done` and it does not enter `completed_tasks`.** Its criteria 2 and 3 fail and are recorded
as failing. Closing it is a statement that *no further work on T011 as scoped will change that
number*, not a claim that the number is acceptable.

**Why the ceiling is genuinely closed rather than merely unbeaten.** Every lever inside T011's scope
has been pulled and measured across sessions 008–009:

| Lever | Result | Where |
|---|---|---|
| Prompt: stop the model counting shots, anchor on timestamps (`p2` → `p3`) | **2/17 → mean 10.7/17** | D-027, D-028 |
| Prompt: restore score spread (`p4`) | Alignment collapsed to 4/17 — reverted | D-028 |
| Frame budget: `fps` 0.5 → 1.0 | **Worse** (8.7 vs 10.7) at **+30% tokens** | D-030 |
| Model self-report as a detector (`hint_drift()`) | 0–1 of 117 on runs two-thirds wrong | D-027, D-029 |
| Validity checks inside `understand()` | Pass on every run including the 6/17 one | T011 criterion 6, closed |

What remains outside the repo's reach: a bigger model (pinned, hard constraint 3), per-shot calls
(forbidden by hard constraint 1 and the reason this project exists), and finer control over how
Gemini binds a judgment to an interval (not exposed). **The only untested class of fix changes
`shots[]` itself**, which is a different artifact, not a fix to this one.

**The measured statement being closed on:** `gemini-3.5-flash` attributing a moment to one of 117
sub-3-second intervals across a 7-minute clip is **~60% reliable — 58 of 102 graded pairs clean over
six `p3` runs**, and no lever available inside one call closes the remaining 40%.

**What closing produces instead of another run:** `docs/run-report.md` § *T011 closed — partial by
design* now carries an explicit **what a consumer may / may not trust** split, a numbered
known-limitations list aimed at whoever writes the downstream agent, and the A/B claim stated as two
halves — **the claim about *what is in the video* holds; the claim about *which second* does not.**
That is a more useful artifact than a seventh prompt variant, and it cost zero of the day's 20
requests (D-031).

**The successor is named, not dropped: [T012](../tasks/T012-coarser-intervals.md), `not_started`.**
It is deliberately a new task rather than a continuation, because it changes `shots[]` — the index's
spine, its `t_start`/`t_end`, its keyframes — and T011's own Inputs/Outputs section states the
boundary list arrives "unchanged, both already correct". Two costs are recorded in the task file so
they are paid consciously: **the frozen 17-shot sample stops being directly comparable** (it is keyed
on `shot_###` ids that would no longer denote the same footage — remap by *timestamp* and state the
changed denominator), and **fewer shots is a worse index for some downstream questions**, since a
1.4s B-roll cutaway can vanish inside a 6s parent.

**The schema does not change** under either path — `shots[]` gets different *content*, not a
different *shape* (hard constraint 6). If T012 ever needs a field recording that shots were merged,
that is a contract change and comes back here first.

**Revisit if:** T012 reaches a stable ≥12/17 on a stated denominator — in which case the ceiling was
a property of *this footage's* cut granularity, not of the model, and that is worth saying loudly.
Or if the pinned model changes (hard constraint 3 would have to move first), which would invalidate
the ceiling measurement outright rather than refine it.

---

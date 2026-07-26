# Session log

Append-only, newest at the bottom. Written by `/checkpoint`. Format:
`prompts/templates/session-start-template.md` § A.

---

## 2026-07-25 — s1 bootstrap · scaffold only

**Task(s):** none — this was the bootstrap session that created the task breakdown itself.
**Status at end:** `scaffold_complete`

### Done

- `uv init` + all deps resolved and locked (151 packages, Python 3.11–3.12):
  runtime `google-genai`, `scenedetect`, `whisperx`, `opencv-python`, `pydantic`, `jsonschema`,
  `python-dotenv`, `tenacity`, `typer`, `rich`; dev `pytest`, `ruff`, `mypy`. Ruff/mypy/pytest
  configured in `pyproject.toml`.
- Agent harness: `.claude/CLAUDE.md` (hard constraints + session protocol) and three slash
  commands — `/start-task`, `/checkpoint`, `/new-task`.
- Docs: `docs/architecture.md` (pipeline, module map, division of labour) and `docs/schema.md`
  (the shared contract in prose, Path A vs Path B edges). `docs/IDEA.md` untouched.
- Tasks T001–T010 seeded, one file each, with acceptance criteria pulled from `docs/IDEA.md`'s
  Definition of Done. `tasks/backlog.md` indexes them.
- State: `progress.json`, `decisions-log.md` (10 entries, 4 unresolved), this log.
- **Schema written for real, not stubbed** — `elvideo/schema/models.py` (pydantic) and
  `elvideo/schema/footage_index.schema.json` (JSON Schema), plus `tests/test_schema.py`
  asserting the two haven't drifted. These are declarative rather than pipeline logic, so they
  were seeded; T006 is downgraded to `partial` accordingly. `validate_index()` is still a stub.
- Pipeline stubs with real signatures, type hints, and docstrings citing `docs/IDEA.md`:
  `probe.py`, `scenes.py`, `transcribe.py`, `gemini.py`, `quality.py`, `build.py`, `cli.py`.
  Every one raises `NotImplementedError("see tasks/T00X-*.md")`.
- Root: `README.md` (ffmpeg prerequisite called out loudly), `.env.example`, `.gitignore`.
- Verified on this machine: uv 0.11.26, Python 3.11.15, git 2.47.0, **ffmpeg/ffprobe 8.1.1 on
  PATH**.

### Verified, not just written

Ran in an ephemeral `uv run --no-project --with ...` environment, so the scaffold could be
checked without the multi-GB torch install (D-008):

- `pytest` — **8 passed** (`tests/test_schema.py`).
- `ruff check .` — **clean**. `.agents/` excluded in `pyproject.toml`: it's vendored tooling with
  21 pre-existing lint hits, not this project's source.
- `mypy elvideo` (strict) — **clean, 12 source files**.
- `python -m elvideo index foo.mp4` reaches the T008 stub, and `--help` renders.

**Two real bugs found and fixed by doing this rather than assuming:**

1. Typer collapses a single-command app, dropping the subcommand name — `python -m elvideo index
   in.mp4` was parsing as "unexpected extra argument `in.mp4`", i.e. the exact DoD invocation
   didn't work. Fixed with an `@app.callback()` to force multi-command mode.
2. `--help` crashed with `UnicodeEncodeError` — a `≤` in the Typer help string against a cp1252
   Windows console. Help strings are now ASCII-only. Both are recorded in `tasks/T008-cli.md` so
   they don't get reintroduced.

### Not done / deferred

- **No pipeline logic whatsoever.** No Gemini call, no scene detection, no transcription. That
  was the scope boundary for this session.
- **`uv sync` not run** (D-008). Deps are resolved and locked but not downloaded — `whisperx`
  pulls torch, a multi-GB download that would have dominated a session that runs no code.
  `uv run pytest` will not work until the next session runs `uv sync` first.
- No remote, no push — the user's call.

### Decisions made

- **D-004** — spec file is `docs/IDEA.md` (uppercase); referenced that way everywhere rather
  than relying on Windows case-insensitivity.
- **D-005** — one `Shot` type populated in stages, rather than a separate `ShotBoundary`. Keeps
  `detect_shots(path) -> [Shot]` from `docs/IDEA.md` literally true.
- **D-006** — added `elvideo/__main__.py` (not in the bootstrap tree) because `python -m elvideo`
  can't resolve without it, and that invocation is a DoD criterion.
- **D-007** — `scenedetect[opencv]` extra doesn't exist in 0.7.1; used plain `scenedetect` plus
  explicit `opencv-python`.
- **D-008** — deps locked but not installed.
- **D-009** — keeping both schema artifacts by hand, deliberately redundant, because pydantic's
  generated JSON Schema doesn't `diff` cleanly against Path A's.
- **D-010** — flagged an open design question: `understand()`'s fixed signature doesn't take the
  shot list, so T007 must align two possibly-different lists. Leaning toward passing boundaries
  in the prompt text. To be settled in T004.

### Blockers

- **D-003 blocks T009 entirely** — no agreed A/B test video, so end-to-end validation can't run.
- **D-001 and D-002 are unresolved and T006/T007 are already building on the assumed answers.**
  `docs/IDEA.md` says of the contract: *"Lock it before either of us codes further."* Every day
  these stay open, both repos code further against an unconfirmed shape.
- `uv sync` outstanding (D-008).

### Next

- **T010 first, or at least its D-003 half** — it's a message to the co-founder, not a work
  session, and it unblocks T009 while stopping T006/T007 from compounding assumptions.
- Then T001 + T002 (probe and shots — small and sequential):
  `prompts/session-start/001-probe-and-scenes.md`.

---

## 2026-07-25 — T001 + T002 · probe and shot detection

**Task(s):** T001 — `probe.py` ffprobe wrapper; T002 — `scenes.py` shot detection
**Status at end:** both `done` — every acceptance criterion met (one with a caveat, see D-014)

### Done

- `elvideo/index/probe.py` — full implementation. Existence check first (`FileNotFoundError`
  with path), actionable "ffprobe not on PATH — install ffmpeg" when the binary is missing,
  `ValueError` carrying path + stderr on non-zero exit / unparseable JSON. `num/den` fps parse
  (`30000/1001` → 29.97). Pydantic `ValidationError` subclasses `ValueError`, so zero/absent
  fields surface through the same declared exception.
- `tests/test_probe.py` — 5 tests, subprocess mocked, no fixture video: fps parse, vertical
  1080×1920 no-transposition, missing file, missing binary, non-zero exit, garbage output.
- `elvideo/index/scenes.py` — full implementation. `ContentDetector(threshold=27.0)` per D-012,
  exposed as module constants `DEFAULT_DETECTOR` / `DEFAULT_THRESHOLD` (the reproducibility
  record Path A must match). `threshold` is a keyword arg with that default — the per-video knob,
  signature still literally `detect_shots(path) -> list[Shot]`. Uses `.seconds` property (not
  deprecated `get_seconds()`); `get_scene_list(start_in_scene=True)` guarantees one whole-video
  shot when no cuts are found.
- `tests/test_scenes.py` — 5 tests: missing file, settings-recorded guard, mocked 120-scene list
  proving `shot_100`+ ids validate, real-video invariants on `in.mp4` (117 shots, gapless,
  `t_start==0.0`, boundaries on exact frame multiples at 25 fps), and a real no-cut clip
  generated via ffmpeg lavfi (skips if ffmpeg absent) returning exactly one shot.
- Smoke-tested on the real A/B clip: probe returns `428.106304s / 25.0 fps / 1280×720`
  (matches D-003); detection returns **117 shots in 25.3s** (D-012 said 20.8s — same order,
  under the minute budget), `last_end=428.04`, `min_dur=0.64s`.
- Gates: `pytest` **18 passed**, `ruff check .` clean, `mypy elvideo` strict clean.
- `uv sync` — deps were already installed (progress.json `deps_installed: true`); the D-008
  blocker was already cleared before this session.

### Not done / deferred

- Nothing from either task file. Rotation metadata (T001 notes) remains out of scope by design.

### Decisions made

- **D-014 (new)** — container duration ≠ video-stream duration on `in.mp4`: `probe().duration_s`
  = 428.106 (format block, audio tail included) vs final shot `t_end` = 428.04 (10,701 frames ÷
  25). Gap 0.066s > one frame. T002's "final t_end equals video duration within one frame" holds
  against the *stream* duration only; T007 must tolerate ~0.1s container/stream skew when
  validating coverage.
- No new detector decisions — D-012's `ContentDetector(threshold=27.0)` adopted as specified,
  now encoded in `scenes.py` constants and guarded by a test.

### Blockers

- **D-001 / D-002 still unresolved** — T010 (co-founder message) remains the highest-leverage
  next step. T002's settings are now written down in code, which is exactly what D-002's
  resolution needs to point at.
- None for T003 — it can start immediately.

### Next

- **T003 — `transcribe.py`** (WhisperX word-level): `prompts/session-start/002-transcribe.md`.
  Slowest stage; device + model settings must be recorded (D-002). T010 message to the
  co-founder can happen in parallel — it's a message, not a session.

---

## 2026-07-26 — T003 + T010 · transcription, and the contract locked

**Task(s):** T003 — `transcribe.py` WhisperX word-level; T010 — schema-sync checkpoint
**Status at end:** both `done`. T003 met every acceptance criterion; T010 was **rewritten
mid-session** after the owner said the repo is solo, and closed as a self-lock rather than a sync.

### Done

**T003 — `elvideo/index/transcribe.py`, full implementation.**

- `transcribe(path, *, model_size, compute_type, language, device, batch_size)` — faster-whisper
  pass for text, then WhisperX's wav2vec2 alignment pass for per-word timing. Alignment kept, per
  the task's explicit warning: plain faster-whisper output is segment-level and fails the first
  criterion.
- No-audio guard runs **first**, via `ffprobe -select_streams a:0`, so a silent container returns
  `[]` without ever loading WhisperX. Checked against a real ffmpeg-generated clip, not only a
  mock — WhisperX's ffmpeg-backed loader errors out on such a file, so the guard is doing real
  work.
- `_to_words()` drops words WhisperX emits with **no `start`/`end`** — real behaviour for
  characters outside the wav2vec2 dictionary (digits, symbols), confirmed by reading
  `whisperx/alignment.py:356`. They carry no timing, so a fabricated one would be worse than
  dropping. Negative durations clamped to `0.0` (`Word.d` is `ge=0`). Output sorted explicitly
  rather than trusting WhisperX's order.
- Settings as module constants for D-002: `DEFAULT_MODEL_SIZE="base"`, `DEFAULT_COMPUTE_TYPE="int8"`,
  `DEFAULT_LANGUAGE="en"`, `DEFAULT_BATCH_SIZE=16`, plus `pick_device()`. Guarded by a test.
- `words_in_range()` — half-open `t_start <= w.t < t_end`.
- Stage timing logged at INFO **with device / model / compute type on the same line**, because a
  timing number without them is not comparable to anything.
- `tests/test_transcribe.py` — 14 tests. Boundary at `t == t_start` (included), at `t == t_end`
  (excluded), one-shot-only ownership across a cut, silent range joining to `""`, empty word
  list, zero-width range, order preserved; plus missing file, no-audio (mocked **and** real
  ffmpeg clip), missing ffprobe, per-word conversion, dropped unaligned words, clamped duration.
  A real-video integration test is marked `slow` (new pytest marker in `pyproject.toml`).

**Measured on `in.mp4` (428s), warm — logged as D-015:**

| | |
|---|---|
| Words | 1436 |
| Wall-clock | **102.7s** — ASR 49.5s + alignment 53.2s |
| Device | cpu (`torch 2.8.0+cpu`, `cuda.is_available()` False) |
| First / last word | `t=0.928` / `t=427.017` |
| Mean / max word duration | 0.18s / 2.02s — word-level, not segment spans |
| Words dropped across all 117 shots | 0 |
| Silent shots | 7 of 117 |

Cold first run was **202.5s** — it downloads the 360 MB wav2vec2 checkpoint. Cached after. The
102.7s number is the one that counts against the budget: ~34% of 300s, so **not a blocker**, and
that verdict is why `base` was chosen over `small` (roughly 2–3× slower on CPU).

**T010 — contract locked, four decisions closed.** See "Decisions made" below.

**Gates:** `pytest -m "not slow"` **35 passed**; the slow integration test **1 passed in 104.11s**;
`ruff check .` clean; `mypy elvideo` strict clean, 12 files.

### Not done / deferred

- **`/checkpoint` was run at the very end** — `progress.json` and `backlog.md` had already been
  hand-synced during the session; this entry and the next-session prompt are the checkpoint's own
  work.
- **Nothing deferred from T003.** Every acceptance criterion is checked off in the task file with
  the number that satisfies it.
- **T010's two Path-A criteria are marked N/A, not done** — "compare the schema field-for-field
  against what Path A emits" and "log Path A's entrypoint if it differs" cannot be satisfied
  without a Path A. Struck through in the task file rather than quietly ticked.
- **`.claude/CLAUDE.md` hard constraint 6 and `docs/IDEA.md` left unedited on purpose.** Both
  still describe the co-founder repo as a *live* manual-sync risk, which D-016 makes
  aspirational. CLAUDE.md's own rule is to log a conflict rather than silently pick a side, so
  it's logged and handed to the owner.
- No commit — the user drives git.

### Decisions made

- **D-015 (new)** — WhisperX settings pinned: `base` / `int8` / `cpu` / `en`, batch 16, torchaudio
  `WAV2VEC2_ASR_BASE_960H` alignment model. Full measurement table, plus the cold-start caveat and
  a note that `pyannote.audio`'s `torchcodec` DLL warning on this box is harmless noise.
- **D-016 (new, governance)** — the owner stated the repo is **solo**; there is no Path A
  counterparty. Three decisions had been parked as "needs the co-founder", and T010 was written
  as a conversation. With nobody to ask, waiting was a permanent block, so they are now
  owner-locked with reasoning. Records what does *not* change (the schema keeps its A/B shape;
  settings stay pinned; changes still get logged) and a reversal condition if a Path A ever
  appears.
- **D-001 → resolved: full index + `is_candidate`.** Argued on merit, not just as the inherited
  assumption: top-N discards exactly the shots downstream questions need. No code change.
- **D-002 → resolved: moot as posed.** Nothing to share with; what survives is the half that does
  the work — settings pinned in code and guarded by tests (D-012, D-015), and from T007 also
  written into the artifact via D-013.
- **D-013 → resolved and shipped.** `index_meta.scene_detector` + `.scene_threshold`, required,
  no defaults, in `models.py` **and** `footage_index.schema.json`, with a new guard in
  `tests/test_schema.py`. **Found while doing it:** `test_block_fields_match_pydantic` never
  covered the `index_meta` block at all — a one-sided edit there would have passed silently.
  `index_meta` is now in the parametrize with the other three blocks.
- **D-010 → resolved: option 2**, shot boundaries go into the Gemini prompt text. Option 1's
  overlap alignment would match 117 frame-accurate shots against Gemini's own segmentation using
  timestamps the constraints already declare untrustworthy — a mis-alignment yields a
  plausible-looking index with captions on the wrong shots and no error. Boundaries arrive as an
  optional kwarg defaulting to `None`, so `understand(path, fps, media_resolution)` stays
  literally callable as `docs/IDEA.md` writes it.
- Propagated into task files: T004's "open question" section replaced with the settled answer;
  T006 reduced to just `validate_index()`; T007 gained two criteria (index-lookup alignment must
  fail loudly on an out-of-range `shot_index`; `index_meta` must carry the detector values
  actually passed to `detect_shots()`); T010 rewritten with the original framing preserved below
  a divider.

### Blockers

- **None.** `progress.json.blockers` is empty for the first time. The D-001/D-002 pair that
  blocked T006/T007 is closed, and T009's D-003 blocker was cleared last session.
- One thing needs the owner, but it blocks nothing: whether to soften CLAUDE.md constraint 6 or
  keep it as intended future state (D-016).
- T004 will need a `GEMINI_API_KEY` in `.env`. Not verified this session — worth confirming
  before that session starts, not during it.

### Next

- **T005 — `quality.py`** (OpenCV Laplacian + exposure):
  `prompts/session-start/003-quality.md`. Smallest remaining task, no API key, no model download,
  and T002 already supplies the shot boundaries it samples within.
- Then T004 (Path B core, now unambiguous), T007, T008, T009.

---

## 2026-07-26 — T005 · OpenCV quality scoring

**Task(s):** T005 — `quality.py`, Laplacian sharpness + exposure
**Status at end:** `done` — every acceptance criterion met, each ticked in the task file with the
number that satisfies it.

### Done

- **`elvideo/index/quality.py`, full implementation.** `score_frame(img)` and
  `score_shot(path, t_start, t_end, work_dir, *, shot_id=None)`. Formula:

  ```
  sharpness       = min(sqrt(laplacian_variance / 1000.0), 1.0)
  brightness_term = max(1 - |mean_luma/255 - 0.5| / 0.5, 0)
  clipping_term   = max(1 - clipped_fraction / 0.5, 0)      # px <= 8 or px >= 247
  quality         = round(0.7*sharpness + 0.3*brightness_term*clipping_term, 4)
  ```

  Every constant is module-level and named (`SHARPNESS_SATURATION`, `W_SHARPNESS`, `W_EXPOSURE`,
  `EXPOSURE_TARGET`, `CLIP_LOW`, `CLIP_HIGH`, `CLIP_SATURATION`, `SAMPLE_POSITION`,
  `ROUND_DIGITS`, `KEYFRAME_PNG_COMPRESSION`) — the D-012 / D-015 precedent, guarded by a test.
- **Sampling:** midpoint of `[t_start, t_end)`, fixed. Seeks via `CAP_PROP_POS_MSEC` rather than
  decoding sequentially; falls back to a `t_start` seek once before raising, since a seek can land
  past the last decodable frame on a shot at the tail of the file.
- **Validation:** `_to_gray()` rejects non-arrays, empty arrays, non-uint8 dtypes, and bad channel
  counts. uint8 is required rather than coerced — `CLIP_LOW` / `CLIP_HIGH` are 8-bit levels and a
  float image would silently invalidate them.
- **`tests/test_quality.py` — 19 tests + 1 slow.** Sharp-vs-blurred fixture pair (built
  arithmetically, no binary in the repo; gap asserted `> 0.1`, not merely `<`), all-white and
  all-black both exactly `0.0` with an explicit `NaN` check, flat mid-gray scoring exposure-only
  (the documented content-dependence, pinned as behaviour), grayscale/BGRA parity, six
  `ValueError` paths, determinism across repeated calls and array copies, keyframe naming both
  ways, and a frame-for-frame proof that the midpoint is what gets extracted.
- **Rounding is load-bearing, not cosmetic:** `cv2.Laplacian` dispatches to different SIMD kernels
  per CPU, so raw float64 can differ in its last bits across machines. 4 decimals sits far coarser
  than that noise and far finer than any decision made on this field, which is what makes
  "bit-identical across runs and machines" true rather than aspirational.

**Measured on `in.mp4` (117 shots) — logged as D-017:**

| | |
|---|---|
| Stage wall-clock | **18.8s** (0.161s/shot), PNG keyframe writes included — 6% of the 300s budget |
| min / p25 / median / p75 / max | 0.061 / 0.355 / 0.480 / 0.555 / 0.857 |
| mean / stdev | 0.465 / 0.169 |
| Distinct values at 2 dp | 55 of 117 |
| Frames at the 1.0 ceiling | **0** |

The spread is the check that mattered: a metric returning ~0.8 for everything would be as broken
as a model that scores everything 0.8. `test_real_video_scores_spread` fails if the range collapses
below 0.3 or distinct 2-dp values drop under 20, so the check survives the session.

**Gates:** `pytest -m "not slow"` **54 passed** (was 35); `pytest -m "slow"` **2 passed in
144.88s**; `ruff check .` clean; `mypy elvideo` strict clean, 12 files.

### Not done / deferred

- **Nothing from the task file.** All nine criteria met.
- **Three-frame median sampling stays out of scope**, as the task file directed — `/new-task` it
  if one frame per shot proves too noisy in T009.
- **Per-call `VideoCapture` open kept, deliberately.** It costs ~0.1s of the 0.161s per shot; a
  capture shared across shots measured 0.045s/shot (5.3s total for 117). At 6% of budget the
  simpler signature won. If the budget tightens, this is the cheapest 13s in the pipeline.
- **`docs/schema.md` and `docs/IDEA.md` untouched** — `quality` was always described as
  "Laplacian + exposure, deterministic"; this session fills in the constants behind that phrase,
  it doesn't change the contract.
- No commit — the user drives git.

### Decisions made

- **D-017 (new)** — the formula and every normalization constant, with the measured distribution.
  Records **why square root, not raw variance**: variance is quadratic in contrast, so linear
  normalization pinned 26 of 117 shots at exactly 1.0 at saturation 300, or crushed the median to
  0.169 at saturation 1000. The square root is the Laplacian standard deviation — gray levels,
  linear in contrast — and lands the median at 0.411 with nothing at the ceiling. Also records why
  saturation is 1000 rather than this clip's own maximum of 832.7: pinning it to the test footage
  would stop the metric discriminating on better footage.
- **D-018 (new)** — `score_shot()` gains a keyword-only `shot_id: str | None = None`. The task
  file flagged the tension directly: the criterion wants `shot_###.png` but the `docs/IDEA.md`
  signature never passes the id. Same extend-a-fixed-signature pattern as D-012 and D-010, so the
  positional call stays literally valid. Fallback name is `shot_at_{sampled_ms:08d}ms.png` —
  timestamp-derived, so two shots cannot overwrite each other the way a fixed name would.
  **T007 must pass `shot_id=shot.id`** or the keyframes on disk stop matching the index.
- No conflicts with `docs/IDEA.md` — nothing to log under the CLAUDE.md conflict rule this session.

### Blockers

- **None.** `progress.json.blockers` stays empty.
- Checked ahead for T004 rather than discovering it mid-session: **`.env` has a non-empty
  `GEMINI_API_KEY`.** Last session flagged this as worth confirming before T004 starts, not during.
- The D-016 owner follow-up is still open and still blocks nothing: whether to soften CLAUDE.md
  hard constraint 6, which describes the Path A repo as a live sync risk.

### Next

- **T004 — `gemini.py`**, the Path B core: `prompts/session-start/004-gemini.md`. One
  `generate_content` call per video, `gemini-3.5-flash` pinned, `media_resolution="low"`,
  `fps=0.5`, shot boundaries in the prompt text per D-010. Prompt design is the real work; the API
  plumbing is not.
- Then T007 (orchestrator — must pass `shot_id=shot.id` per D-018 and populate `index_meta`'s
  detector fields per D-013), T008, T009.

---

## 2026-07-26 — T004 · Gemini native understanding (the Path B core)

**Task(s):** T004 — `gemini.py`, one native call per video
**Status at end:** **`blocked`** — code complete, all gates green, but **no live API call was ever
made**: the key in `.env` has no quota. Four acceptance criteria are unverifiable without one real
call and are marked `[~]` in the task file rather than ticked. See D-021.

### Done

**`elvideo/index/gemini.py`, full implementation.**

- `understand(path, fps=0.5, media_resolution="low", *, shots=None)` — the positional signature
  `docs/IDEA.md` § *Module layout* fixes, extended with the D-010 boundaries kwarg exactly the way
  D-012 and D-018 extended theirs.
- **One `generate_content` per invocation, instrumented not intended.** `generate_call_count()` /
  `reset_call_count()`; `test_exactly_one_call_regardless_of_shot_count` pushes 117 shots through a
  mocked client and asserts one request. Logged as
  `gemini generate_content request #1 model=… fps=… media_resolution=… prompt=p1`. A 429 retry
  increments the counter **on purpose** — a hidden retry would defeat the instrument.
- **Request payload asserted, not the signature.** The fake client captures `model`, `contents`,
  and `config`, so the tests check that `media_resolution` arrives as
  `MediaResolution.MEDIA_RESOLUTION_LOW` on the config and that `fps` arrives on
  `Part.video_metadata.fps` of the video part. `"medium"` and `fps=2.0` are tested as per-call
  overrides that leave the module defaults untouched.
- **Structured output** via `response_mime_type="application/json"` + `response_schema`. There is
  no fence-stripping anywhere in the parser: a fenced or prose body raises. Two wire models rather
  than reusing `ShotUnderstanding` — see D-019 — which also lets the hint fields be dropped from
  the schema entirely when boundaries are supplied.
- **D-010 wired end to end.** Boundaries render as `idx t_start-t_end` lines; the prompt says do not
  merge, split, invent, or skip. Out-of-range **and** duplicate `shot_index` both raise loudly; a
  short list only warns, because a missing caption is visible and recoverable while a misnumbered
  one is neither. Output sorted by `shot_index`. The `shots=None` fallback still works and keeps
  `t_start_hint` / `t_end_hint`.
- **Prompt as module constants with `PROMPT_VERSION = "p1"`** — five scoring bands, scores
  calibrated *within this video*, an explicit statement that a run of identical scores is a failure
  of the task, `moment_reason` as evidence in ≤15 words that never restates the caption, and a
  reminder to use the audio.
- **Backoff** via `tenacity`: 5 attempts, 4s doubling to a 60s ceiling, 429 only. Non-429 errors are
  not retried. Final failure is a `RuntimeError` naming the step and quoting the server's text.
- **File API lifecycle:** upload, poll while `PROCESSING` with a 300s deadline, refuse anything that
  is not `ACTIVE`, and delete the handle in a `finally` so the failure path cleans up too. A failed
  delete warns instead of masking the real result.
- **Observability for T009:** token usage (`prompt`/`output`/`thoughts`/`total`), upload and call
  timings separately, and the `editorial_score` distribution
  (`min/median/max/stdev/distinct@2dp`) with a **warning below stdev 0.05** — the "everything is
  0.8" failure the task names, caught automatically rather than by eye.

**`tests/test_gemini.py` — 47 fast tests + 1 slow.** Guards (missing file, unset key, blank key,
bad fps, unknown resolution, empty shot list); the one-call rule; every payload field; both prompt
paths; six response-failure paths; 429 retried-then-succeeded, persistent-429, non-429-not-retried,
and 429-at-upload; the full File API lifecycle including the timeout and the failed delete; and the
three log lines T009 reads.

**Gates:** `uv run pytest -m "not slow"` **101 passed** (was 54); `ruff check .` clean; `mypy elvideo`
strict clean, 12 files. The slow marker now holds 3 tests: 2 pass, and the new real-API one **fails**
— see below.

### Not done / deferred

- **The live run never happened.** `tests/test_gemini.py::test_real_video_one_call_spread_scores`
  fails on the shortest decisive line:

  ```
  google.genai.errors.ClientError: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message':
  'Your prepayment credits are depleted. ...'}}
  ```

  So these stay unverified, all four marked `[~]` in the task file: real token usage against the
  ~30K target; whether `editorial_score` actually spreads under prompt `p1`; whether
  `moment_reason` reads as evidence rather than a second caption; and the `shots=None` path against
  the real model. The instrumentation and the assertions for all four are written and passing
  against mocks — what is missing is one call.
- **No workaround attempted.** Switching model, provider, or tier would break the pinned
  `gemini-3.5-flash` constraint and make the A/B measure something else.
- **Prompt not iterated.** `p1` is the first version and has never seen a model response. The
  `PROMPT_VERSION` constant exists precisely because that is expected to change.
- No commit — the user drives git.

### Decisions made

- **D-019 (new)** — Gemini call settings and the prompt version. The spec locks model /
  `media_resolution` / `fps` / structured output / backoff but is silent on sampling, which changes
  the output just as much. Pinned as constants and guarded by a test: `TEMPERATURE=0.4`, `SEED=7`,
  `THINKING_LEVEL=LOW`, `RETRY_MAX_ATTEMPTS=5`, `PROMPT_VERSION="p1"`. **Why 0.4 rather than 0.0:**
  near-greedy decoding is what *produces* the "everything is 0.8" clustering the task calls a
  prompt bug, while 1.0 makes the stage non-repeatable. The choice is falsifiable rather than
  taste — the spread is logged every run and asserted in the slow test. Also records why the
  response schema is two private wire models instead of `ShotUnderstanding`.
- **D-020 (new)** — the 429 backoff wraps the **File API upload** as well as `generate_content`.
  Found by running it: with a dead key the 429 arrives at upload time, before any generation, and
  unwrapped that surfaced as a raw SDK traceback with none of the actionable text. Uploads are
  deliberately **not** counted by `generate_call_count()` — that counter is the instrument behind
  the one-call rule and folding uploads into it would make the number meaningless.
- **D-021 (new, open — needs the owner)** — the key has no quota. Isolated rather than assumed: a
  5-token text-only call on `gemini-3.5-flash` fails identically, so it is not the video, the file
  size, the request shape, or a transient per-minute cap. An earlier attempt with a stale key failed
  differently (`400 API_KEY_INVALID`), which confirms the `.env` key is now read and accepted — it
  is the project behind it that is empty. `docs/IDEA.md` assumes free tier throughout; this key's
  project is on **prepay billing**, a different quota pool that does not fall back to the free tier.
- No conflict with `docs/IDEA.md` to log under the CLAUDE.md conflict rule.

### Blockers

- **D-021 — the API key.** `progress.json.blockers` is non-empty again for the first time since
  T003. **What would unblock it:** an API key from an AI Studio project with **billing not enabled**
  (that is the free tier) in `.env`, then
  `uv run pytest tests/test_gemini.py -m slow --log-cli-level=INFO`. That one command settles every
  `[~]` criterion in T004 and produces the token number the ~30K target is checked against.
- **T009 is blocked by the same thing** — an end-to-end run with no Gemini call proves nothing about
  the Path B claim.
- **T007 is not blocked.** `understand()`'s signature and output are settled, so `build.py` can be
  written and tested against a mocked understanding pass.
- The D-016 owner follow-up (CLAUDE.md hard constraint 6) is still open and still blocks nothing.

### Next

- **T006 then T007**, both in `prompts/session-start/005-build-orchestrator.md`. **T006 first** —
  `validate_index()` is the last stub in `elvideo/schema/` and T007 cannot meet its
  "validates before it is written" criterion without it. Caught after the first draft of the prompt
  put T007 first and T006 in a footnote.
- **T007 — `build.py`**, the orchestrator.
  Alignment is an index lookup on `shot_index` (D-010), must pass `shot_id=shot.id` to
  `score_shot()` (D-018), must populate `index_meta.scene_detector` / `.scene_threshold` from the
  values actually passed to `detect_shots()` (D-013), and must log **per-stage** timing.
- In parallel, whenever the owner has a free-tier key: rerun the T004 slow test and close D-021.

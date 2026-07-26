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

---

## 2026-07-26 — T006 + T007 · the validator, then the orchestrator

**Task(s):** T006 — `validate_index()`; T007 — `build.py`, the join point
**Status at end:** T006 **`done`**, every criterion ticked. T007 **`partial`** — implemented and
measured on the real clip, but the `<5 min wall-clock` criterion cannot be settled while the
Gemini stage is mocked (D-021), so it is marked `[~]` rather than ticked.

### Done

**T006 — `elvideo/schema/__init__.py`.**

- `validate_index(doc)` on `jsonschema`, against a **plain dict with no pydantic involvement** —
  the JSON Schema is the interoperability artifact (D-009), and validating through pydantic would
  only prove pydantic agrees with itself.
- The validator is compiled once (`@lru_cache`) and its dialect comes from the schema's own
  `$schema` key rather than being hardcoded.
- **Errors carry a path.** Messages are prefixed with the JSON path
  (`$.shots[42].editorial_score: 1.5 is greater than the maximum of 1`), the first error in
  *document* order is the one raised, and the total violation count is stated. At 117 shots,
  `ValidationError.message` alone does not say which shot.
- **`t_end > t_start` is enforced in code, not in the schema** — see D-022 below. Same exception
  type, same path shape, so callers cannot tell which half rejected the document.
- `tests/test_schema.py` — **31 tests** (was 8): minimal valid document, Path-A-shaped document
  (both judgment fields null, `path_variant: "local"`), pydantic round-trip, extra key at top level
  and inside a shot, backwards and zero-length shots, five malformed shot ids, `shot_1000`,
  missing detector settings, `transcript: null`, unknown `path_variant`, document-order error
  reporting.
- **`embedding` "no code writes to it" is now enforced, not asserted in prose.**
  `test_no_code_writes_the_embedding_field` scans `elvideo/` outside `schema/` for `embedding=` or
  `"embedding":` and fails on a hit.

**T007 — `elvideo/index/build.py`, full implementation.**

- `build_index(path, work_dir="work", fps=..., media_resolution=..., *, threshold=...)`.
  `threshold` is keyword-only — the same extend-a-fixed-signature pattern as D-012 / D-018 — so
  `index_meta.scene_threshold` can carry the value **actually passed to `detect_shots()`** (D-013)
  rather than a re-read of the module constant.
- Stage order probe → shots → transcript → Gemini → quality → join → validate → write, each one
  timed by a `_stage()` context manager that logs its own line, plus a summary line with the
  breakdown and the total. Timing happens in `finally`, so a stage that *fails* still reports how
  long it ran — which is the number you want when a stage blew the budget.
- **The one-call rule is checked, not assumed.** `_assert_one_call()` reads
  `gemini.generate_call_count()` back after the understanding stage and aborts on anything but 1.
- `align_understanding()` is an **index lookup on `shot_index`** (D-010), not an overlap match.
  Out-of-range and duplicate indices raise; a short response only warns and leaves those shots with
  their defaults; an empty response still yields a full valid index. `t_start`, `t_end` and `id` are
  never touched.
- `is_candidate` from `CANDIDATE_THRESHOLD = 0.65` (D-023). A null score is never a candidate.
- Writes via a temp file plus `os.replace`, so a crash mid-write cannot truncate a good index.
  Validation runs **before** the write, so a failure leaves nothing behind.
- `tests/test_build.py` — **33 fast + 1 slow.** Alignment gets synthetic inputs and no mocks
  (1:1, 3 judgments for 120 shots, none at all, out-of-range at 4/40/999, duplicate, more segments
  than shots, tag-list aliasing, the short-response warning). `build_index` runs with every
  producer stage faked: stage order checked against both the call record *and* the log lines,
  call-count abort at 0/2/117, `index_meta` with non-default values on every axis, transcript
  slicing, `is_candidate` at the 0.65 boundary, `shot_id` passed to `score_shot` (D-018),
  `embedding` null, per-stage logging, no file left after a validation failure.

**Measured on `in.mp4` — the full pipeline, Gemini mocked (D-021):**

| Stage | Wall-clock |
|---|---|
| probe | 0.06s |
| shots | 31.68s |
| transcript | 102.75s |
| **understand** | **0.00s — MOCKED, no live call** |
| quality | 23.85s |
| join | 0.01s |
| validate | 0.08s |
| write | 0.02s |
| **Total** | **158.5s** (a second warm run under pytest: 131.8s) |

Output: 117 shots, gapless, `t_start=0.0` → `t_end=428.04`; 1436 words; 7 silent shots; 117
keyframes whose names match the index ids exactly; `work/footage_index.json` at 177 KB, passing
`validate_index()`. Container/stream skew is exactly as D-014 predicted (428.106 vs 428.04).

**Gates:** `uv run pytest -m "not slow"` **155 passed** (was 101); slow marker now 4 — 3 pass
(transcribe, quality, build), 1 still blocked by D-021; `ruff check .` clean; `mypy elvideo` strict
clean, 12 files.

### Not done / deferred

- **The `<5 min wall-clock` criterion is not ticked.** 158.5s is 53% of the 300s budget, but it is
  a **floor, not the measurement**: the missing stage is the entire point of Path B. Roughly 141s
  of headroom remains for the upload plus one `generate_content` call. Re-measure when D-021 clears.
- **`work/footage_index.json` on disk is a mocked artifact.** Every caption reads
  `[MOCKED] no live Gemini call was made for shot N` and every `moment_reason` reads
  `[MOCKED] placeholder judgment, D-021`, deliberately, so the file cannot be mistaken for a real
  Path B index by a later session. `editorial_score` values in it are a synthetic sawtooth; the
  "42 of 117 candidates" it produces measures the generator, not the model.
- **Concurrency stays out of scope**, as the task file directed: probe/shots/transcript/gemini are
  independent and could overlap. Get the sequential version correct and timed first.
- `docs/architecture.md` and `docs/schema.md` untouched — this session implements what they already
  describe, it does not change the contract's shape.
- No commit — the user drives git.

### Decisions made

- **D-022 (new)** — `t_end > t_start` is enforced in `validate_index()`, **not** in the JSON
  Schema, because draft 2020-12 cannot compare two sibling properties. **Stated cost:** the two
  artifacts are no longer equivalent — anyone validating the file with a generic tool (`ajv`,
  `check-jsonschema`, a Path A repo in another language) gets a *weaker* check than we do, which is
  the exact asymmetry D-009 exists to prevent. Pinned by
  `test_schema_alone_does_not_catch_backwards_timings`, which asserts that raw `jsonschema`
  **accepts** the backwards document — so if a future dialect ever makes the constraint
  expressible, that test goes red and the Python half can be deleted.
- **D-023 (new)** — `is_candidate` is `editorial_score >= 0.65`, read off the rubric rather than
  chosen by feel: 0.65 is the floor of the **strong** band in `gemini.SYSTEM_INSTRUCTION`
  (0.65–0.84 strong, 0.85+ hero, 0.40–0.64 "useful connective tissue"). If the bands are re-cut,
  this constant moves with them — they are one decision, not two. Not recorded in the artifact:
  `index_meta` has no field for it and adding one carries D-013's contract cost.
- **Tooling:** `types-jsonschema` added as a dev dependency. `jsonschema` ships no inline types and
  `mypy` is configured strict; stub-only package, matched to the runtime version (4.26).
- No conflict with `docs/IDEA.md` to log under the CLAUDE.md conflict rule.

### Blockers

- **D-021 — still the only blocker, and it now touches three tasks.** T004's four `[~]` criteria,
  **T007's wall-clock criterion**, and all of T009. **What would unblock it:** a key from an AI
  Studio project with **billing not enabled**, then
  `uv run pytest tests/test_gemini.py -m slow --log-cli-level=INFO`, then re-run
  `tests/test_build.py -m slow` without the `understand` monkeypatch.
- **T008 is not blocked by it** — the CLI is a thin wrapper over `build_index`, and its criteria are
  about argument parsing, exit codes and help text.
- The D-016 owner follow-up (CLAUDE.md hard constraint 6) is still open and still blocks nothing.

### Next

- **T008 — `cli.py`**: `prompts/session-start/006-cli.md`. Thin wrapper; the two Typer traps from
  the bootstrap session (single-command collapse, non-ASCII help strings on a cp1252 console) are
  recorded in the task file and must not be reintroduced.
- Then T009, which needs the key. And whenever the owner has one: rerun both slow tests and close
  D-021.

---

## 2026-07-26 — T004 live verification · D-021 cleared, prompt iterated to `p2`

**Task(s):** T004 — the four criteria left `[~]` when the API key had no quota
**Status at end:** T004 **`done`**. No blockers anywhere in `progress.json` for the first time.

### Done

- **Owner supplied a working free-tier key. D-021 resolved.** First live run passed on the first
  attempt with no code changes: `gemini generate_content request #1 model=gemini-3.5-flash fps=0.5
  media_resolution=low prompt=p1`, 117 shots, one call, upload deleted.
- **Prompt iterated `p1` → `p2` — and this was the real work of the session.** `p1` technically
  passed and that was the problem: 11 distinct scores, **117/117 of them on the 0.05 grid**, a
  ceiling of 0.75, and 97 of 117 shots inside 0.50–0.65. The model refused the hero band on
  ordinary footage and picked from a dozen round numbers. `p2` adds rank-before-you-score, an
  explicit "the best shot here IS the best shot here", two-decimal precision with no score shared by
  more than ~10 shots, and "a category label is not evidence". Result on the same clip: **37
  distinct values, 32/117 on the grid, hero band reached (0.85)**. Full table in **D-024**.
- **Regression guard tightened to match.** The slow test now asserts *granularity* — ≥15 distinct
  values and <90% on the 0.05 grid — which `p1` fails on every run. The first attempt also raised
  the range threshold to 0.4; a later run scored min 0.50 and failed it, so **the range assertion
  was put back to 0.3 and the reason written into the test**: whether the model calls the outro
  frames unusable genuinely varies run to run, and `seed` is best-effort. Granularity is the signal
  that actually detects clustering.
- **`moment_reason` verified by reading all 117**, not by sampling: *"Hero shot demonstrating
  real-world rear seat width with three adults"*, *"Third exterior pan of the same car"*. Evidence,
  not a second caption. 4 of 117 still open with a category label — recorded as accepted.
- **Token cost measured and the spec's target corrected** — see **D-025**. Three runs: **38,684 /
  39,174 / 38,390** total, prompt ~27.7K of it. The spec's ≈30K (and D-003's ~14K for this clip)
  counted sampled frames and **omitted the audio track**, which Gemini bills per second regardless
  of `fps` or `media_resolution`.
- Final state: `pytest -m "not slow"` **155 passed**, `ruff` clean, `mypy` strict clean, and the
  gemini slow test **1 passed** for real (~2 min, ~38K tokens per run).

### Not done / deferred

- **The `shots=None` free-segmentation path still has never run live.** It costs a second call on
  the same clip and every consumer in this repo uses the boundary path. Written into T004 as
  explicitly not-verified rather than quietly ticked — it was never one of the task's acceptance
  criteria.
- **T007's `<5 min` criterion is still unmeasured for real.** It is no longer *blocked* — the key
  works — but nobody has yet run `build_index` end to end with the live understanding stage. The
  arithmetic: 158.5s mocked + 96.8s for the real stage ≈ **230–255s against a 300s budget**. Inside
  it, but not by much, and the projection is not the measurement.
- Four live calls were spent this session (p1 run, p1 dump for inspection, p2 run, final green
  gate). No commit — the user drives git.

### Decisions made

- **D-021 → resolved.** Kept in full in the log rather than deleted: the diagnosis is the reusable
  part. If it recurs it is the *project's billing mode*, not the code.
- **D-024 (new)** — the `p1` → `p2` iteration with the measured before/after, why granularity is
  the assertion that matters, and the run-to-run variance that `seed` does not remove.
- **D-025 (new)** — real token cost ~38K for a 7:08 clip, ~54K projected for 10 min, with the audio
  explanation. **T009 should assert against ~40K for this clip, not 30K.** Deliberately not "fixed"
  by trimming inputs — raising the target to match reality beats making a wrong estimate come true.
- **D-019 updated** — no longer marked unverified; `PROMPT_VERSION` is now `p2`.

### Blockers

- **None.** `progress.json.blockers` is empty and `open_decisions` is empty.
- The D-016 owner follow-up (CLAUDE.md hard constraint 6 describing a Path A that does not exist) is
  still open and still blocks nothing.

### Next

- **T008 — `cli.py`**: `prompts/session-start/006-cli.md`. Needs no key.
- Then **one live CLI run closes T007's last criterion and feeds T009 at once** — same ~38K tokens,
  two results.

---

## 2026-07-26 — T008 · `cli.py`, and the live run that closed T007

**Task(s):** T008 — `cli.py`, the entrypoint (and T007's last open criterion, closed as a side effect)
**Status at end:** T008 **`done`**. T007 **`done`**. `completed_tasks` is now everything except T009.

### Done

- **`elvideo/cli.py` implemented** — the last stub in the repo is gone. Options: `--work-dir`,
  `--fps`, `--media-resolution`, `--threshold`. `.env` loaded via `python-dotenv`, per-stage timing
  rendered through a `RichHandler`, exit 1 on every failure path, exit 2 from Typer on a bad option
  value. `build.py` was **not** touched — the module is argument parsing plus two fail-fast guards.
- **`tests/test_cli.py` — 36 tests**, `build_index` mocked in all of them. Covers the argument
  surface, the exit-code map, work-dir creation, stderr routing, the log filtering, and both
  bootstrap traps (the Typer single-command collapse and the cp1252 help strings).
- **The live end-to-end run passed, first attempt, no code changes:**
  `python -m elvideo index in.mp4` → `work/footage_index.json`, **234.7s**, 117 shots, 1436 words,
  43 candidates, **one** `generate_content` call, **38,956 tokens**, exit 0. Per stage: probe 0.05s,
  shots 20.95s, transcript 107.76s, understand 86.77s (upload 18.7s + call 64.9s), quality 19.04s,
  join 0.01s, validate 0.06s, write 0.02s. `editorial_score` min 0.10 / median 0.61 / max 0.85,
  37 distinct at 2dp.
- **T007's `<5 min` criterion is therefore closed** — 234.7s, 78% of the 300s budget, measured
  rather than projected. The artifact on disk is now a **real** index: 0 `[MOCKED]` captions,
  `validate_index()` clean, `index_meta` reads `scene_threshold: 27.0`, `sample_fps: 0.5`.
- **Two output defects the live run exposed, both fixed:**
  1. **Em dashes in messages that reach the terminal** rendered as `?` on the cp1252 console — the
     same trap as the help strings, one layer down, and invisible until a CLI existed to print
     them. Five messages in `gemini.py`, one in `probe.py`, one in `transcribe.py` are now ASCII.
     Docstrings deliberately untouched: nothing prints them.
  2. **`lightning` printed at INFO despite the root logger being at WARNING**, because it sets a
     level on its own logger at import. Fixed with a filter on the rich handler; third-party
     `WARNING` and above still gets through.
- Gates: `uv run pytest -m "not slow"` **191 passed**, `uv run ruff check .` clean,
  `uv run mypy elvideo` strict clean (12 files).

### Not done / deferred

- **The `<5 min` number is measured on a 7:08 clip, not a 10:00 one.** Transcription and quality
  scale with duration, so a true 10-minute video projects to roughly **300–330s — at or just over
  the budget**. T007 is ticked because `in.mp4` is the agreed test video (D-003), but the headroom
  is thinner than "234.7 < 300" suggests, and the A/B writeup should say so rather than quote the
  raw number. Recorded in `tasks/T007-build-orchestrator.md` next to the tick.
- **The slow tests were not re-run this session** (last green 2026-07-26, 4/4). The live CLI run
  covers the same ground for the gemini path and costs the same quota, so re-running them would
  have spent ~38K tokens for a second copy of an answer already in hand.
- `--verbose` / `--quiet`, a JSON output mode, and a progress bar: none are in the criteria, each
  is a reason for the module to grow. Left out on purpose.
- The ffmpeg/h264 `mmco: unref short failure` chatter still reaches the terminal. Native code
  writes it to the process's stderr, below Python's logging — not fixable from `cli.py`.
- No commit — the user drives git.

### Decisions made

- **D-026 (new)** — three CLI choices that were not in the acceptance criteria:
  (1) **`--threshold` is exposed**, because D-012 calls the detector threshold a per-video knob in
  the same breath as `fps` and a knob nobody can reach is not a knob;
  (2) **`gemini.check_api_key()` is now public** and the CLI preflights it, so a missing key fails
  in 0.1s instead of after the ~2.5-minute transcription stage — a four-line wrapper over the
  existing private `_api_key()`, so there is still one source of the message;
  (3) **per-stage timing is rendered by attaching a handler**, not by changing `build_index` to
  return a timings dict — the orchestrator stays callable without inheriting our presentation.
  The entry also records the `pyproject.toml` tooling change:
  `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls = ["typer.Argument", "typer.Option"]`,
  because B008 already ignored `typer.Option` on `str`/`float` parameters and fired only on the
  enum-annotated one.
- No conflict with `docs/IDEA.md` to log under the CLAUDE.md conflict rule.

### Blockers

- **None.** `blockers` and `open_decisions` are both empty.
- The D-016 owner follow-up (CLAUDE.md hard constraint 6 describing a Path A counterparty that does
  not exist) is still open and still blocks nothing.

### Next

- **T009 — E2E validation**: `prompts/session-start/007-e2e-validation.md`. Most of its evidence
  already exists from this session's live run; what is missing is the **run report in a tracked
  file** (`work/` is gitignored), the **five-shot hand spot-check**, and the machine recorded.
  Token assertions go against **~40K, not the spec's 30K** (D-025) — and that miss is itself one of
  T009's findings.

---

## 2026-07-26 — T009 · E2E validation, and the defect it found

**Task(s):** T009 — E2E validation on the A/B test video
**Status at end:** T009 **`done`** — 8 criteria pass, 2 fail, 1 not-verifiable, all recorded.
**T011 opened** and is now the only remaining task.

### Done

- **`docs/run-report.md` written and tracked** — the deliverable T009 actually owed. Carries the
  command, the machine (Ryzen 7 5800H, 8C/16T, 15.3GB, Windows 11, cpu-only torch 2.8.0, Python
  3.12.11, ffmpeg 8.1.1), the eight per-stage timings, tokens against the corrected target, the
  call count read from the counter, the score distribution, the 17-shot spot-check table, and a
  pass/fail/not-verifiable verdict with a reason for every criterion.
- **The pipeline's structural claims all verified against the existing live run** — no re-run, the
  recorded numbers were current and a second run would have spent ~39K tokens to reproduce them:
  - schema validity checked **three** independent ways — `validate_index()`, `jsonschema` draft
    2020-12 against `elvideo/schema/footage_index.schema.json`, and `pydantic` — all clean;
  - **frame accuracy verified numerically**, not assumed: all 234 boundary values are exact
    multiples of 1/25s (**0** off-grid), shots are contiguous, and they cover 10,701 of the
    container's 10,701 frames;
  - 1 Gemini call, 38,956 tokens, 0×429, 234.7s, 117 shots, 1,436 words, 43 candidates, and the
    `is_candidate` flag agrees with the 0.65 threshold on all 117 shots;
  - score spread confirmed: 37 distinct at 2dp, 32/117 on the 0.05 grid, largest cluster 10.
- **The hand spot-check was done properly and it failed.** 17 shots compared against their
  extracted keyframes: **2 clean matches, 2 partial, 13 mismatches.** The worst is `shot_059`, the
  clip's top-scored shot at 0.85 — captioned "three men sit side-by-side in the back seat and give
  a thumbs up", frame shows the presenter at an open boot with nobody in the car.
- **The obvious innocent explanations were ruled out before blaming the model.** Frames
  re-extracted with `ffmpeg -ss <midpoint> -frames:v 1` for shots 025, 059 and 105 are the same
  images `quality.score_shot()` wrote, so keyframe sampling and shot boundaries are both correct.
  `transcript` is unaffected — it joins by time window from WhisperX and matches the picture on the
  same shots whose captions are wrong. **The classical half of the pipeline is sound; the LLM half
  is misfiled against it.** It is also not a constant offset (`shot_022`'s caption lands on
  `shot_025`, +3; `shot_048`'s describes what `shot_033` shows, −15), so no index shift repairs it.
- **`tasks/T009-e2e-validation.md`** updated: status `done`, every criterion ticked or explicitly
  failed with its evidence, plus an Outcome note.
- **`tasks/T011-caption-shot-alignment.md` created** and registered in `tasks/backlog.md`.
- Gates: `uv run pytest -m "not slow"` **191 passed**, `uv run ruff check .` clean,
  `uv run mypy elvideo` strict clean (12 files).

### Not done / deferred

- **The alignment defect is not fixed, on purpose.** T009's contract is to measure, and its own
  Notes section says a failing criterion is a legitimate outcome. Fixing it here would have meant
  spending free-tier quota on prompt experiments under a task that exists to report numbers.
  → **T011**.
- **The cause is not diagnosed.** Two hypotheses are recorded in D-027 and neither is tested:
  (1) Gemini's timestamps are second-granular while the median shot is **2.68s** and **36 of 117**
  are under 2s; (2) at `fps=0.5` there are ~214 frames for 117 shots — 1.8 each, and the sub-2s
  shots get one frame or none. 17 hand-checked shots prove the problem is real and are not enough
  to attribute a cause.
- **The spot-check sample is hand-picked, not systematic.** Shots were chosen to span the score
  range and the timeline, which is fine for finding a defect and wrong for measuring one. T011's
  first criterion is a repeatable sample with a fixed rule so a later run compares like with like.
- **The slow tests were not re-run** (last green 2026-07-26, 4/4). Nothing in this session touched
  code — only Markdown, JSON state and one new task file.
- **No re-run of the pipeline**, and none was needed: no code changed, so the recorded numbers
  still describe the artifact on disk.
- No commit — the user drives git.

### Decisions made

- **D-027 (new, `open`)** — Gemini's per-shot judgments attach to the wrong `shot_index`. Logged as
  a **measurement, not a diagnosis**: the numbers, what was ruled out, the two untested hypotheses,
  and the constraint that shapes any fix (one call per video — a per-shot loop is the design this
  project exists to avoid and would blow the 10 RPM cap on 117 shots). Left `open` deliberately;
  it closes when T011 attributes a cause.
- **T009 closes as `done` with two failing criteria**, rather than as `partial`. Its acceptance
  criteria are a checklist to *measure and record*, and all twelve were measured and recorded. A
  `partial` would imply measurement work is outstanding, which it is not — remediation is
  outstanding, and that has its own task.
- **Reported the failure rather than tuning around it**, per the task file and the session prompt:
  the useful output is the measured number plus the reason, not a run tuned until an estimate comes
  true. Nothing was adjusted to improve either failing criterion.
- No conflict with `docs/IDEA.md` to log under the CLAUDE.md conflict rule. The ~30K token figure
  in § *Gemini call settings* is superseded by D-025, which already records it.

### Blockers

- **None.** `blockers` is empty and the API key works.
- `open_decisions` now holds **D-027** — open because the cause is untested, not because anything
  is waiting on a human. It does not block T011; it *is* T011's subject.
- The D-016 owner follow-up (`.claude/CLAUDE.md` hard constraint 6 and `docs/IDEA.md` still
  describe the co-founder's Path A repo as a live sync risk) is still open and still blocks
  nothing. It is why criterion 7 is marked not-verifiable rather than failed.

### Next

- **T011 — caption ↔ `shot_index` alignment**: `prompts/session-start/008-caption-alignment.md`.
  The repo's top defect and the only remaining task. Measure first against the **existing**
  `work/footage_index.json`; any fix stays inside **one** Gemini call; budget the live runs, each
  is ~39K tokens and ~4 minutes.


---

## 2026-07-26 — T011 · caption ↔ `shot_index` alignment: measured, improved, not closed

**Task(s):** T011 — Gemini judgments attach to the wrong `shot_index`
**Status at end:** **`partial`** — the defect is measurably smaller and the cause is partly
attributed. **Criterion 2 (≥12/17) and criterion 3 (`shot_059`) fail.** T011 stays open by its own
wording: "a smaller improvement is a legitimate result to record, but it does not close this task."

### Done

- **The measurement is now repeatable, which it was not before.** `elvideo/eval/alignment.py` +
  `elvideo/eval/alignment_sample.json` + `elvideo/eval/__init__.py`. One Gemini call grades all 17
  `(keyframe, caption)` pairs as match / partial / mismatch against a frozen sample; run it with
  `python -m elvideo.eval.alignment work/footage_index.json`. T009's number was a human reading
  frames and could not be reproduced, so nothing could be shown to improve against it.
- **The grader was validated before being trusted.** On the untouched T009 index it returned
  **2 match / 1 partial / 14 mismatch** and agreed with the human column on **16 of 17** without
  being shown it. The single disagreement is `shot_116` (human *partial*, grader *mismatch*).
- **Prompt `p2` → `p3`** in `elvideo/index/gemini.py`: locate each shot by its timestamp rather
  than by counting cuts (stated with the mechanism — this detector cuts more finely than a person
  would, so a counting model drifts out of step), hints now requested on the shot-list path too,
  a self-check, and an honest-uncertainty escape.
- **Three live runs, one Gemini call each, call count read from the counter every time:**

  | Run | Prompt | Clean match /17 | Tokens | Score range |
  |---|---|---:|---:|---:|
  | baseline (T009 artifact) | `p2` | **2** | 38,956 | 0.75 |
  | 1 | `p3` | **13** | 42,764 | 0.27 |
  | 2 | `p4` | **4** | 41,402 | 0.60 |
  | 3 | `p3` replicate | **6** | 42,131 | 0.48 |

- **`hint_drift()` and `_check_hints()`** added to `gemini.py` — public detector plus a warning
  above 25% drift. **`gemini.is_rate_limited()` promoted to public** so the eval module can build
  its own retryer without routing through `_generate_with_backoff`, which would inflate the
  one-call-per-video counter.
- **`docs/run-report.md`** gained a full T011 section sitting directly beneath the T009 numbers:
  method, the four-row results table, the negative result on hints, the `p4` trade-off, the
  variance finding, the three named shots, and a 9-row criteria table with two FAILs and one
  PARTIAL.
- **Tests:** `tests/test_alignment_eval.py` (15 new) and a hint-drift block in
  `tests/test_gemini.py` (5 new). Two `p2`-era tests were rewritten rather than deleted:
  `test_hints_are_not_requested_when_boundaries_are_given` → `test_hints_are_requested_on_both_paths`,
  carrying the reason the old judgment was wrong.
- **Gates:** `uv run pytest -m "not slow"` **211 passed** · `uv run ruff check .` clean ·
  `uv run mypy elvideo` strict clean (14 files).

### Not done / deferred

- **The task's headline criterion is not met and this is the main finding, not a footnote.**
  `p3` scored 13/17 and then **6/17 on a replicate of the identical configuration** — same seed,
  same temperature, same boundaries. The honest summary is **"2/17 → 6–13/17, n=2"**.
- **D-027 hypothesis 2 — frame starvation — is still completely untested.** `fps` was never raised
  from 0.5. That is the one lever with a plausible mechanism that has not been pulled, ~+14K
  tokens per run, and it is the obvious next move.
- **`shot_059` never matched its frame under any prompt.** It stopped inventing three passengers
  (`p3`: "the presenter climbs into the boot") and dropped off the top score to 0.69, but the frame
  is the presenter standing *outside* the boot. Criterion 3 fails on this shot alone.
- **The hint detector does not detect the thing it was built for.** `hint_drift()` returns
  **0 of 117** on every run, including the ones where two-thirds of sampled captions describe other
  footage — the model echoes our own timestamps back regardless of where it looked. Kept as a
  regression guard, not as the answer to criterion 6.
- **The slow tests were not re-run** (4 total, last green 2026-07-26). One of them is now a
  coin-flip: it asserts `max(scores) - min(scores) > 0.3`, and `p3` produced **0.27** on run 1 and
  0.48 on run 3. Left at 0.3 deliberately — loosening a D-024 regression guard on two samples would
  be tuning the test to the run. **Expect it to fail intermittently until someone measures it
  properly.**
- **Only 3 live index runs were spent**, the agreed budget, plus 4 cheap grading calls (~3K tokens
  each). No 429 at any point.
- No commit — the user drives git.

### Decisions made

- **D-028 (new, `resolved`)** — `p3`: the prompt anchors on timestamps and hints are requested on
  both paths. Supersedes the shot-list half of D-024. Records the `p4` experiment and why it was
  reverted: it repaired the score spread (range 0.60, 39 distinct) and **collapsed alignment to
  4/17** — the two instructions compete for the model's attention. Also carries the two small
  API changes (`is_rate_limited`, `hint_drift` public).
- **D-029 (new, `resolved`)** — caption/frame agreement is measured by a Gemini judge over a frozen
  17-shot sample. Argues the grader-is-a-model objection explicitly (grading one still against one
  sentence is the easy half of attributing a moment across 7 minutes) and rests the case on the
  16/17 calibration rather than on the architecture. Records the sample's known weakness: it is
  T009's **hand-picked** 17, kept because criterion 2 is written as "of 17" against a published
  baseline, so comparability beat rule-generation.
- **D-027 updated, deliberately left `open`** — cause *partly* attributed. Hypothesis 1 supported
  (the model was counting, not locating); hypothesis 2 untested; and a new finding that closes off
  the most promising detection route (self-report is not independent evidence). It closes when
  hypothesis 2 is measured or the fix is stable at ≥12/17, not because the numbers moved.
- **Shipped `p3` despite it not closing the task**, because both of its runs beat the baseline and
  +8% tokens is trivial against the 250K TPM cap. Recorded as an improvement with a measured range,
  never as a fix.
- **Chose to spend the third live run replicating `p3` rather than trying a fourth prompt.** The
  replicate is what turned a headline "13/17, criterion met" into the correct "6–13/17, criterion
  failed" — the more useful outcome, and the reason the variance finding exists at all.
- No conflict with `docs/IDEA.md` to log under the CLAUDE.md conflict rule.

### Blockers

- **None.** `blockers` is empty, the API key works, no 429 was seen across 7 calls.
- `open_decisions` holds **D-027** only — open because hypothesis 2 is unmeasured, not because
  anything waits on a human.
- The D-016 owner follow-up (`.claude/CLAUDE.md` hard constraint 6 and `docs/IDEA.md` still
  describe a Path A counterparty that does not exist) is still open and still blocks nothing.

### Next

- **T011, continued** — `prompts/session-start/009-fps-and-alignment-variance.md`. One flag left:
  `--fps 1.0`, the untested D-027 hypothesis 2. **Budget 2–3 runs per setting, not one** — this
  session proved a single run cannot rank two configurations on this measure. Grade every run with
  `python -m elvideo.eval.alignment`; do not eyeball captions.

---

## 2026-07-26 — T011 continued · `fps` measured, D-027 resolved, and the real quota found

**Task(s):** T011 — D-027 hypothesis 2 (frame starvation at `fps=0.5`)
**Status at end:** **`partial`**, unchanged and correctly so. **Criterion 2 (≥12/17) and criterion 3
still fail.** But D-027 is now **`resolved`**: both hypotheses are measured, and the defect has a
bounded ceiling instead of an open question.

### Done

- **Hypothesis 2 tested properly — three runs per setting, not one.** A ~110-line scratchpad driver
  re-runs *only* `understand()` against the existing `work/footage_index.json` (boundaries,
  transcripts and quality scores are already correct and cost 150s of CPU to recompute), then each
  index is graded by `python -m elvideo.eval.alignment`. ~100s per run instead of 235s.

  | `fps` | Clean matches /17 | Mean | Tokens (mean) | Score spread |
  |---|---|---:|---:|---|
  | **0.5** | 13, 6, 13 | **10.7** | **42,553** | clustering warning never fired |
  | 1.0 | 9, 8, 9 | 8.7 | 55,500 (+30%) | warning fired on 2 of 3 (stdev 0.048, 0.043) |

  **Frame starvation is not the cause.** Doubling sampled frames (~1.8 → ~3.7 per shot) buys
  nothing on attribution, costs 30% more tokens, and *flattens the editorial scoring it was not
  meant to touch*. Call count **1** on all six runs, read from the counter.

- **`seed=7` turns out to be exactly reproducible, which rewrites last session's variance story.**
  This session's `fps=0.5` run reproduced session 008's run 1 **bit-identically** — all 117
  captions, all 117 `editorial_score` values, the total token count (42,764), even the grading
  call's 7,721 — hours apart. So the 6/17 replicate was **a second deterministic outcome, not a
  noisy draw around a mean**. At `fps=0.5` exactly two outcomes have ever been seen: A (13/17,
  42,764 tok) twice, B (6/17, 42,131 tok) once. The practical rule ("2–3 runs per configuration")
  survives; its justification does not. Repeated runs sample a small **discrete** set.

- **`shot_005` is settled** — it matches its frame on all six `p3` runs at both sample rates. One of
  criterion 3's three named shots is met.

- **The slow test's coin-flip assertion is now set on evidence, not left as a known flake.**
  `max(scores) - min(scores) > 0.3` → `> 0.2`, with the reasoning in the test body: six measured
  `p3` runs ranged 0.25–0.65, so 0.3 failed **4 of 6** — and it never caught what it was written
  for, because **`p1`'s range was 0.65** (0.10–0.75, D-024), comfortably over 0.3. Clustering has
  always been caught by the granularity assertions, never by this one. 0.2 sits below the measured
  floor with margin.

- **`docs/run-report.md`** gained a new top-level section *T011 continued — `fps` tested*, beneath
  the existing T011 numbers rather than replacing them: the six-run table, the bimodal-variance
  finding, the three named shots at both rates, the quota discovery, and a re-scored 9-row criteria
  table (6 pass / 2 fail / 1 closed-as-not-achievable).

- **Gates:** `uv run pytest -m "not slow"` **211 passed** · `uv run ruff check .` clean ·
  `uv run mypy elvideo` strict clean (14 files).

### Not done / deferred

- **Run 5 of the agreed 5 never ran.** The key hit a daily cap the repo had never recorded:

  ```
  Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests,
  limit: 20, model: gemini-3.5-flash
  ```

  It was budgeted as a fourth `fps=0.5` datapoint. `fps=0.5` therefore has n=3, not n=4. This does
  not change the verdict — the two settings' means differ by 2.0 matches in the *opposite* direction
  to the hypothesis — but the baseline is one sample thinner than planned. See **D-031**.

- **The slow tests were not re-run** (4 total, last green 2026-07-26). The gemini one needs a live
  call and the quota was gone. **The lowered 0.2 threshold has therefore not been exercised against
  the real API** — it is set from six recorded runs, not verified by a seventh.

- **Criterion 2 is not met and there is no cheap lever left.** Prompt anchoring is worth ~9 matches
  of 17; frame budget is worth none. The remaining idea (merge sub-2s shots before the call so the
  model picks among ~60 distinguishable intervals rather than 117 near-identical ones) changes
  `shots[]` itself — a product decision, deliberately **not** folded into T011.

- **One transient failure worth not misreading:** an `httpx.RemoteProtocolError: Server
  disconnected without sending a response` during a File API upload. Not a 429, no quota spent,
  succeeded on retry. Distinct from the quota error above.

- `work/footage_index.json` deliberately left as the T009 `p2` artifact — it is the published 2/17
  baseline the grader was calibrated against. The six `p3` indexes live beside it under explicit
  names.

- No commit — the user drives git.

### Decisions made

- **D-027 → `resolved`.** Closure condition ("closes when hypothesis 2 is measured or the fix is
  stable at ≥12/17") is met by the first clause. Resolved with the defect **not fixed** and the
  residual ceiling written into the entry: `gemini-3.5-flash` attributing a moment to one of 117
  sub-3-second intervals across 7 minutes is roughly **60% reliable**, and no lever available inside
  one call closes the rest. Records the successor idea (coarser intervals) as unscheduled.
- **D-030 (new, `resolved`)** — `fps` default stays 0.5, justified with agreement *and* token cost
  at both values, n=3 each, per T011 criterion 7. Also carries the slow test's 0.3 → 0.2 change and
  the argument that the range assertion was never the guard it was believed to be.
- **D-031 (new, `resolved`)** — the binding free-tier limit is **20 `generate_content`
  requests/day/project/model**, not the 250K TPM cap `docs/IDEA.md` says lets you "iterate freely
  all day". At ~42K tokens a run, requests run out long before tokens. **Grading calls come from the
  same pool**, so a *measured* index run costs 2 requests. No code change — the backoff behaved
  correctly and cannot retry past a daily cap. Plan sessions in requests, not tokens.
- **Criterion 6 closed as *not achievable this way*** rather than left `PARTIAL`. Validity checks
  pass on every run including the 6/17 one; `hint_drift()` reports 0–1 of 117 on runs that are half
  wrong. No detector exists inside `understand()` that does not look at frames, and looking at
  frames is a second model call — outside it by hard constraint 1. The grading harness *is* that
  detector, correctly kept as a separate consumer.
- **`docs/IDEA.md` left unedited** on the quota point, per the CLAUDE.md rule that a conflict with
  the spec is logged rather than silently resolved. Flagged to the owner beside D-016.

### Blockers

- **None that block work.** `blockers` is empty and `open_decisions` is now **empty for the first
  time since T009** — D-027 is resolved and D-030/D-031 were resolved as they were written.
- **A live constraint, not a blocker:** the daily 20-request quota is spent for 2026-07-26. Any
  session needing live calls should start on a later day, or with the request count planned.
- The D-016 owner follow-up (`.claude/CLAUDE.md` hard constraint 6 and `docs/IDEA.md` still describe
  a Path A counterparty that does not exist) is still open and still blocks nothing. **D-031 adds a
  second item to that same owner pile:** `docs/IDEA.md`'s "iterate freely all day".

### Next

- **A decision, not a task.** T011's cheap levers are exhausted. Either (a) `/new-task` the
  coarser-intervals experiment — raise `--threshold` so adjacent sub-2s shots merge and the model
  chooses among ~60 distinguishable intervals — which is a change to `shots[]` and therefore a
  product decision; or (b) accept the measured ~60% ceiling, close T011 as partial-by-design, and
  write the A/B up honestly. `prompts/session-start/010-alignment-ceiling-or-coarser-shots.md`
  frames both.

---

## 2026-07-27 — T011 (closed), T012 (created) · Path B: accept the ceiling, write it up

**Task(s):** T011 — caption ↔ `shot_index` alignment · T012 — coarser intervals (created, not started)
**Status at end:** T011 `partial` — **closed by design**. T012 `not_started`.
**Live Gemini requests spent: 0.**

Session 010 was framed as a choice between two paths, and the choice was the work.
**Path B was taken:** accept the measured ~60% ceiling, close T011, and state precisely what the
index can and cannot be trusted for. Path A (coarser intervals via `--threshold`) was **not** run —
it is written up as T012 instead. No code was touched this session; the deliverable is documentation
of a result that was already measured.

Clock note: local date 2026-07-27 (IST), UTC `2026-07-26T18:40Z`. Files date this session 2026-07-27.

### Done

- **`docs/run-report.md`** — fourth section appended, **§ *T011 closed — partial by design
  (2026-07-27, session 010)*.** Extends, does not replace, the three measured sections. Contains:
  - **What a consumer may trust**, field by field with the evidence: `t_start`/`t_end` (0 of 234
    boundary values off the 1/25s grid, 10,701/10,701 frames covered), shot ordering, `words[]`
    (joined by time window, not index — structurally immune to the defect), `keyframe` paths
    (`ffmpeg`-verified on three shots), schema shape, and the caption *corpus* as searchable content.
  - **What a consumer may not trust**: that `shots[i].caption` describes `shots[i]` — **58 of 102**
    graded pairs clean over six `p3` runs; `editorial_score` and `is_candidate` on a *named* shot,
    which inherit the same error wholesale; and `t_start_hint`/`t_end_hint` as a self-check.
  - A **6-point known-limitations list** aimed at whoever writes the downstream agent.
  - The **A/B claim split in two**: the claim about *what is in the video* holds (one call, 117
    shots, ~42.5K tokens, 86.8s of a 234.7s run, free tier); the claim about *which second* does not.
- **`state/decisions-log.md`** — **D-032** appended: T011 closes as `partial` by design; the
  coarser-intervals experiment is its named successor. Carries the exhausted-lever table and the
  revisit condition.
- **`tasks/T012-coarser-intervals.md`** — new task file, `not_started`, nothing run. Goal, the two
  costs it must pay before its first live request, nine acceptance criteria, and the constraints
  specific to it (the session-009 understanding-only driver **does not apply** — changing boundaries
  forces the full pipeline).
- **`tasks/T011-caption-shot-alignment.md`** — Status line rewritten to record the by-design closure;
  third **Outcome** section appended (2026-07-27).
- **`tasks/backlog.md`** — T011 row updated to closed-by-design, **T012 row added**, and the
  "Suggested order" prose rewritten so the index does not still read as though a decision is pending.
- **`state/progress.json`** — `current_task` `T012`, `closed_2026_07_27_session_010` block, a
  `consumer_contract` block mirroring the trust/do-not-trust split, and a rewritten `next_task`.

### Not done / deferred

- **T011's criteria 2 and 3 still fail, and that is now permanent.** Closing the task does not close
  the gap: ≥12/17 was never reached (best mean **10.7/17**), and `shot_059` matched its frame on
  **0 of 6** `p3` runs. **T011 is NOT in `completed_tasks`.**
- **Path A was not attempted.** No coarser-threshold run exists, so the hypothesis that ~60
  distinguishable intervals fixes attribution is **untested**, not disproved. It is T012.
- **The slow tests (4) were not re-run** — unchanged from session 009. D-030 lowered the score-range
  assertion 0.3 → 0.2 from six recorded runs, and that threshold has **still never been exercised
  against the live API**. Worth one request on a future live day.
- **The two owner follow-ups are untouched and still block nothing:** D-016 (CLAUDE.md hard
  constraint 6 and `docs/IDEA.md` describe a Path A counterparty that does not exist) and D-031
  (`docs/IDEA.md`'s "TPM cap 250K/min → iterate freely all day", contradicted by the 20-request daily
  cap). Both left unedited per the CLAUDE.md conflict rule.
- No commit — the user drives git.

### Decisions made

- **D-032 (new, `resolved`)** — the session's substance. T011 closes at `partial`; `partial` is its
  **final** state, not a waypoint. Justified by the exhausted-lever table (prompt anchoring worth ~9
  matches of 17, `p4` reverted, `fps` worse at +30% tokens, self-report worth nothing, validity
  checks pass even on the 6/17 run) plus what is out of reach (bigger model pinned out by hard
  constraint 3, per-shot calls forbidden by hard constraint 1). Records **T012** as the named
  successor with its two costs, and states the revisit condition: if T012 reaches a stable ≥12/17 on
  a stated denominator, the ceiling was a property of *this footage's* cut granularity rather than
  of the model — a stronger claim than T011 can currently make.
- **`progress.json` `status` deviates from `/checkpoint`'s four-value enum** — it reads
  `not_started` with a `status_note` explaining why. Nothing is in progress: T011 is closed and T012
  is written but unstarted. `in_progress` would be false and `task_complete` would overstate. Flagged
  here rather than silently picked.
- **T012 was given a full task file rather than a backlog line.** "Recorded as the named successor"
  is worth more as the repo's own contract format — task files are the contract, the backlog is an
  index. Writing it cost nothing and it is explicitly `not_started`; it is not Path A's work, which
  would have required runs, grades, and a report section.

### Blockers

- **None.** `blockers` is empty and `open_decisions` is empty — D-032 was resolved as it was written.
- **Not a blocker, a standing constraint:** 20 `generate_content` requests per project per model per
  day (D-031), grading calls included. Any future live session states its request count up front.

### Next

- **T012 — coarser intervals — and it is optional, not owed.** s1's pipeline is finished and its
  result is written up; T012 only buys better attribution at the cost of index granularity. If
  nobody picks it up, the repo is in a coherent finished state as it stands.
- Generated prompt: **`prompts/session-start/011-coarser-intervals-or-stop.md`**.

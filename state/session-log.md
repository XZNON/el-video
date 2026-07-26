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

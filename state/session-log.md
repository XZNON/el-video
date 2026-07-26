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

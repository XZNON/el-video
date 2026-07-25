# Bootstrap Prompt — `elvideo-gemini` (Path B: Gemini-native Understanding, s1)

Paste this whole file into Claude Code as your first message in a fresh repo directory.
`docs/idea.md` (the spec) will already exist on disk before you run this — read it first, it is
ground truth for everything below. If it's missing, stop and ask for it instead of guessing.

---

## 0. Scope of THIS session

You are scaffolding, not implementing. Build the repo skeleton, the agentic harness, the task
breakdown, and the state/prompt system described below. Every source module should be a real,
importable stub with correct signatures, type hints, and docstrings, ending in
`raise NotImplementedError("see tasks/T00X-*.md")` — no real logic yet. Do not call the Gemini
API, do not write scene-detection or transcription logic. Stop at the end of Step 9 and hand off
via the generated next-session prompt rather than continuing into T001.

If any instruction below conflicts with `docs/idea.md`, idea.md wins — flag the conflict in
`state/decisions-log.md` rather than silently picking one.

---

## 1. Hard constraints (bake these into CLAUDE.md, not just this prompt)

- One Gemini call per video, never per shot. This is a load-bearing product decision, not an
  optimization — a design that drifts toward per-shot calls is wrong even if it "works."
- Free tier only: target ≈30K tokens/10-min video, `media_resolution=low`, default `fps=0.5`
  (raise per-video for action-heavy footage, lower for talking-head).
- Model string is pinned: `gemini-3.5-flash`. Don't "helpfully" swap it for another model name.
- Shot cuts (PySceneDetect), word timing (WhisperX), and quality scoring (OpenCV Laplacian) stay
  classical/deterministic. Gemini's own timestamps are only second-granular and are never used
  for `t_start`/`t_end` — those come from PySceneDetect.
- Local filesystem only in s1. No GCS, no Firestore, no Cloud Run, no embeddings computation
  (the `embedding` field exists in the schema but stays `null`).
- `footage_index.json` is a **shared contract** with a co-founder's separate repo (El-Video,
  local-first path). Don't change the schema shape without logging it in
  `state/decisions-log.md` — this repo has no automated way to know if the other side changed
  too, so schema edits are a manual-sync risk, not just a local one.
- Speed target: full index of a 10-min video in <5 min wall-clock, dominated by transcription +
  the one Gemini call. Per-stage timing must be logged, not just total time.

---

## 2. Repo & tooling

- Repo name: `elvideo-gemini` (or ask the user if they want a different name before creating it).
- Python package name: `elvideo` (matches idea.md's module layout exactly, so paths are portable
  if the two implementations ever get compared/merged later).
- Tooling: `uv`. Run `uv init`, then `uv add` the runtime deps and `uv add --dev` the dev deps
  below. Target Python `>=3.11,<3.13` (check WhisperX/PySceneDetect compatibility if `uv` balks;
  don't silently downgrade below 3.11 without noting it).

**Runtime deps:** `google-genai`, `scenedetect[opencv]`, `whisperx`, `opencv-python`, `pydantic`,
`jsonschema`, `python-dotenv`, `tenacity`, `typer`, `rich`

**Dev deps:** `pytest`, `ruff`, `mypy`

**System prerequisite (not pip-installable):** `ffmpeg` on PATH, for `ffprobe`. Note this loudly
in the README — it's the one dependency `uv add` won't catch.

---

## 3. Directory structure to create

```
elvideo-gemini/
├── .claude/
│   ├── CLAUDE.md
│   └── commands/
│       ├── start-task.md
│       ├── checkpoint.md
│       └── new-task.md
├── docs/
│   ├── idea.md                  # already exists — do not overwrite
│   ├── architecture.md
│   └── schema.md
├── prompts/
│   ├── bootstrap.md              # verbatim copy of THIS prompt, for provenance
│   ├── templates/
│   │   └── session-start-template.md
│   └── session-start/            # generated kickoff prompts land here
├── tasks/
│   ├── backlog.md
│   ├── T001-probe.md
│   ├── T002-scenes.md
│   ├── T003-transcribe.md
│   ├── T004-gemini-understanding.md
│   ├── T005-quality.md
│   ├── T006-schema-and-models.md
│   ├── T007-build-orchestrator.md
│   ├── T008-cli.md
│   ├── T009-e2e-validation.md
│   └── T010-schema-sync-checkpoint.md
├── state/
│   ├── progress.json
│   ├── session-log.md
│   └── decisions-log.md
├── elvideo/
│   ├── __init__.py
│   ├── cli.py
│   ├── index/
│   │   ├── __init__.py
│   │   ├── probe.py
│   │   ├── scenes.py
│   │   ├── transcribe.py
│   │   ├── gemini.py
│   │   ├── quality.py
│   │   └── build.py
│   └── schema/
│       ├── __init__.py
│       ├── footage_index.schema.json
│       └── models.py
├── tests/
│   ├── test_schema.py
│   └── fixtures/
│       └── .gitkeep
├── work/                         # gitignored runtime output
│   └── .gitkeep
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
```

---

## 4. `.claude/CLAUDE.md` — persistent project memory

Write this so every future Claude Code session (with zero other context) can orient itself in
under a minute. Include:

- The one-line project description from idea.md.
- The hard constraints from Section 1 above, verbatim or tightened.
- **Session protocol**, stated explicitly:
  1. At session start: read `state/progress.json` and the last ~3 entries of
     `state/session-log.md` before touching any code.
  2. Read the relevant `tasks/T0XX-*.md` file in full before starting work on it.
  3. At session end: run `/checkpoint` (see Section 5) — never leave a session without updating
     state.
- Coding conventions: type hints everywhere, pydantic models for the schema (not raw dicts),
  docstrings that reference the relevant idea.md section, `ruff` clean, tests via `pytest`.
- A pointer: "Full spec is `docs/idea.md`. Don't re-derive architecture decisions already made
  there — cite them."

---

## 5. `.claude/commands/` — slash commands (the harness)

Each is a markdown file whose body is the prompt Claude Code runs for that command.

**`start-task.md`** (`/start-task <task-id>`):
Reads `tasks/T0XX-*.md`, the relevant idea.md section it references, and current
`state/progress.json`. Restates the task's goal and acceptance criteria back to the user before
writing any code, and sets `progress.json`'s `current_task` + status to `in_progress`.

**`checkpoint.md`** (`/checkpoint`):
1. Updates `state/progress.json` (current task, status, completed tasks, blockers, timestamp).
2. Appends a dated entry to `state/session-log.md` using the format in
   `prompts/templates/session-start-template.md` (what got done, what's next, blockers).
3. Generates the next paste-ready session prompt into `prompts/session-start/NNN-<slug>.md` —
   it should name the next task, restate its acceptance criteria, and link the state files to
   read first. This is the file the user actually pastes into Claude Code next time.

**`new-task.md`** (`/new-task <name>`):
Scaffolds a new `tasks/T0XX-<name>.md` from the same template as the seeded tasks (Section 6),
for work that comes up mid-stream and wasn't anticipated in the initial breakdown.

---

## 6. `tasks/` — seed these ten, one file each, from idea.md's scope + Definition of Done

Each task file: **Goal**, **Reads/depends on** (idea.md section, other tasks), **Inputs/Outputs**,
**Acceptance criteria** (pulled directly from idea.md's DoD checklist where it applies), **Status**.

| ID | Title | Core acceptance criterion (from idea.md) |
|---|---|---|
| T001 | `probe.py` — ffprobe wrapper | returns duration/fps/w/h, feeds `video` block of schema |
| T002 | `scenes.py` — shot detection | frame-accurate `t_start`/`t_end` via PySceneDetect, not Gemini |
| T003 | `transcribe.py` — WhisperX | word-level timing; `words_in_range()` helper for per-shot transcript |
| T004 | `gemini.py` — native understanding pass | **exactly one** call per video; structured JSON out; `media_resolution=low`; `fps` as a per-video knob; exponential backoff on 429 |
| T005 | `quality.py` — OpenCV scoring | Laplacian + exposure, deterministic, no LLM involved |
| T006 | `schema/` — contract + validator | pydantic models mirror `docs/schema.md` exactly; `embedding` reserved/null |
| T007 | `build.py` — orchestrator | assembles + validates `footage_index.json`; logs per-stage timing |
| T008 | `cli.py` — entrypoint | `python -m elvideo index in.mp4` works end to end |
| T009 | E2E validation | on the agreed A/B test video: 1 Gemini call, ≤~30K tokens, no 429, <5 min wall-clock, schema validates |
| T010 | Schema-sync checkpoint | resolve idea.md's 3 "Open decisions to confirm" (full-index vs top-N; shared vs vendored PySceneDetect/WhisperX; which test video) — log resolution in `state/decisions-log.md` |

`tasks/backlog.md` is just an index: task ID, title, status, one-line note — kept in sync by
`/checkpoint`.

---

## 7. `state/` — seed files

**`progress.json`** (initial):
```json
{
  "current_task": null,
  "status": "scaffold_complete",
  "completed_tasks": [],
  "blockers": [],
  "open_decisions": ["full-index-vs-topN", "shared-vs-vendored-detect", "ab-test-video"],
  "last_updated": "<ISO timestamp at scaffold time>"
}
```

**`session-log.md`**: start with one entry documenting this bootstrap session itself (what got
created, that no logic was implemented, what task is next).

**`decisions-log.md`**: seed with the three open decisions from idea.md's "Open decisions to
confirm" section, each marked unresolved, with a one-line prompt for what resolving it requires
(e.g. "needs a 10-min message with the co-founder, not a solo call").

---

## 8. Source skeleton — signatures only

Mirror idea.md's module layout table exactly:

```python
# elvideo/index/scenes.py
def detect_shots(path: str) -> list[Shot]: ...
# elvideo/index/transcribe.py
def transcribe(path: str) -> list[Word]: ...
# elvideo/index/gemini.py
def understand(path: str, fps: float, media_resolution: str) -> list[ShotUnderstanding]: ...
# elvideo/index/quality.py
def score_frame(img: "np.ndarray") -> float: ...
# elvideo/index/build.py
def build_index(...) -> dict: ...
```

Define `Shot`, `Word`, `ShotUnderstanding` as pydantic models in `elvideo/schema/models.py`
matching the `footage_index.json` example in idea.md field-for-field — this file is the single
source of truth other modules import from, not ad hoc dicts.

`elvideo/schema/footage_index.schema.json` — write the actual JSON Schema for the contract (not
just the pydantic models) so it can be validated independent of the Python types, and so it's
diffable against whatever the co-founder's repo produces.

`tests/test_schema.py` — one placeholder test that loads the schema file and asserts it's valid
JSON Schema (not that any real output validates against it yet — there's no real output).

---

## 9. Root files

- **`README.md`**: what this is (link to `docs/idea.md`), the ffmpeg prerequisite, `uv sync`,
  `uv run python -m elvideo index in.mp4` once T008 lands, and a pointer to `.claude/CLAUDE.md`
  for anyone (human or agent) picking this up cold.
- **`.env.example`**: `GEMINI_API_KEY=`
- **`.gitignore`**: `work/`, `.env`, `__pycache__/`, `.venv/`, standard Python ignores.
- **`docs/architecture.md`**: the pipeline diagram + module table from idea.md, restated (not
  copy-pasted wholesale — this is the "read this before that" version).
- **`docs/schema.md`**: prose description of the `footage_index.json` contract and which fields
  are Path B's edge (`editorial_score`, `moment_reason`) vs shared with Path A.

---

## 10. Git

`git init`, first commit message: `chore: scaffold elvideo-gemini (s1 bootstrap, no logic yet)`.
Don't set up a remote or push — that's the user's call.

---

## 11. Close out

1. Copy this entire prompt verbatim into `prompts/bootstrap.md`.
2. Update `state/progress.json` and `state/session-log.md` per Section 7.
3. Generate `prompts/session-start/001-probe-and-scenes.md` — a ready-to-paste prompt that kicks
   off T001 (and T002, since probe+scenes are small and sequential), restating their acceptance
   criteria and pointing at the state files to read first.
4. Print a final summary: the tree that got created, and remind the user that no pipeline logic
   exists yet — next session starts with `prompts/session-start/001-probe-and-scenes.md`.

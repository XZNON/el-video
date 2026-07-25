# CLAUDE.md — elvideo-gemini

**Project, one line:** Turn one ≤10-min video into a shot-level text index
(`footage_index.json`) that an agent can later reason over — Gemini-native path, running locally
on the free tier, zero cloud, zero credits.

This is **s1 / Part 1 only** (video → structured index → local store). Render, Director, Critic,
and Delivery are out of scope.

**Full spec is `docs/IDEA.md`.** Don't re-derive architecture decisions already made there —
cite them. If anything here conflicts with `docs/IDEA.md`, **idea.md wins**; log the conflict in
`state/decisions-log.md` rather than silently picking one.

> Note: the spec file is `docs/IDEA.md` (uppercase). The bootstrap prompt calls it `docs/idea.md`
> — same file. See `state/decisions-log.md` D-004.

---

## Hard constraints

These are load-bearing product decisions, not optimizations. A design that drifts away from them
is wrong even if it "works."

1. **One Gemini call per video, never per shot.** A 10-min video is 100–300 shots; per-shot calls
   blow the 10 RPM free-tier cap instantly. Gemini watches the whole clip once and returns the
   full shot list in one structured response. This is also the differentiator — native
   long-context understanding, not frame-by-frame captioning.
2. **Free tier only.** Target ≈30K tokens per 10-min video. `media_resolution=low` (66 tok/frame,
   not 258). Default `fps=0.5`; raise to 1–2 for action-heavy footage, lower for talking-head —
   a per-video knob, never a global change.
3. **Model string is pinned: `gemini-3.5-flash`.** Do not "helpfully" swap it for another model
   name.
4. **Classical stays classical.** Shot cuts (PySceneDetect), word timing (WhisperX), and quality
   scoring (OpenCV Laplacian) are deterministic and non-LLM. **Gemini's own timestamps are only
   second-granular and are never used for `t_start`/`t_end`** — those come from PySceneDetect.
5. **Local filesystem only in s1.** No GCS, no Firestore, no Cloud Run, no embeddings computation.
   The `embedding` field exists in the schema but stays `null`.
6. **`footage_index.json` is a shared contract** with a co-founder's separate repo (El-Video,
   Path A / local-first). Don't change the schema shape without logging it in
   `state/decisions-log.md`. This repo has **no automated way to know if the other side changed
   too** — schema edits are a manual-sync risk, not just a local one.
7. **Speed target:** full index of a 10-min video in **<5 min wall-clock**, dominated by
   transcription + the one Gemini call. **Per-stage timing must be logged, not just total time.**

---

## Session protocol

**Follow this every session. No exceptions.**

1. **At session start** — read `state/progress.json` and the last ~3 entries of
   `state/session-log.md` **before touching any code**. They tell you what task is live, what's
   blocked, and what the previous session actually left behind.
2. **Before working a task** — read the relevant `tasks/T0XX-*.md` file **in full**, plus the
   `docs/IDEA.md` section it cites. Use `/start-task T0XX`.
3. **At session end** — run `/checkpoint`. Never leave a session without updating state. It
   updates `progress.json`, appends to `session-log.md`, syncs `tasks/backlog.md`, and generates
   the next paste-ready prompt into `prompts/session-start/`.

---

## Coding conventions

- **Type hints everywhere.** `uv run mypy elvideo` is configured strict.
- **Pydantic models for the schema, never raw dicts.** `elvideo/schema/models.py` is the single
  source of truth every other module imports from.
- **Two schema artifacts, kept in lockstep:** `models.py` (pydantic, for Python) and
  `footage_index.schema.json` (JSON Schema, for cross-repo diffing against Path A). Change one,
  change the other, and say so in `state/decisions-log.md`.
- **Docstrings cite the spec** — reference the relevant `docs/IDEA.md` section by name so the
  reasoning is one hop away.
- `uv run ruff check .` clean before checkpoint.
- Tests via `uv run pytest`.
- Stubs raise `NotImplementedError("see tasks/T00X-*.md")` until their task lands.

## Commands

```bash
uv sync                              # install deps (first run pulls torch via whisperx — multi-GB)
uv run python -m elvideo index in.mp4   # once T008 lands
uv run pytest
uv run ruff check .
uv run mypy elvideo
```

## Module map

| Module | Signature | Owner |
|---|---|---|
| `elvideo/index/probe.py` | `probe(path) -> VideoMeta` | shared, ffprobe |
| `elvideo/index/scenes.py` | `detect_shots(path) -> list[Shot]` | shared, PySceneDetect |
| `elvideo/index/transcribe.py` | `transcribe(path) -> list[Word]` | shared, WhisperX |
| `elvideo/index/gemini.py` | `understand(path, fps, media_resolution) -> list[ShotUnderstanding]` | **Path B core** |
| `elvideo/index/quality.py` | `score_frame(img) -> float` | shared, OpenCV |
| `elvideo/index/build.py` | `build_index(...) -> dict` | orchestrator |

`gemini.py` is the analogue of El-Video's pluggable `caption.py` — same role (understanding),
different backend.

## Current state

Scaffold complete, **no pipeline logic implemented**. Every module raises `NotImplementedError`.
Task order: T001 → T010, see `tasks/backlog.md`. Three open decisions are unresolved and blocking
T009 — see `state/decisions-log.md`.

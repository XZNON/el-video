# elvideo-gemini

Turn one ≤10-min video into a shot-level text index (`footage_index.json`) that an agent can
later reason over — **Gemini-native path**, running locally on the free tier, zero cloud, zero
credits.

This is **Path B** of a two-implementation A/B on the Understanding stage. Path A (a co-founder's
separate repo, "El-Video") does the same job with a local VLM. Both emit the **identical**
`footage_index.json` schema; the diff between the two indexes on the same footage *is* the
architecture decision.

Full spec: **[`docs/IDEA.md`](docs/IDEA.md)** — ground truth, read it before changing anything.
Picking this up cold (human or agent)? Start at **[`.claude/CLAUDE.md`](.claude/CLAUDE.md)**.

> **Status: scaffold only.** Every module is a typed stub that raises `NotImplementedError`.
> No pipeline logic exists yet. Next session starts with
> `prompts/session-start/001-probe-and-scenes.md`.

---

## Prerequisites

**`ffmpeg` must be on your PATH** — this is the one dependency `uv add` will *not* install for
you. `probe.py` shells out to `ffprobe`, which ships with ffmpeg.

```bash
ffprobe -version   # must print a version, not "command not found"
```

- Windows: `winget install Gyan.FFmpeg` (or `choco install ffmpeg`)
- macOS: `brew install ffmpeg`
- Debian/Ubuntu: `sudo apt install ffmpeg`

Python `>=3.11,<3.13` and [`uv`](https://docs.astral.sh/uv/) are the only other requirements.

## Setup

```bash
uv sync                      # installs deps into .venv (pulls torch via whisperx — multi-GB, slow first run)
cp .env.example .env         # then paste a free-tier GEMINI_API_KEY into it
```

## Usage

Once **T008** lands (not yet — see `tasks/backlog.md`):

```bash
uv run python -m elvideo index in.mp4
```

Writes `work/footage_index.json`, validated against
`elvideo/schema/footage_index.schema.json`, plus per-stage timing to the log.

---

## How it works

```
in.mp4 ──▶ probe (ffprobe) ─────────────┐
        ├▶ shots  (PySceneDetect)  ──────┤
        ├▶ words  (WhisperX, word-level) ┤
        └▶ Gemini native pass ───────────┤──▶ build ──▶ footage_index.json  (local disk)
             (whole video, 1 call)        │              + validate against schema
           quality (OpenCV Laplacian) ────┘
```

**The one rule that makes free-tier work: one Gemini call per video, never per shot.** A 10-min
video is 100–300 shots; per-shot calls would blow 10 RPM instantly. Gemini watches the whole clip
once and returns the full shot list in a single structured response.

Everything that must be *exact* stays classical and deterministic — shot cuts (PySceneDetect),
word timing (WhisperX), quality (OpenCV Laplacian). Gemini's own timestamps are second-granular
and are **never** used for `t_start`/`t_end`.

More: [`docs/architecture.md`](docs/architecture.md) · [`docs/schema.md`](docs/schema.md)

## Layout

| Path | What |
|---|---|
| `docs/IDEA.md` | The spec. Ground truth. |
| `docs/architecture.md` | Pipeline + module map, orientation version |
| `docs/schema.md` | The `footage_index.json` shared contract, in prose |
| `.claude/CLAUDE.md` | Persistent project memory for agent sessions |
| `.claude/commands/` | `/start-task`, `/checkpoint`, `/new-task` |
| `tasks/` | T001–T010 breakdown + `backlog.md` index |
| `state/` | `progress.json`, `session-log.md`, `decisions-log.md` |
| `prompts/` | `bootstrap.md` (provenance) + generated session kickoffs |
| `elvideo/` | The package |
| `work/` | Runtime output — gitignored |

## Dev

```bash
uv run pytest
uv run ruff check .
uv run mypy elvideo
```

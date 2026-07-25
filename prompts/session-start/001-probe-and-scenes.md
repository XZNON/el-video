# Session 001 — T001 + T002: probe and shot detection

## Read these first, in this order

1. `state/progress.json` — what's live, what's blocked
2. `state/session-log.md`, the last entry (there's only one so far — the bootstrap)
3. `.claude/CLAUDE.md` — hard constraints and session protocol
4. `tasks/T001-probe.md` and `tasks/T002-scenes.md` — both in full
5. `docs/IDEA.md` § *Scope*, § *Architecture (Path B)*, § *Shared contract*

Then run `/start-task T001`.

## Before anything else

```bash
uv sync
```

Deps are resolved and locked but **not installed** (decisions-log D-008) — `whisperx` pulls
torch, so this is a multi-GB download on first run. Nothing, including `pytest`, works until it
finishes. Kick it off first.

Then confirm the prerequisite that `uv` can't install:

```bash
ffprobe -version
```

It was on PATH at scaffold time (8.1.1). If it isn't on yours, T001 cannot be done.

Sanity-check that the scaffold is intact while `uv sync` runs:

```bash
uv run pytest          # tests/test_schema.py should pass — schema artifacts are real, not stubs
uv run ruff check .
```

## Where things stand

The repo is scaffolded and nothing is implemented. Every module in `elvideo/` raises
`NotImplementedError("see tasks/T00X-*.md")`.

Two exceptions, both deliberate: `elvideo/schema/models.py` and
`elvideo/schema/footage_index.schema.json` are **real** — they're declarative contract, not
pipeline logic, so the bootstrap wrote them rather than stubbing them. `tests/test_schema.py`
guards that they agree with each other. Only `validate_index()` in `elvideo/schema/__init__.py`
is still a stub.

This session implements the first two stages of the pipeline. Both are small, classical, and
deterministic — no Gemini anywhere in this session.

---

## Task 1: T001 — `probe.py`, ffprobe wrapper

**Goal:** read duration, frame rate, and pixel dimensions from a video and return a `VideoMeta`.
Fills the `video` block of `footage_index.json`.

**Acceptance criteria** (restated in full; `tasks/T001-probe.md` is authoritative if they
disagree):

- [ ] `probe("in.mp4")` returns a `VideoMeta` with all five fields populated and non-zero.
- [ ] `fps` is the **container** frame rate, parsed from `r_frame_rate`'s `num/den` form
      (`30000/1001` → `29.97`), not rounded to an int.
- [ ] `duration_s` is a float in seconds, read from the format block.
- [ ] Raises `FileNotFoundError` with the path when the file doesn't exist.
- [ ] Raises `FileNotFoundError` with an actionable message ("ffprobe not on PATH — install
      ffmpeg") when the binary is missing, rather than an opaque `OSError`.
- [ ] Raises `ValueError` with the path and ffprobe's stderr when ffprobe exits non-zero or the
      output can't be parsed.
- [ ] Vertical video (1080×1920) reports `w=1080, h=1920` — no silent transposition.
- [ ] Unit test covers the `num/den` fps parse and the missing-file path. Mock the subprocess;
      no fixture video needed.

---

## Task 2: T002 — `scenes.py`, shot detection

**Goal:** detect shot boundaries with PySceneDetect and return ordered `Shot` objects with
frame-accurate `t_start` / `t_end`. These timings are load-bearing for the entire index.

**Acceptance criteria** (restated in full; `tasks/T002-scenes.md` is authoritative):

- [ ] `detect_shots("in.mp4")` returns shots in ascending `t_start` order.
- [ ] Boundaries are **frame-accurate**, derived from PySceneDetect's frame numbers and the
      container fps — not rounded to whole seconds.
- [ ] Coverage is gapless and non-overlapping: `shots[i].t_end == shots[i+1].t_start` for all
      `i`, and `shots[0].t_start == 0.0`.
- [ ] The final shot's `t_end` equals the video duration (within one frame).
- [ ] A single-shot video (no cuts detected) returns exactly one shot spanning the whole
      duration — not an empty list.
- [ ] Ids are zero-padded and unique, matching `^shot_[0-9]{3,}$` (a 100+ shot video must still
      validate).
- [ ] Detector and threshold are recorded somewhere reproducible, so Path A can match them
      (D-002).
- [ ] Raises `FileNotFoundError` with the path when the file doesn't exist.
- [ ] A 10-min video is detected in well under a minute.

---

## Constraints that bite on these two tasks

- **Both stages are classical, deterministic, and shared with Path A.** No model involvement of
  any kind. Gemini does not appear in this session.
- **PySceneDetect owns `t_start` / `t_end`.** Gemini's timestamps are second-granular and are
  never used for them. T002 is the *only* source of those two fields.
- **D-002 (shared vs vendored detection) is unresolved.** So whatever detector and threshold you
  pick must be **written down explicitly** — not left as an implicit library default. Path A has
  to be able to match them exactly, or the A/B diff is contaminated by a threshold difference.
- `video.fps` (container rate, T001) and `index_meta.sample_fps` (rate fed to Gemini) are
  different fields with different meanings. Don't conflate them.
- Type hints everywhere, pydantic models from `elvideo/schema/models.py` (never ad hoc dicts),
  docstrings citing the relevant `docs/IDEA.md` section, `ruff` clean.

## Blockers and open decisions affecting this

- **D-002 — shared vs vendored PySceneDetect/WhisperX.** Doesn't block the code, but it does
  mean the detector settings must be recorded for later sync. See `state/decisions-log.md`.
- **No test video yet (D-003).** You can write and unit-test both modules without one — mock
  ffprobe for T001, and use synthetic assertions for T002's ordering/coverage invariants. But
  neither can be verified against real footage until a clip exists. Any short local video works
  for smoke-testing in the meantime; the *agreed A/B* video only matters for T009.

## Definition of done for the session

- `probe.py` and `scenes.py` implemented, with every acceptance criterion above met or explicitly
  recorded as not met.
- Unit tests pass: `uv run pytest`.
- Clean: `uv run ruff check .` and `uv run mypy elvideo`.
- Detector + threshold choice recorded in `state/decisions-log.md` (relevant to D-002).
- Smoke-tested on some real video file, even a throwaway one — these two modules are the
  cheapest possible check that ffmpeg and PySceneDetect actually work on this machine.

End with `/checkpoint`.

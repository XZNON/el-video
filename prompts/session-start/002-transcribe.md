# Session 002 — T003: WhisperX word-level transcription

## Read these first, in this order

1. `state/progress.json` — what's live, what's blocked
2. Last ~3 entries of `state/session-log.md` — what the previous session left behind
3. `.claude/CLAUDE.md` — hard constraints and session protocol
4. `tasks/T003-transcribe.md` — in full
5. `docs/IDEA.md` § *Scope* (step 3), § *Shared contract* (the `words[]` block), § *Storage &
   speed*; also `docs/schema.md` § *`words[]`* and `state/decisions-log.md` **D-002**

Then run `/start-task T003`.

## Where things stand

T001 (`probe.py`) and T002 (`scenes.py`) are **done** — implemented, unit-tested, and
smoke-tested on the real A/B clip `in.mp4` (428.11s, 25 fps, 1280×720; 117 shots in 25.3s at
`ContentDetector(threshold=27.0)`, gapless). Gates are green: pytest 18 passed, ruff clean,
mypy strict clean. Deps are installed (`uv sync` already run — torch is present).

Two things the last session recorded that matter here:

- **D-014**: container duration (428.106s, includes audio tail) ≠ video stream duration
  (428.04s) on `in.mp4`. Words may legitimately have timestamps past the last shot's `t_end`.
- T002's detector settings live as constants in `elvideo/index/scenes.py` — the same
  "recorded, reproducible" treatment is required for WhisperX settings this session.

## This session: T003 — `transcribe.py`

**Goal:** transcribe the audio track with **word-level** timestamps (WhisperX alignment pass,
not segment-level), returning a flat chronological `list[Word]`; provide `words_in_range()` to
slice it into per-shot transcripts.

**Acceptance criteria** (restated in full — `tasks/T003-transcribe.md` is authoritative if they
disagree):

- [ ] `transcribe("in.mp4")` returns words with per-word `t` and `d`, not segment-level spans.
- [ ] Output is chronological and covers the whole audio track.
- [ ] A video with **no audio track** returns `[]` rather than raising.
- [ ] `words_in_range()` is **half-open on the right** (`t_start <= w.t < t_end`), so a word
      landing exactly on a cut belongs to exactly one shot — never both, never neither.
- [ ] `words_in_range()` returns `[]` for a silent range, and the joined transcript for such a
      shot is `""` (empty string, not `None` — the schema requires a string).
- [ ] Unit tests for `words_in_range()` cover: boundary word at `t == t_start` (included),
      boundary word at `t == t_end` (excluded), empty range, and empty word list. These need no
      audio fixture.
- [ ] Model size / compute type / language settings are recorded, so Path A can match (D-002).
- [ ] Stage timing is reported — this is expected to be the slowest stage and the biggest single
      chunk of the <5 min budget.
- [ ] Raises `FileNotFoundError` with the path when the file doesn't exist.

## Constraints that bite on this task specifically

- **Classical, shared with Path A.** Same model + settings both sides or the `transcript` field
  pollutes the A/B diff. Record model size, compute type, device, language — as code constants,
  the way `scenes.py` records the detector (D-012 precedent).
- **Local only.** No cloud transcription APIs.
- **Speed:** transcription + the one Gemini call *is* the 5-min budget. If this stage alone
  approaches 5 min on `in.mp4` (7:08), flag it as a blocker rather than absorbing it.
- WhisperX's **alignment pass** is what produces word-level timing — don't drop it to save time;
  plain faster-whisper output is segment-level and fails the first criterion.
- Device (CPU vs CUDA) is a real speed fork — record which one the timing numbers came from.
- Type hints everywhere, `Word` from `elvideo/schema/models.py` (never ad hoc dicts), docstrings
  citing `docs/IDEA.md`, ruff + mypy strict clean.

## Blockers and open decisions affecting this

- **D-002 (unresolved)** — shared vs vendored WhisperX. Doesn't block the code; it means the
  settings chosen must be explicit and shareable, not library defaults. Add what you pick to
  `state/decisions-log.md`.
- **T010 still pending** — the co-founder message resolving D-001/D-002. Not this session's
  work, but if the user wants to send it, the concrete settings from this session belong in it.

## Definition of done for the session

- `transcribe.py` implemented: `transcribe()` + `words_in_range()`, every criterion above met or
  explicitly recorded as not met.
- Unit tests pass (`uv run pytest`), ruff clean, mypy strict clean.
- WhisperX settings recorded in code constants **and** `state/decisions-log.md`.
- Smoke-tested on `in.mp4` with wall-clock timing reported against the 5-min budget.

End with `/checkpoint`.

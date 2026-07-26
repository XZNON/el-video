# T003 — `transcribe.py`: WhisperX word-level transcription

**Status:** `done` (2026-07-26) — settings and measurements in `state/decisions-log.md` **D-015**

## Goal

Transcribe the audio track with **word-level** timestamps, and provide `words_in_range()` to
slice that flat list into a per-shot transcript.

Word-level (not segment-level) is the requirement. Segment timing is useless for the thing this
index exists to enable downstream: precise cuts and filler removal.

## Reads / depends on

- `docs/IDEA.md` § *Scope* (step 3), § *Shared contract* (the `words[]` block), § *Storage &
  speed*
- `docs/schema.md` § *`words[]` — flat word-level timing*
- `state/decisions-log.md` **D-002** (shared vs vendored WhisperX)
- Tasks: none hard. T002 supplies the ranges `words_in_range()` is called with, but the two can
  be built independently.

## Inputs / outputs

**In:** `path: str`.
**Out:** `list[Word]` — `{t, d, w}`, chronological, flat for the whole video.

`words_in_range(words, t_start, t_end) -> list[Word]` slices it.

## Acceptance criteria

- [x] `transcribe("in.mp4")` returns words with per-word `t` and `d`, not segment-level spans.
      1436 words, mean duration 0.18s, max 2.02s.
- [x] Output is chronological and covers the whole audio track. First word `t=0.928`, last
      `t=427.017` on a 428s clip; sorted explicitly, not trusted from WhisperX.
- [x] A video with **no audio track** returns `[]` rather than raising. Checked up front with
      `ffprobe -select_streams a:0`, so WhisperX is never loaded.
- [x] `words_in_range()` is **half-open on the right** (`t_start <= w.t < t_end`), so a word
      landing exactly on a cut belongs to exactly one shot — never both, never neither.
- [x] `words_in_range()` returns `[]` for a silent range, and the joined transcript for such a
      shot is `""` (empty string, not `None` — the schema requires a string).
- [x] Unit tests for `words_in_range()` cover: boundary word at `t == t_start` (included),
      boundary word at `t == t_end` (excluded), empty range, and empty word list. These need no
      audio fixture.
- [x] Model size / compute type / language settings are recorded, so Path A can match (D-002).
      Module constants + `pick_device()`, pinned in **D-015**, guarded by a test.
- [x] Stage timing is reported — logged at INFO with device / model / compute type on the same
      line. **102.7s** warm (ASR 49.5s + align 53.2s) on the 428s clip; ~34% of the <5 min
      budget, so not a blocker.
- [x] Raises `FileNotFoundError` with the path when the file doesn't exist.

## Constraints that bite here

- **Classical and deterministic-ish, shared with Path A.** Same model and settings on both
  sides, or `transcript` differs between the two indexes and pollutes the A/B diff with noise
  that has nothing to do with Understanding.
- **Local only.** No cloud transcription APIs. WhisperX runs on the laptop.
- Speed: transcription plus the one Gemini call *is* the 5-minute budget. If this stage alone
  approaches it, flag it as a blocker rather than absorbing it.

## Notes

WhisperX pulls torch — the first `uv sync` is a multi-GB download. That's expected; it is not a
dependency problem to "fix."

WhisperX's alignment pass is what produces word-level timing; plain faster-whisper output is
segment-level and won't satisfy the first acceptance criterion. Don't drop the alignment step to
save time.

Device selection (CPU vs CUDA) is a real fork on speed. Whatever's chosen must be recorded with
the timing numbers, or the A/B speed comparison means nothing.

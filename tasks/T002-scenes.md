# T002 — `scenes.py`: shot detection

**Status:** `not_started`

## Goal

Detect shot boundaries with PySceneDetect and return them as an ordered list of `Shot` objects
with frame-accurate `t_start` / `t_end`.

These timings are load-bearing for the whole index. Everything downstream — transcript slicing,
keyframe extraction, Gemini alignment — is indexed off them.

## Reads / depends on

- `docs/IDEA.md` § *Architecture (Path B)*, § *Definition of done* (bullet 3)
- `docs/architecture.md` § *Division of labour*
- `state/decisions-log.md` **D-002** (shared vs vendored PySceneDetect) and **D-005** (why
  `Shot` is partially populated here)
- Tasks: T006 for the `Shot` model (already seeded in scaffold, so not a hard block).

## Inputs / outputs

**In:** `path: str`.
**Out:** `list[Shot]`, chronological, with only `id`, `t_start`, `t_end` set. Everything else
keeps its model default until T007 fills it.

Ids: `shot_000`, `shot_001`, … zero-padded to at least 3, assigned in `t_start` order.

## Acceptance criteria

- [ ] `detect_shots("in.mp4")` returns shots in ascending `t_start` order.
- [ ] Boundaries are **frame-accurate**, derived from PySceneDetect's frame numbers and the
      container fps — not rounded to whole seconds.
- [ ] Coverage is gapless and non-overlapping: `shots[i].t_end == shots[i+1].t_start` for all
      `i`, and `shots[0].t_start == 0.0`.
- [ ] The final shot's `t_end` equals the video duration (within one frame).
- [ ] A single-shot video (no cuts detected) returns exactly one shot spanning the whole
      duration — not an empty list.
- [ ] Ids are zero-padded and unique, and match the `^shot_[0-9]{3,}$` pattern the schema
      enforces (a 100+ shot video must still validate).
- [ ] Detector and threshold are recorded somewhere reproducible, so Path A can use the same
      ones (see D-002).
- [ ] Raises `FileNotFoundError` with the path when the file doesn't exist.
- [ ] A 10-min video is detected in well under a minute — this stage is not allowed to eat the
      wall-clock budget.

## Constraints that bite here

- **Classical and deterministic. Shared with Path A.** Same detector + same threshold on both
  sides, or the shot lists differ and the A/B diff stops being clean — that's the entire point
  of D-002.
- **Gemini's timestamps are never used for `t_start` / `t_end`.** They're second-granular. This
  module is the only source of those two fields.

## Notes

`ContentDetector` is the default choice; threshold is the tuning knob. Whatever you pick, it must
be written down and shared, not left as an implicit library default — Path A has to match it.

Talking-head footage with no hard cuts is the degenerate case worth testing early: it should
produce one long shot, and the rest of the pipeline should handle that without special-casing.

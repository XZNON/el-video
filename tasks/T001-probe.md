# T001 — `probe.py`: ffprobe wrapper

**Status:** `not_started`

## Goal

Read duration, frame rate, and pixel dimensions out of a video file and return them as a
`VideoMeta`. This fills the `video` block of `footage_index.json` and is the first thing the
pipeline does — every later stage assumes it succeeded.

Small task, deliberately first: it proves the ffmpeg prerequisite is really satisfied on the
machine before anything expensive runs.

## Reads / depends on

- `docs/IDEA.md` § *Scope* (step 1), § *Shared contract* (the `video` block)
- `docs/schema.md` § *`video` — probe output*
- Tasks: none. This is the root of the graph.

## Inputs / outputs

**In:** `path: str` — path to the source video.
**Out:** `VideoMeta(path, duration_s, fps, w, h)` from `elvideo/schema/models.py`.

Shells out to `ffprobe` (ships with ffmpeg, must be on PATH). Suggested invocation:

```
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate \
        -show_entries format=duration -of json <path>
```

## Acceptance criteria

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
- [ ] Unit test covers the `num/den` fps parse and the missing-file path. No fixture video
      needed: mock the subprocess for the parse test.

## Constraints that bite here

- Deterministic, classical, shared with Path A. No model involvement of any kind.
- `video.fps` is the container rate and must not be confused with `index_meta.sample_fps` (the
  rate fed to Gemini). Different fields, different meanings.

## Notes

Rotation metadata is a known trap: some phone footage carries a `rotate` side-data tag, so the
stream's `width`/`height` are pre-rotation and disagree with what a player shows. Out of scope
for the acceptance criteria above — but if the A/B test video turns out to be affected, raise it
as a new task rather than patching it in silently.

# T005 — `quality.py`: OpenCV scoring

**Status:** `not_started`

## Goal

Score each shot's technical quality — sharpness and exposure — from a sampled keyframe, using
OpenCV. Deterministic, no model involved.

This is the counterweight to `editorial_score`: Gemini says whether a moment is *good*, this says
whether the footage is *usable*. A beautifully-composed out-of-focus shot should score high on
one and low on the other.

## Reads / depends on

- `docs/IDEA.md` § *Shared contract* (the `quality` field), § *Storage & speed* (keyframe path)
- `docs/schema.md` § *`shots[]`*
- Tasks: T002 (needs shot boundaries to sample within).

## Inputs / outputs

**In:** `score_frame(img: np.ndarray) -> float`; `score_shot(path, t_start, t_end, work_dir) -> float`.
**Out:** `float` in `0.0`–`1.0`.

Keyframes are written to `{work_dir}/keyframes/shot_###.png` — gitignored runtime output.

## Acceptance criteria

- [ ] `score_frame()` returns a float in `[0.0, 1.0]`, combining Laplacian variance (sharpness)
      with an exposure term.
- [ ] **Deterministic**: the same input array gives a bit-identical result across runs and
      machines. No randomness, no sampling jitter, no LLM.
- [ ] A visibly blurred frame scores measurably lower than its sharp counterpart — assert this
      with a fixture pair (sharp image + `cv2.GaussianBlur` of it), not by eyeball.
- [ ] A blown-out (all-white) and a crushed (all-black) frame both score low on the exposure
      term, and neither produces `NaN` or a divide-by-zero.
- [ ] `score_shot()` extracts a representative frame from inside `[t_start, t_end)` — the
      midpoint is a fine choice, but the choice must be documented and fixed, since it affects
      reproducibility.
- [ ] Keyframes land in `{work_dir}/keyframes/shot_###.png` with ids matching the shot ids.
- [ ] Raises `ValueError` for an empty or non-image array, and when no frame can be read from
      the range.
- [ ] Normalization from raw Laplacian variance (unbounded) to `0-1` is documented — say what
      the saturation point is and why, rather than leaving a magic constant.
- [ ] Scoring 100–300 shots takes seconds, not minutes. It must not eat the wall-clock budget.

## Constraints that bite here

- **No LLM, ever, in this module.** The number must be reproducible so the two A/B indexes are
  byte-comparable on `quality`, and so a change in it is attributable to the footage rather than
  to sampling.
- **Shared with Path A.** Same formula and same normalization constants on both sides, or the
  field is not comparable.
- `work/` is gitignored — keyframes are disposable intermediate output, not artifacts.

## Notes

Laplacian variance is scale- and content-dependent: a low-detail scene (a plain wall) scores like
a blurred one. That's a known limitation of the metric, not a bug to fix here — but it's worth a
line in the A/B writeup, because both paths inherit it equally.

One frame per shot is the s1 approach. Sampling three and taking the median would be more robust
and is a reasonable follow-up, but only if it doesn't push this stage's cost up meaningfully —
`/new-task` it rather than expanding this one.

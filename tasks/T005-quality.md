# T005 — `quality.py`: OpenCV scoring

**Status:** `done` — every criterion met. Formula + constants pinned in D-017, keyframe naming in D-018.

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

- [x] `score_frame()` returns a float in `[0.0, 1.0]`, combining Laplacian variance (sharpness)
      with an exposure term. — `0.7 * sharpness + 0.3 * (brightness × clipping)`, clamped and
      rounded to 4 dp (D-017).
- [x] **Deterministic**: the same input array gives a bit-identical result across runs and
      machines. No randomness, no sampling jitter, no LLM. — `test_deterministic_across_repeated_calls`;
      `ROUND_DIGITS = 4` sits far coarser than cross-CPU SIMD float noise.
- [x] A visibly blurred frame scores measurably lower than its sharp counterpart — assert this
      with a fixture pair (sharp image + `cv2.GaussianBlur` of it), not by eyeball. —
      `test_blur_scores_lower_than_sharp`, gap asserted > 0.1, not merely `<`.
- [x] A blown-out (all-white) and a crushed (all-black) frame both score low on the exposure
      term, and neither produces `NaN` or a divide-by-zero. — both score exactly `0.0`; no
      denominator in the formula can be zero.
- [x] `score_shot()` extracts a representative frame from inside `[t_start, t_end)` — the
      midpoint is a fine choice, but the choice must be documented and fixed, since it affects
      reproducibility. — `SAMPLE_POSITION = 0.5`, asserted frame-for-frame by
      `test_score_shot_samples_the_midpoint`.
- [x] Keyframes land in `{work_dir}/keyframes/shot_###.png` with ids matching the shot ids. —
      via the optional `shot_id` kwarg (**D-018**); timestamp-derived fallback when omitted.
- [x] Raises `ValueError` for an empty or non-image array, and when no frame can be read from
      the range. — empty, wrong channel count, wrong ndim, non-uint8, non-array, unopenable
      video, and bad `[t_start, t_end)` ranges all covered.
- [x] Normalization from raw Laplacian variance (unbounded) to `0-1` is documented — say what
      the saturation point is and why, rather than leaving a magic constant. — `SHARPNESS_SATURATION
      = 1000.0` with the measured distribution and the sqrt-vs-linear comparison in **D-017**.
- [x] Scoring 100–300 shots takes seconds, not minutes. It must not eat the wall-clock budget. —
      **18.8s for 117 shots** (0.161s/shot) including PNG writes: 6% of the 300s budget.

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

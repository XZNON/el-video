# Session 003 — T005: OpenCV quality scoring

## Read these first, in this order

1. `state/progress.json` — what's live, what's blocked
2. Last ~3 entries of `state/session-log.md` — what the previous session left behind
3. `.claude/CLAUDE.md` — hard constraints and session protocol
4. `tasks/T005-quality.md` — in full
5. `docs/IDEA.md` § *Shared contract* (the `quality` field), § *Storage & speed* (keyframe path);
   also `docs/schema.md` § *`shots[]`*

Then run `/start-task T005`.

## Where things stand

Three of the four classical stages are **done** and smoke-tested on the real clip `in.mp4`
(428.11s, 25 fps, 1280×720, has audio):

- **T001 `probe.py`** — ffprobe wrapper.
- **T002 `scenes.py`** — 117 shots in 25.3s at `ContentDetector(threshold=27.0)`, gapless,
  frame-accurate. Settings pinned as module constants (D-012).
- **T003 `transcribe.py`** — 1436 words in 102.7s warm on CPU (ASR 49.5s + alignment 53.2s).
  Settings pinned as module constants (D-015).

Gates green: `pytest -m "not slow"` 35 passed, ruff clean, mypy strict clean. Deps installed.

**The contract is now locked.** T010 closed on 2026-07-26 as a *self-lock*, not a co-founder sync
— the repo is solo, there is no Path A counterparty (**D-016**). D-001 (full index +
`is_candidate`), D-002 (settings pinned rather than shared), D-013 (`index_meta` gained
`scene_detector` + `scene_threshold`), and D-010 (Gemini gets the shot boundaries in its prompt)
are all resolved. `progress.json.blockers` is empty.

**`progress.json` also carries an owner follow-up that is deliberately not actioned:** CLAUDE.md
hard constraint 6 and `docs/IDEA.md` still describe the co-founder repo as a *live* manual-sync
risk. That's aspirational now. Don't act on it unprompted, and **don't "simplify" the A/B-shaped
parts of the schema away** — `path_variant: "gemini" | "local"` and the nullable
`editorial_score` / `moment_reason` are free to keep and a one-way door to remove (D-016).

## This session: T005 — `quality.py`

**Goal:** score each shot's *technical* quality — sharpness and exposure — from a sampled
keyframe, using OpenCV. Deterministic, no model involved.

This is the counterweight to Gemini's `editorial_score`: that says whether a moment is *good*,
this says whether the footage is *usable*. A beautifully-composed out-of-focus shot should score
high on one and low on the other.

**Signatures** (from `docs/IDEA.md` § *Module layout* and the task file):

```python
score_frame(img: np.ndarray) -> float
score_shot(path: str, t_start: float, t_end: float, work_dir: str) -> float
```

**Acceptance criteria** (restated in full — `tasks/T005-quality.md` is authoritative if they
disagree):

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

## Constraints that bite on this task specifically

- **No LLM, ever, in this module.** The number must be reproducible so a change in it is
  attributable to the footage rather than to sampling. `docs/IDEA.md`: quality is deterministic,
  an LLM cannot be.
- **Record the constants the way T002 and T003 did.** Module-level named constants (the
  saturation point, the exposure target, the frame-sampling rule), not magic numbers inline —
  `DEFAULT_THRESHOLD` in `scenes.py` and `DEFAULT_MODEL_SIZE` in `transcribe.py` are the
  precedent, and both are guarded by a test asserting their values.
- **Speed budget.** The <5 min total is dominated by transcription (102.7s) plus the one Gemini
  call. This stage decodes 117 frames out of a 48 MB file — keep it in seconds. Prefer seeking to
  a timestamp over decoding sequentially, and log the stage timing like the other stages do.
- `work/` is **gitignored** — keyframes are disposable intermediate output, not artifacts. It's
  already in `.gitignore` and in ruff's `extend-exclude`.
- Type hints everywhere; docstrings citing `docs/IDEA.md` by section; ruff + mypy strict clean
  before checkpoint. `quality` is a plain float on `Shot`, so this module doesn't import the
  models — but the stub in `elvideo/index/quality.py` already has the signatures and docstrings,
  so start from it rather than rewriting the file.
- **A real tension to settle deliberately, not by accident:** the criterion says keyframes land
  at `{work_dir}/keyframes/shot_###.png` "with ids matching the shot ids", but
  `score_shot(path, t_start, t_end, work_dir)` — the signature fixed by `docs/IDEA.md` — **is
  never given the shot id.** Either derive the name from the timestamp, or add an optional
  `shot_id` keyword with a `None` default (the pattern D-012 and D-010 both used to extend a
  fixed signature without breaking it). Pick one and log it; don't let the filename scheme
  emerge by accident.
- **mypy note (D-011):** numpy is imported under `TYPE_CHECKING` in the existing stub for exactly
  this module, and `python_version = "3.12"` is set because of numpy 2.5's stubs. Don't "fix" the
  version pin if numpy typing complains — read D-011 first.

## Blockers and open decisions affecting this

- **None.** `progress.json.blockers` is empty. Nothing gates this task.
- Known limitation to write down rather than solve: **Laplacian variance is content-dependent** —
  a low-detail scene (a plain wall) scores like a blurred one. That's the metric, not a bug. Worth
  a line in the docstring and eventually in the A/B writeup.
- Explicitly out of scope: sampling three frames per shot and taking the median. More robust, and
  a reasonable follow-up, but `/new-task` it rather than expanding this one.

## Definition of done for the session

- `elvideo/index/quality.py` implemented: `score_frame()` + `score_shot()`, every criterion above
  met or explicitly recorded as not met.
- `tests/test_quality.py` — the sharp-vs-blurred fixture pair, the all-white / all-black exposure
  cases, the `ValueError` paths, and a determinism check. No video fixture needed for
  `score_frame()`; use `in.mp4` for `score_shot()` and skip if absent (`tests/test_scenes.py` has
  the skipif precedent).
- `uv run pytest` passes, `uv run ruff check .` clean, `uv run mypy elvideo` strict clean.
- Smoke-run across all 117 shots of `in.mp4` with the stage wall-clock reported, and the score
  distribution eyeballed — if every shot scores ~0.8, the normalization is wrong, the same way a
  model that scores everything 0.8 is a prompt bug.
- Normalization constants recorded in `state/decisions-log.md` as a new `D-0XX` entry, with the
  measured distribution. Same treatment as D-012 and D-015.

End with `/checkpoint`.

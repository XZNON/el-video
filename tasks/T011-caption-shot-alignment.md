# T011 — Gemini judgments attach to the wrong `shot_index`

**Status:** `not_started`

## Goal

Make a caption describe the shot it is stored on. Today it usually does not: T009's hand
spot-check of 17 shots on `in.mp4` found **2 clean matches, 2 partial, 13 wrong** — the model
watches the video and describes it accurately, then files those descriptions under the wrong shot
indices. At the end of this task, a re-run of the same clip has a **measured** caption/frame
agreement rate, that rate is materially better than 2/17, and the pipeline can tell when the
mapping has gone wrong instead of emitting a schema-valid index that is quietly misaligned.

This is the highest-value defect in the repo. Every downstream claim — "find me the hero shot",
`is_candidate`, the whole A/B argument — is a claim about *which second of footage*, and that is
exactly the part that is currently unreliable.

## Reads / depends on

- `docs/run-report.md` § *The alignment failure* — the evidence, the 17-shot table, and the
  ruled-out explanations
- `state/decisions-log.md` **D-010** (why the shot list is passed as numbered text rather than any
  other way), **D-024** (the `p2` prompt this modifies), **D-019** (pinned call settings), **D-025**
  (the token budget any fix is spending against)
- `docs/IDEA.md` § *Gemini call settings (locked)*, § *Definition of done (s1)*
- Tasks: T004 (`gemini.py`, `done` — this task reopens its output quality, not its interface),
  T009 (`done` — this task exists because of its findings)

## Inputs / outputs

**In:** `in.mp4` plus the 117-shot boundary list from `scenes.detect_shots()` — unchanged, both
already correct.
**Out:** `list[ShotUnderstanding]` from `elvideo/index/gemini.py`, same type as today. **The schema
does not change** — this is an accuracy fix, not a contract change. If a fix turns out to need a
new field, that is a contract change and goes to `state/decisions-log.md` first (hard constraint 6).

## Acceptance criteria

- [ ] A **repeatable measurement** of caption/frame agreement exists and is recorded: N shots
      sampled from `in.mp4` by a fixed rule (not hand-picked), each scored match / partial /
      mismatch against its keyframe, with the sample list committed so a later run compares like
      with like. The T009 baseline for this measure is **2 match / 2 partial / 13 mismatch of 17**.
- [ ] Agreement after the fix is **≥ 12 of 17 clean matches** on that same sample — i.e. the
      failure is the exception, not the rule. A smaller improvement is a legitimate result to
      record, but it does not close this task.
- [ ] The three shots named in `docs/run-report.md` as unambiguous failures — `shot_059`
      (top-scored 0.85, captioned "three men in the back seat", frame shows an empty boot),
      `shot_105` (captioned "presenter exits", frame is a parked car with no presenter), and
      `shot_005` (captioned "walks around the front", frame is a static front-on car) — each either
      match their frames or are demonstrably absent from the fixed sample for a stated reason.
- [ ] **Still exactly one Gemini call per video.** Verified from the counter, not intent. A fix
      that costs two calls fails this criterion regardless of how well it aligns.
- [ ] Token cost after the fix is recorded against the **38,956** baseline. A rise is acceptable if
      it is stated; the free-tier ceiling to stay under is the 250K/min TPM cap, not the old ~30K
      estimate (D-025).
- [ ] `understand()` **detects** a bad mapping rather than trusting it: at minimum, every returned
      `shot_index` is in `[0, len(shots))`, appears at most once, and the response covers every
      shot — with a named exception raised on violation, not a silent pass. (Note whether the
      current run already satisfies this; if it does, index validity was never the failure and the
      check is a regression guard, not the fix.)
- [ ] If `fps` is raised as part of the fix, the new default is justified with the measured
      agreement rate *and* the token cost at both values, and the change is logged as a decision —
      `fps` is a per-video knob and its default is a pinned setting (hard constraint 2, D-019).
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run mypy elvideo` all clean.
- [ ] The result — including a failure to reach ≥12/17 — is written into `docs/run-report.md`
      alongside the T009 numbers, so the two are readable side by side.

## Constraints that bite here

- **One Gemini call per video, never per shot** (hard constraint 1). The obvious fix — ask the
  model about each shot individually — is exactly the design this project exists to avoid, and
  would blow the 10 RPM cap on a 117-shot clip. Any per-shot loop is out of bounds.
- **Free tier only** (hard constraint 2). Each experimental run costs ~39K tokens and ~4 minutes.
  Budget the number of live runs before starting; the prompt-iteration work in D-024 took three.
- **`gemini-3.5-flash` is pinned** (hard constraint 3). "Try a bigger model" is not available.
- **Gemini's own timestamps are never `t_start`/`t_end`** (hard constraint 4). They may legitimately
  be used as a *hint* for matching a judgment to a shot — that is what the `_JudgmentWithHints`
  wire model already exists for — but the boundaries in the output stay PySceneDetect's.
- **The schema is a contract** (hard constraint 6). Fix the values, not the shape.

## Notes

Found in T009 on 2026-07-26, by the one criterion that required a human to look at pictures. It had
been invisible until then: the schema validates, `validate_index()` passes, `t_end > t_start` holds,
the score distribution is healthy (37 distinct values at 2dp), and the slow test's granularity
assertions pass. **Every automated gate in the repo is a shape check, and a caption on the wrong
shot has the right shape.** D-024's `p1 → p2` prompt work fixed score *clustering* and explicitly
noted that "caption quality was never the problem" — true, and beside the point, because nobody had
yet checked whether the captions were on the right shots.

Two hypotheses from the run report, neither yet tested:

1. **Gemini's timestamps are second-granular** while the median shot on `in.mp4` is 2.68s and 36 of
   117 shots are under 2s. The model may simply be unable to resolve the boundary list at the
   granularity the index needs.
2. **`fps=0.5` gives ~214 frames for 117 shots** — 1.8 per shot, and the sub-2s shots get one frame
   or none. A shot the model never saw a frame of still gets a row in the response, and the rubric
   asks it for a confident judgment.

If (2) dominates, raising `--fps` to 1.0 costs roughly +14K visual tokens on this clip and is worth
measuring first because it is one flag. If (1) dominates, the shape of the fix is different —
anchoring on something the model can actually see rather than on a number it has to infer.

**Measure before changing anything.** The report's evidence is 17 hand-checked shots, which is
enough to establish that the problem is real and not enough to attribute a cause. The first unit of
work here is the repeatable measurement in criterion 1, against the *existing* index — a fix
without a baseline cannot be shown to have worked.

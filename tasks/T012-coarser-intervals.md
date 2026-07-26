# T012 — Coarser intervals: ask about ~60 shots instead of 117

**Status:** `not_started` — **recorded as T011's named successor, not scheduled.** Created
2026-07-27 (session 010) by the Path B decision, **D-032**. Nothing here has been run.

## Goal

Test the last untested class of fix for the alignment defect: **change what is asked, not how.**
T011 proved that `gemini-3.5-flash` binding a judgment to one of **117 sub-3-second intervals** is
~60% reliable, and that neither prompt wording nor frame budget closes the rest. The hypothesis
this task tests is that **the model is not bad at watching video — it is bad at telling
near-identical short intervals apart.** 36 of 117 shots on `in.mp4` are under 2s and the median is
2.68s. Give it ~60 intervals a human could actually distinguish and attribution may resolve.

At the end of this task, agreement at a coarser threshold is **measured over at least two runs per
setting on a stated denominator**, and the result — including a failure to beat T011's mean of
10.7/17 — is written up beside the existing numbers.

**This is a product decision, not an accuracy fix.** It changes `shots[]` itself: the index's spine,
its `t_start`/`t_end`, its keyframes. That is why it is a separate task rather than more T011.

## Reads / depends on

- `docs/run-report.md` § *T011 closed — partial by design* — the ceiling, the consumer-trust split,
  and the cost estimate this task inherits. **Do not re-derive the six-run evidence base**; §§ *T011*
  and *T011 continued* hold it.
- `state/decisions-log.md` **D-032** (this task's charter and the two costs it must pay),
  **D-012** (the `ContentDetector` / `--threshold` setting being moved), **D-026** (`--threshold`
  exposed on the CLI), **D-029** (the grading harness), **D-031** (the 20-requests/day quota),
  **D-027** / **D-030** (what is already ruled out)
- `docs/IDEA.md` § *Gemini call settings (locked)*, § *Definition of done (s1)*
- Tasks: T002 (`scenes.py`, the detector this retunes), T011 (`partial` — this task exists because
  of its measured ceiling)

## Inputs / outputs

**In:** `in.mp4`, and a **different** boundary list — `scenes.detect_shots()` at a raised
`ContentDetector` threshold (`python -m elvideo index in.mp4 --threshold 40`), so adjacent micro-cuts
merge.

**Out:** the same `footage_index.json` shape with **different `shots[]` content** — fewer, longer
shots. **The schema does not change** (hard constraint 6): different values, same contract. If this
turns out to need a field recording that shots were merged, that is a contract change and goes to
`state/decisions-log.md` **before** any code.

## The two costs, to be paid before the first run

Both are stated in D-032. Neither is optional.

1. **The frozen 17-shot sample stops being directly comparable.**
   `elvideo/eval/alignment_sample.json` is keyed on `shot_###` ids that will no longer denote the
   same footage — different boundaries means different shots means a different denominator.
   **Solve this before running anything.** The defensible option is to map the old sample's
   *timestamps* onto the new shot list and grade those, then state in the report that the
   denominator changed and why. A number on a silently-changed denominator is worse than no number.
2. **Fewer shots is a worse index for some downstream questions.** A B-roll cutaway that had its own
   1.4s shot can vanish inside a 6s parent. Better attribution is bought with lost granularity, and
   the writeup has to say what was lost, not only what was gained.

## Acceptance criteria

- [ ] The sample-comparability problem has a **stated, implemented solution** before any live run —
      old sample timestamps mapped onto the new shot list, with the changed denominator named in the
      report.
- [ ] At least **two runs per threshold setting**, graded through `elvideo/eval/alignment.py`.
      Report the **mean**, never a single lucky run — T011 saw 13/17 and 6/17 from bit-identical
      inputs (D-030, finding 1).
- [ ] The new shot count and duration distribution are recorded (count, median, how many under 2s)
      beside the 117 / 2.68s / 36 baseline.
- [ ] **Still exactly one Gemini call per video**, from the counter (hard constraint 1).
- [ ] Token cost recorded against the 42,553 mean at `fps=0.5` — fewer shots should mean a shorter
      prompt and a shorter response; say by how much.
- [ ] Wall-clock recorded per stage. The full pipeline is required here (see Constraints), so this
      is a ~235s-per-run task, not a ~100s one.
- [ ] The granularity that was **lost** is stated concretely — at least one named shot present at
      `--threshold 27` and absent at the new setting.
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run mypy elvideo` clean.
- [ ] Result written into `docs/run-report.md` as a fourth section — **extend, do not replace** —
      including the **request count spent**, and including a failure to beat 10.7/17 if that is what
      happens.

## Constraints that bite here

- **The understanding-only shortcut does not apply.** Session 009's driver loads an existing
  `work/footage_index.json` and calls `understand()` directly (~100s instead of 235s). Changing
  `--threshold` changes the boundaries, so **the full pipeline is required every run.**
- **Budget in requests, not tokens** (D-031). 20 `generate_content` calls per project per model per
  day, and **grading shares the pool** — a measured run costs 2. Two thresholds × two runs, graded,
  is **8 of 20**. State the count before starting; session 009 ran out mid-plan.
- **One Gemini call per video, never per shot** (hard constraint 1) — unchanged, and the grading
  harness obeys it too, all pairs in one request.
- **`gemini-3.5-flash` is pinned** (hard constraint 3), **`fps` stays 0.5** (D-030), and **Gemini's
  timestamps are never `t_start`/`t_end`** (hard constraint 4). This task moves exactly one variable:
  the detector threshold.
- **The schema is a contract** (hard constraint 6). Content, not shape.

## Notes

**A negative result closes this task legitimately.** If ~60 coarser intervals do not beat 10.7/17,
that is worth knowing precisely — it would mean the ceiling is a property of the *model's* interval
binding rather than of this footage's cut granularity, which is a stronger and more general claim
than T011 can currently make. Say it with the per-run numbers either way.

**The failure mode to avoid** is drifting back into prompt experiments. That route is measured and
exhausted (D-032's table); re-running it spends the binding resource to reproduce a known number.

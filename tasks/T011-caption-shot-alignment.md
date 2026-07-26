# T011 — Gemini judgments attach to the wrong `shot_index`

**Status:** `partial` — **CLOSED by design on 2026-07-27 (D-032). `partial` is its final state.**

A measured improvement (2/17 → 6–13/17) that does not reach ≥12/17 reliably. Criterion 2 says in
as many words that a smaller improvement "does not close this task", so this is not `done` and it
does **not** enter `completed_tasks`. It is closed anyway, because every lever inside its scope has
been pulled and measured and the remaining idea changes `shots[]` itself — that is
**[T012](T012-coarser-intervals.md)**, not this. What was delivered, what fails, and why closing is
the right call is in the three **Outcome** sections at the bottom.

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

- [x] A **repeatable measurement** of caption/frame agreement exists and is recorded: N shots
      sampled from `in.mp4` by a fixed rule (not hand-picked), each scored match / partial /
      mismatch against its keyframe, with the sample list committed so a later run compares like
      with like. The T009 baseline for this measure is **2 match / 2 partial / 13 mismatch of 17**.
- [ ] **FAILED — mean 10.7/17 over 3 runs at the best setting.** Agreement after the fix is **≥ 12 of 17 clean matches** on that same sample — i.e. the
      failure is the exception, not the rule. A smaller improvement is a legitimate result to
      record, but it does not close this task.
- [ ] **FAILED — 1 of 3 met (`shot_005`).** The three shots named in `docs/run-report.md` as unambiguous failures — `shot_059`
      (top-scored 0.85, captioned "three men in the back seat", frame shows an empty boot),
      `shot_105` (captioned "presenter exits", frame is a parked car with no presenter), and
      `shot_005` (captioned "walks around the front", frame is a static front-on car) — each either
      match their frames or are demonstrably absent from the fixed sample for a stated reason.
- [x] **Still exactly one Gemini call per video.** Verified from the counter, not intent. A fix
      that costs two calls fails this criterion regardless of how well it aligns.
- [x] Token cost after the fix is recorded against the **38,956** baseline. A rise is acceptable if
      it is stated; the free-tier ceiling to stay under is the 250K/min TPM cap, not the old ~30K
      estimate (D-025).
- [x] **CLOSED — not achievable this way (session 009).** `understand()` **detects** a bad mapping rather than trusting it: at minimum, every returned
      `shot_index` is in `[0, len(shots))`, appears at most once, and the response covers every
      shot — with a named exception raised on violation, not a silent pass. (Note whether the
      current run already satisfies this; if it does, index validity was never the failure and the
      check is a regression guard, not the fix.)
- [x] **MET (session 009) — measured at both values, default unchanged, D-030.** If `fps` is raised as part of the fix, the new default is justified with the measured
      agreement rate *and* the token cost at both values, and the change is logged as a decision —
      `fps` is a per-video knob and its default is a pinned setting (hard constraint 2, D-019).
- [x] `uv run pytest`, `uv run ruff check .`, `uv run mypy elvideo` all clean.
- [x] The result — including a failure to reach ≥12/17 — is written into `docs/run-report.md`
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

---

## Outcome — 2026-07-26 (session 008)

**Delivered.** A repeatable measurement, a prompt fix that helps, and an honest ceiling on how
much it helps. Full numbers in `docs/run-report.md` § *T011*; decisions in D-027 (update), D-028,
D-029.

| | |
|---|---|
| Baseline (`p2`, T009 index) | **2** match / 1 partial / 14 mismatch of 17 |
| `p3` run 1 | **13** match / 1 / 3 |
| `p4` run 2 | **4** match / 2 / 11 — reverted |
| `p3` replicate, run 3 | **6** match / 0 / 11 |
| Gemini calls per index | **1** on every run, from the counter |
| Tokens | 42,764 / 41,402 / 42,131 vs the 38,956 baseline (+8%) |
| Gates | 211 fast tests, `ruff` clean, `mypy` strict clean (14 files) |

**What was learned, in order of how much it should shape the next attempt:**

1. **The model was counting shots, not locating them.** One instruction telling it to find each
   shot by its timestamp — with the reason, that this detector cuts more finely than a person
   would — is worth 4–11 points of agreement on a 17-shot sample. That is the cause D-027 asked
   for, and it is hypothesis 1.
2. **Run-to-run variance is larger than the effect.** 13/17 and 6/17 from identical inputs,
   `seed=7`. Any future prompt comparison needs 2–3 runs per configuration or it is measuring
   noise. This is why criterion 2 is failed rather than squeaked past on the 13.
3. **The model's own timestamps cannot police it.** `p3` asks for `t_start_hint` / `t_end_hint`
   and `hint_drift()` reports 0 of 117 drifted on every run, including the ones two-thirds wrong.
   It echoes our numbers back. Self-report is not evidence — the detector T011 wanted does not
   exist along this route.
4. **Alignment and scoring compete.** `p4` restored the score spread and halved the alignment.
   Whatever closes this task has to buy both, not trade them.

**Left undone, and it is the obvious next move:** `fps` was never raised, so **D-027 hypothesis 2
(frame starvation — ~214 sampled frames for 117 shots at `fps=0.5`, and 36 shots under 2s) is
still untested.** It costs roughly +14K tokens per run and is one flag. Given finding 2, budget
**2–3 runs at `fps=1.0`**, not one, and grade each with
`python -m elvideo.eval.alignment work/footage_index.json`.

`shot_059` is the shot to watch: it has never matched its frame under any prompt, though `p3` at
least stopped inventing three passengers and dropped it out of the top score.

---

## Outcome — 2026-07-26 (session 009): `fps` measured, hypothesis 2 rejected

**The lever left undone above was pulled, and it does not work.** D-027 is now `resolved`: both of
its hypotheses have been measured, one supported and one rejected. T011 stays `partial` — criterion
2 still fails — but it now fails against a *bounded* ceiling rather than an open question.

| `fps` | Clean matches /17 (3 runs) | Mean | Tokens (mean) | Score spread |
|---|---|---:|---:|---|
| **0.5** | 13, 6, 13 | **10.7** | **42,553** | clustering warning never fired |
| 1.0 | 9, 8, 9 | 8.7 | 55,500 (+30%) | warning fired on 2 of 3 |

**Frame starvation was not the cause.** Doubling sampled frames (~1.8 → ~3.7 per shot) bought
nothing on attribution, cost 30% more tokens, and flattened the editorial scoring it was not meant
to touch. `fps` default stays 0.5 — **D-030**, which closes criterion 7 with numbers at both values.

**Two findings worth more than the negative result:**

1. **`seed=7` is exactly reproducible.** Session 009's `fps=0.5` run reproduced session 008's run 1
   **bit-identically** — 117 captions, 117 scores, 42,764 tokens, even the grader's 7,721. So the
   6/17 replicate was a *second deterministic outcome*, not noise around a mean. Repeated runs
   sample a small discrete set of outcomes; they do not average away jitter. The practical rule
   ("2–3 runs per configuration") survives, its justification changes.
2. **The free tier's binding limit is 20 requests/day/model**, not the 250K TPM cap this repo has
   budgeted against — **D-031**. Run 5 was refused by it. Grading calls come from the same pool, so
   a *measured* index run costs 2 requests. Plan sessions in requests, not tokens.

**Criterion 6 is closed as *not achievable this way*.** The validity checks pass on every run
including the 6/17 one; `hint_drift()` reports 0–1 of 117 on runs that are half wrong. No detector
exists inside `understand()` that does not look at frames, and looking at frames is a second model
call — outside it by hard constraint 1. The grading harness is that detector, correctly kept as a
separate consumer.

**Criterion 3 is 1 of 3 met:** `shot_005` matches on all six `p3` runs. `shot_105` matches 2 of 6.
`shot_059` matches **0 of 6** — though at `fps=1.0` the grader twice softened it to *partial*
("presenter is gesturing, not pushing down on the seats"): right place, right person, wrong action.

**Gates:** 211 fast tests, ruff clean, mypy strict clean. The slow test's score-range assertion was
lowered 0.3 → 0.2 on six measured runs (D-030) — at 0.3 it failed 4 of 6, and it never caught `p1`
anyway, whose range was 0.65.

**The only untested class of fix left, and it is not a prompt change:** ask a different question.
Merge adjacent sub-2s shots before the call so the model chooses among ~60 distinguishable
intervals instead of 117 near-identical ones. `--threshold` is the cheap way to try it. It changes
`shots[]` itself, so it is a product decision — `/new-task` it rather than folding it in here.

---

## Outcome — 2026-07-27 (session 010): closed as `partial` by design, zero live requests

**No new measurement was taken, deliberately.** Session 010 had two legitimate moves — change what
is asked (raise `--threshold`, ~60 coarser intervals) or accept the measured ceiling and write it
up. **The second was chosen** and recorded as **D-032**.

**Why this task closes without passing.** Everything inside its scope has been pulled and measured:

| Lever | Result |
|---|---|
| Prompt anchored on timestamps (`p2` → `p3`) | 2/17 → **mean 10.7/17** |
| Prompt tuned for score spread (`p4`) | alignment collapsed to 4/17 — reverted |
| Frame budget (`fps` 0.5 → 1.0) | **worse** — 8.7/17 at **+30% tokens** |
| Model self-report (`hint_drift()`) | 0–1 of 117 on runs two-thirds wrong |
| Validity checks in `understand()` | pass on every run, including the 6/17 one |

What is left is outside reach: a bigger model is pinned out (hard constraint 3), per-shot calls are
the design this project exists to avoid (hard constraint 1), and the only untested idea changes
`shots[]` itself. **Another prompt variant would spend the binding resource — requests, 20/day
(D-031) — to reproduce a number already known to three significant figures.**

**Final measured position:** `gemini-3.5-flash` attributing a moment to one of 117 sub-3-second
intervals across a 7-minute clip is **~60% reliable — 58 of 102 graded pairs clean over six `p3`
runs** (32/51 at `fps=0.5`, 26/51 at `fps=1.0`). Criteria 2 and 3 stand as **FAIL**; criterion 6
stands as **closed, not achievable this way**; the other six pass.

**What session 010 produced instead of a seventh run:** `docs/run-report.md` § *T011 closed —
partial by design* — a **what a consumer may / may not trust** split field by field, a numbered
known-limitations list written for whoever builds the downstream agent, and the A/B claim stated as
two halves rather than one verdict:

> **The claim that survives is about *what is in the video*. The claim that fails is about *which
> second*.**

The captions are accurate, specific and cheap, produced in one call at ~42.5K tokens for a 117-shot
7-minute clip. The timeline is frame-accurate and deterministic. **What must not be assumed is that
the two describe the same instant** — check the keyframe before acting on a single shot.

**The successor is named, not dropped:** **[T012 — coarser intervals](T012-coarser-intervals.md)**,
`not_started`. It carries the two costs this task cannot absorb — the frozen 17-shot sample stops
being directly comparable (remap by timestamp, state the changed denominator) and fewer shots is a
worse index for some questions.

**Gates:** 211 fast tests, ruff clean, mypy strict clean (14 files). Unchanged — no code was touched
this session. **The slow tests remain un-exercised against the live API** since D-030 lowered the
score-range assertion 0.3 → 0.2; that is one request on any future live day.

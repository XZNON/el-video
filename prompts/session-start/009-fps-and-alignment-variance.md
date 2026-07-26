# Session 009 — T011 (continued): does `fps` fix the alignment, and can anything here be measured reliably?

## Read these first, in this order

1. `state/progress.json` — `current_task` is **T011**, status **`partial`**. `blockers` is empty;
   `open_decisions` holds **D-027**, which is this task's subject, not an obstacle to it.
2. Last ~3 entries of `state/session-log.md` — especially 2026-07-26 § *T011 · caption ↔
   `shot_index` alignment: measured, improved, not closed*
3. `.claude/CLAUDE.md` — hard constraints and session protocol
4. `tasks/T011-caption-shot-alignment.md` — **in full**, including the **Outcome** section at the
   bottom, which is what the last session actually left behind
5. `docs/run-report.md` § **T011 — caption ↔ `shot_index` alignment** — the four-row results table,
   the negative result on hints, and the variance finding. This is the baseline you are beating.
6. `docs/IDEA.md` § *Gemini call settings (locked)*, § *Definition of done (s1)*
7. `state/decisions-log.md` — **D-027** (the finding, with the T011 update at the end of the
   entry), **D-028** (the `p3` prompt you would be modifying), **D-029** (the grading harness you
   will be running), **D-019** (pinned call settings), **D-025** (the token budget)

Then run `/start-task T011`.

## Where things stand

**T011 is `partial`, not `not_started` and not `done`.** The last session built the measurement it
was missing and used it three times.

**What exists now that did not before:** a repeatable agreement measurement —
`python -m elvideo.eval.alignment work/footage_index.json` grades 17 `(keyframe, caption)` pairs
match / partial / mismatch in **one** Gemini call (~3K tokens) against a frozen sample in
`elvideo/eval/alignment_sample.json`. It was calibrated before being trusted: on the old `p2` index
it returned **2 match / 1 partial / 14 mismatch** and agreed with T009's human column on **16 of
17**. It never increments `gemini.generate_call_count()`.

**What the prompt change bought:** `p3` tells the model to find each shot by its timestamp instead
of counting cuts. Measured, one Gemini call each, `fps=0.5` throughout:

| Index | Prompt | **Clean match /17** | Tokens | Score range |
|---|---|---:|---:|---:|
| T009 baseline | `p2` | **2** | 38,956 | 0.75 |
| Run 1 | `p3` | **13** | 42,764 | 0.27 |
| Run 2 | `p4` | **4** | 41,402 | 0.60 |
| Run 3 | `p3` replicate | **6** | 42,131 | 0.48 |

**The finding that matters most is the third row from the bottom.** `p3` scored 13/17 and then
**6/17 on a replicate of the identical configuration** — same prompt, same `seed=7`, same
`temperature=0.4`. **Run-to-run variance on this measure is larger than most of the effects being
chased.** A single run cannot rank two configurations. Budget 2–3 runs per setting or you are
measuring noise; `p3` vs `p4` at one run each (13 vs 4) is exactly that mistake, preserved in the
table above as a warning.

**Three things are already ruled out — extend them, do not re-litigate:**

- **Keyframes, boundaries and transcripts are correct** (T009, re-verified with `ffmpeg`).
- **Index validity was never the failure.** Range, duplicate and coverage checks in `_check_indices`
  passed on the 2/17 run. They are a regression guard.
- **The model's own timestamps cannot police it.** `p3` requires `t_start_hint`/`t_end_hint`, and
  `hint_drift()` reports **0 of 117** drifted on *every* run, including the ones two-thirds wrong.
  It echoes our numbers back regardless of where it looked. **Self-report is not evidence** — do not
  rebuild a detector on this route.

**The one lever never pulled:** `fps` has been 0.5 for every run ever made. D-027's hypothesis 2 —
~214 sampled frames for 117 shots, 1.8 per shot, and 36 shots under 2s getting one frame or none —
is **completely untested**.

## This session: T011 — finish the attribution, or record why it cannot be finished

**Goal:** test whether frame starvation is what is left of D-027, using enough runs per setting that
the answer means something. Either reach a **stable** ≥12/17 and close T011, or attribute the cause
and record the ceiling honestly.

**Acceptance criteria** (restated in full — `tasks/T011-caption-shot-alignment.md` is authoritative
if they disagree; the first, fourth, fifth, eighth and ninth are already met and must stay met):

- [x] A **repeatable measurement** of caption/frame agreement exists and is recorded, with the
      sample list committed so a later run compares like with like. **Done** —
      `elvideo/eval/alignment.py`, frozen 17-shot sample, grader calibrated 16/17 against the human
      column. Baseline for this measure is **2 match / 1 partial / 14 mismatch of 17**.
- [ ] Agreement is **≥ 12 of 17 clean matches** on that same sample. **Currently 6–13 of 17 across
      two runs of `p3` — failed.** Given the measured variance, treat this as a criterion about the
      *mean of 2–3 runs*, not a single lucky run, and say which you are reporting.
- [ ] The three shots named in `docs/run-report.md` — **`shot_059`** (captioned "three men in the
      back seat" under `p2`, frame shows the presenter at an empty boot), **`shot_105`**, and
      **`shot_005`** — each either match their frames or are demonstrably absent from the sample for
      a stated reason. **Currently: `shot_005` matches on both `p3` runs, `shot_105` on one,
      `shot_059` on none — failed.**
- [x] **Still exactly one Gemini call per video**, verified from the counter. Held on all three runs.
      Grading calls are a separate consumer and must stay out of that counter.
- [x] Token cost recorded against the **38,956** baseline. `p3` costs ~42,100 (+8%). The ceiling is
      the 250K/min TPM cap, not the old ~30K estimate (D-025). Record it again at any new `fps`.
- [ ] `understand()` **detects** a bad mapping rather than trusting it: every returned `shot_index`
      in `[0, len(shots))`, at most once, covering every shot, with a named exception on violation.
      **Partial** — those checks exist and already passed on the failing run, and the `hint_drift()`
      route is a dead end (see above). If you find a detector that actually fires on a misaligned
      run, that is a genuinely new result; if you conclude none is possible without looking at
      frames, say so and close the criterion as *not achievable this way*.
- [ ] If `fps` is raised, the new default is justified with the measured agreement rate **and** the
      token cost at both values, and logged as a decision — `fps` is a per-video knob and its
      default is a pinned setting (hard constraint 2, D-019). **This is the criterion this session
      is most likely to be able to close.**
- [x] `uv run pytest`, `uv run ruff check .`, `uv run mypy elvideo` all clean. **Currently 211 fast
      tests pass, ruff clean, mypy strict clean (14 files)** — keep it that way.
- [x] The result — including a failure to reach ≥12/17 — is written into `docs/run-report.md`
      alongside the T009 numbers. **Done for session 008; extend that section, do not replace it.**

## Constraints that bite on this task specifically

- **One Gemini call per video, never per shot** (hard constraint 1). Any per-shot loop is out of
  bounds however well it aligns. The grading harness obeys this too — all 17 pairs in one request.
- **Free tier only** (hard constraint 2). An index run is ~42K tokens and ~100s via the experiment
  path; a grading call is ~3K. **Decide the run budget before starting.** At 2–3 runs per `fps`
  setting, testing 0.5 vs 1.0 properly is 4–6 index runs, ~250K tokens total. That is affordable
  against a 250K/min TPM cap spread over a session, but it is not free — say the number up front.
- **`fps` at 1.0 costs roughly +14K visual tokens per run** on this clip, taking a run to ~56K.
  Still far under the cap.
- **`gemini-3.5-flash` is pinned** (hard constraint 3). "Try a bigger model" is not on the table.
- **Gemini's own timestamps are never `t_start`/`t_end`** (hard constraint 4) — and, as of last
  session, are not trustworthy as hints either.
- **The schema is a contract** (hard constraint 6). This is an accuracy fix. A new field goes to
  `state/decisions-log.md` first.
- **Do not re-run the full pipeline to test the understanding stage.** Boundaries, transcripts and
  quality scores are already in `work/footage_index.json`; loading them and calling `understand()`
  directly costs ~100s instead of 235s and spends no extra quota. The last session used a driver in
  the scratchpad — rebuild it, it is ~40 lines.

## Blockers and open decisions affecting this

- **No blockers.** `blockers` in `progress.json` is empty, the key works, and no 429 was seen
  across 7 calls last session.
- **D-027 is `open`** and is this task's subject. Read the **Update** at the end of the entry:
  hypothesis 1 (the model was counting shots, not locating them) is **supported**; hypothesis 2
  (frame starvation) is **untested**. It closes when hypothesis 2 is measured or the fix is stable
  at ≥12/17 — not when the numbers happen to look better.
- **A slow test is now a coin-flip and it was left that way on purpose.** `tests/test_gemini.py`
  asserts `max(scores) - min(scores) > 0.3`; `p3` produced **0.27** on one run and 0.48 on another.
  Loosening a D-024 regression guard on two samples would be tuning the test to the run. If this
  session gathers more runs, it will have the evidence to set that threshold honestly — do that
  rather than deleting the assertion.
- **Alignment and scoring compete for the model's attention.** `p4` restored the score spread and
  halved the alignment. Any prompt work has to buy both, and has to prove it over multiple runs.
- The D-016 owner follow-up (`.claude/CLAUDE.md` hard constraint 6 and `docs/IDEA.md` still describe
  a Path A counterparty that does not exist) is still open and still blocks nothing.

## Definition of done for the session

`fps=1.0` has been measured on the frozen sample with **at least two runs**, its token cost is
recorded next to the `fps=0.5` numbers in `docs/run-report.md`, and D-027 either moves to
`resolved` with hypothesis 2 attributed or stays `open` with the measurement that failed to settle
it. The call count is still 1 per index from the counter, and `uv run pytest` /
`uv run ruff check .` / `uv run mypy elvideo` are clean.

If the agreement rate reaches a **stable** ≥12/17 and `shot_059` matches its frame, T011 closes and
`fps` gets a decision entry. If it does not, T011 stays `partial` and the report says so — with the
per-run numbers, not an average that hides the spread.

**A session that measures honestly and does not reach ≥12/17 is a good session. A session that
reports a single lucky run as a result is not** — the last one nearly did, and the replicate is the
only reason it didn't.

End with `/checkpoint`.

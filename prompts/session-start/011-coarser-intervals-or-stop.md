# Session 011 — T012: coarser intervals. Optional work on a finished repo.

**Read the "Where things stand" section before deciding to do anything at all.** s1 is finished and
written up. T012 is a real experiment, not an obligation, and starting it costs 8 of the day's 20
free-tier requests.

## Read these first, in this order

1. `state/progress.json` — `current_task` is **T012**, status **`not_started`** (with a
   `status_note` explaining why that is not one of `/checkpoint`'s four values). Read the
   `closed_2026_07_27_session_010` block, the `consumer_contract` block, and `next_task`.
2. Last ~3 entries of `state/session-log.md` — especially 2026-07-27 § *Path B: accept the ceiling,
   write it up*
3. `.claude/CLAUDE.md` — hard constraints and session protocol
4. `tasks/T012-coarser-intervals.md` — **in full**, including the *two costs, to be paid before the
   first run*
5. `docs/run-report.md` § **T011 closed — partial by design** — the consumer-trust split and the A/B
   claim this task would revise. §§ *T011* and *T011 continued* hold the six-run evidence base;
   **do not re-derive it.**
6. `docs/IDEA.md` § *Gemini call settings (locked)*, § *Definition of done (s1)*
7. `state/decisions-log.md` — **D-032** (why T011 closed and what T012 is chartered to do),
   **D-012** (the `ContentDetector` threshold this task moves), **D-026** (`--threshold` on the CLI),
   **D-031** (the 20-requests/day quota — read before planning any live run), **D-029** (the grading
   harness), **D-027** and **D-030** (what is already ruled out, so it is not retried)

Then run `/start-task T012`.

## Where things stand

**s1 is complete and coherent as it stands.** The pipeline runs end to end on a free-tier key:
`python -m elvideo index in.mp4` produces a schema-valid 117-shot index in **234.7s** with **one**
Gemini call and ~42.5K tokens. T001–T010 are `done`.

**T011 is closed at `partial`, by design, and is not coming back** (D-032). Its measured statement:
`gemini-3.5-flash` attributing a moment to one of **117 sub-3-second intervals** across a 7-minute
clip is **~60% reliable — 58 of 102 graded pairs clean over six `p3` runs**. Prompt anchoring bought
~9 matches of 17; frame budget bought none and cost 30% more tokens; the model's self-report detects
nothing. Session 010 spent **zero** requests and produced the writeup instead: what a consumer may
trust, what it may not, and the A/B claim split in two — **what is in the video holds, which second
does not.**

**T012 is the one untested class of fix, and it is optional.** It changes `shots[]` itself, so it is
a product decision: better attribution bought with lost granularity. **Deciding not to run it is a
legitimate way to end this session** — say so, record it, and stop. What is not legitimate is
drifting back into prompt experiments; that route is measured and exhausted.

## This session: T012 — coarser intervals: ask about ~60 shots instead of 117

**Goal:** test whether the model is bad at *watching video* or merely bad at *telling 117
near-identical short intervals apart*. 36 of 117 shots on `in.mp4` are under 2s and the median is
2.68s. Raise the detector threshold (`python -m elvideo index in.mp4 --threshold 40`) so adjacent
micro-cuts merge into ~60 intervals a human could distinguish, and measure whether attribution
resolves.

**State the request count before spending anything.** Two thresholds × two runs, graded, is
**8 of the day's 20** (D-031). Confirm the quota has reset first.

**Acceptance criteria** (restated in full — `tasks/T012-coarser-intervals.md` is authoritative if
they disagree):

- [ ] The sample-comparability problem has a **stated, implemented solution before any live run** —
      `elvideo/eval/alignment_sample.json` is keyed on `shot_###` ids that will no longer denote the
      same footage. Map the old sample's **timestamps** onto the new shot list, grade those, and name
      the changed denominator in the report. A number on a silently-changed denominator is worse than
      no number.
- [ ] At least **two runs per threshold setting**, graded through `elvideo/eval/alignment.py`.
      Report the **mean**, never a single lucky run — T011 saw 13/17 and 6/17 from bit-identical
      inputs.
- [ ] The new **shot count and duration distribution** are recorded (count, median, how many under
      2s) beside the 117 / 2.68s / 36 baseline.
- [ ] **Still exactly one Gemini call per video**, verified from the counter, not from intent.
- [ ] **Token cost** recorded against the 42,553 mean at `fps=0.5` — fewer shots should mean a
      shorter prompt and response; say by how much.
- [ ] **Wall-clock recorded per stage.** The full pipeline is required here, so this is ~235s per
      run, not ~100s.
- [ ] The granularity that was **lost** is stated concretely — at least one named shot present at
      `--threshold 27` and absent at the new setting.
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run mypy elvideo` all clean.
- [ ] Result written into `docs/run-report.md` as a **fifth** section — extend, do not replace —
      including the **request count spent**, and including a failure to beat 10.7/17 if that is what
      happens.

## Constraints that bite on this task specifically

- **The understanding-only shortcut does not apply here.** Session 009's driver loads an existing
  `work/footage_index.json` and calls `understand()` directly (~100s instead of 235s). Changing
  `--threshold` changes the boundaries, so **the full pipeline runs every time.**
- **Budget in requests, not tokens** (D-031). 20 `generate_content` calls per project per model per
  day, and **grading shares the pool** — a measured run costs 2. Session 009 ran out mid-plan.
- **One Gemini call per video, never per shot** (hard constraint 1). The grading harness obeys it
  too — all pairs in one request.
- **`gemini-3.5-flash` is pinned** (hard constraint 3). **`fps` stays 0.5** (D-030). **Gemini's own
  timestamps are never `t_start`/`t_end`** (hard constraint 4) and are not usable as hints either.
  This task moves **exactly one variable**: the detector threshold.
- **The schema is a contract** (hard constraint 6). `shots[]` gets different *content*, not a
  different *shape*. If a field is needed to record that shots were merged, that goes to
  `state/decisions-log.md` **before** any code.
- **Free tier only** (hard constraint 2), local filesystem only (hard constraint 5).

## Blockers and open decisions affecting this

- **No blockers.** `blockers` is empty and `open_decisions` is empty.
- **A live constraint:** confirm the 20-request daily quota has reset before planning runs. Session
  010 spent none, session 009 spent all 20 on 2026-07-26.
- **The slow tests have still never been exercised against the live API.** `tests/test_gemini.py`'s
  score-range assertion moved 0.3 → 0.2 on six recorded runs (D-030). If this session makes any live
  call, `uv run pytest -m slow` is worth one of the 20.
- **Two items sit with the owner and block nothing:** D-016 (`.claude/CLAUDE.md` hard constraint 6
  and `docs/IDEA.md` still describe a Path A counterparty that does not exist) and D-031
  (`docs/IDEA.md`'s "TPM cap 250K/min → iterate freely all day", contradicted by the daily request
  cap). Both logged rather than silently edited, per the CLAUDE.md conflict rule.

## Definition of done for the session

**If T012 is run:** the sample-comparability solution is implemented and stated, at least two runs
per threshold are measured and graded, the shot-count distribution and the lost granularity are both
recorded, `docs/run-report.md` gains a fifth section naming the request count spent, and T012's
status reflects the outcome — including `partial` or a recorded negative result if ~60 intervals do
not beat **10.7/17**. **A negative result closes T012 legitimately**: it would mean the ceiling is a
property of the model's interval binding rather than of this footage's cut, which is a stronger and
more general claim than T011 can currently make.

**If T012 is declined:** say so explicitly, record the decision in `state/decisions-log.md` with the
reasoning (granularity loss not worth the attribution gain, or the request budget better spent
elsewhere), set T012's status accordingly, and stop. **s1 needs nothing further to be coherent.**

Either way: `uv run pytest` / `uv run ruff check .` / `uv run mypy elvideo` clean, and the call count
still 1 per index from the counter.

End with `/checkpoint`.

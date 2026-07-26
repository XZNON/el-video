# Session 010 — T011 is out of cheap levers. Decide: coarser shots, or accept the ceiling.

## Read these first, in this order

1. `state/progress.json` — `current_task` is **T011**, status **`partial`**. `blockers` is empty and
   **`open_decisions` is empty for the first time since T009.** Read `next_task` and
   `t011_closure_note`: they frame this session's choice.
2. Last ~3 entries of `state/session-log.md` — especially 2026-07-26 § *T011 continued · `fps`
   measured, D-027 resolved, and the real quota found*
3. `.claude/CLAUDE.md` — hard constraints and session protocol
4. `tasks/T011-caption-shot-alignment.md` — **in full**, including **both** Outcome sections at the
   bottom (session 008 and session 009). They are what the last two sessions actually left behind.
5. `docs/run-report.md` § **T011 — caption ↔ `shot_index` alignment** and § **T011 continued —
   `fps` tested**. The second section's six-run table is the evidence base; do not re-derive it.
6. `docs/IDEA.md` § *Gemini call settings (locked)*, § *Definition of done (s1)*
7. `state/decisions-log.md` — **D-027** (now `resolved`; read both Updates), **D-030** (`fps` stays
   0.5, and the slow test's lowered threshold), **D-031** (the 20-requests/day quota — read this
   before planning any live run), **D-028** (the `p3` prompt), **D-029** (the grading harness),
   **D-012** (the `--threshold` / `ContentDetector` setting a coarser-shots experiment would move)

Then run `/start-task T011`.

## Where things stand

**T011 is `partial` and every cheap lever has been pulled and measured.** This is not a session that
picks up where the last one left off — it is a session that decides whether T011 continues at all.

**What is settled, with numbers. Do not re-litigate any of it:**

| Finding | Evidence |
|---|---|
| Boundaries, keyframes and transcripts are correct | T009, re-verified with `ffmpeg` |
| Index validity was never the failure | range / duplicate / coverage checks pass on the 6/17 run |
| The model's self-report cannot police it | `hint_drift()` = 0–1 of 117 on runs that are half wrong |
| The model was counting shots, not locating them | `p2` → `p3` moved 2/17 → mean 10.7/17 |
| **Frame starvation is NOT the cause** | `fps=1.0` scores 9/8/9 vs `fps=0.5`'s 13/6/13, at +30% tokens |
| `seed=7` is exactly reproducible | one run reproduced an earlier one bit-identically, tokens and all |
| The free tier's binding limit is requests, not tokens | **20 `generate_content`/day/model** (D-031) |

**The measured ceiling:** `gemini-3.5-flash` attributing a moment to one of **117 sub-3-second
intervals** across a 7-minute clip is roughly **60% reliable** (mean 10.7 of 17 clean matches).
Prompt work bought ~9 of those matches. Sample rate bought none. **Criterion 2 (≥12/17) and
criterion 3 (`shot_059`) still fail**, criterion 6 is closed as *not achievable this way*, and
criterion 7 is met.

## This session: pick one of two paths, and say which up front

Both are legitimate. Neither is a fallback for the other. **Decide before spending a single live
request, and record the choice in `state/decisions-log.md` either way.**

### Path A — change *what is asked*, not how (the last untested class of fix)

**The hypothesis:** the model is not bad at watching video, it is bad at telling 117 near-identical
short intervals apart. 36 of 117 shots on `in.mp4` are under 2s and the median is 2.68s. Give it
~60 intervals that a human could actually distinguish and attribution may resolve.

**The one flag:** `--threshold` on the CLI (D-012, D-026), which raises `ContentDetector`'s
sensitivity floor so adjacent micro-cuts merge. `python -m elvideo index in.mp4 --threshold 40`.

**What makes this different from everything already tried:** it changes `shots[]` itself — the
artifact's spine, `t_start`/`t_end`, the keyframes, the whole index. That is a **product decision**,
not a prompt tweak, and it has real costs to state honestly:

- **The frozen 17-shot sample stops being directly comparable.** Different boundaries means
  different shots means a different denominator. `elvideo/eval/alignment_sample.json` is keyed on
  `shot_###` ids that will no longer mean the same footage. **Solve this before running anything** —
  the most defensible option is to map the old sample's *timestamps* onto the new shot list and
  grade those, stating in the report that the denominator changed and why.
- **Fewer shots is a worse index for some downstream questions**, not just a better one for
  attribution. A B-roll cutaway that lived in its own 1.4s shot may vanish into a 6s parent.
- **This is arguably out of T011's scope** — its Inputs/Outputs section says the boundary list is
  "unchanged, both already correct". If you take this path, **`/new-task` it** rather than
  stretching T011, and say so in the decisions log.

**Budget it in requests (D-031):** a full pipeline run at a new threshold is 1 index request; each
grading is 1 more. Two thresholds × 2 runs each, graded, is **8 requests of the day's 20** — plus
~235s of wall clock per run, because changing boundaries means the full pipeline, not the
understanding-only driver.

### Path B — accept the ceiling and write it up

**The case for it:** the number is measured, bounded from two directions, and honest. Part 1's job
per `docs/IDEA.md` § *Definition of done (s1)* is a working video → index → local store pipeline
with an A/B claim about Gemini-native understanding. That pipeline works: one call, ~42K tokens,
234.7s, schema-valid, frame-accurate boundaries. **The claim that holds is about *what is in the
video*; the claim that does not hold is about *which second*.** Saying so precisely is a real
result, not a concession.

**What this session would produce:** T011 closed as **partial-by-design** with an explicit
statement of what a consumer may and may not trust; a short "known limitations" section that a
downstream agent author would actually read; and the coarser-shots idea recorded as the named
successor experiment rather than silently dropped. **Zero live requests.**

## Acceptance criteria (T011, current state — the task file is authoritative)

- [x] A repeatable measurement exists, sample committed — `elvideo/eval/alignment.py`, frozen
      17-shot sample, grader calibrated 16/17 against the human column
- [ ] **FAILED** — ≥ 12 of 17 clean matches. Best setting is `fps=0.5`, **mean 10.7/17** over three
      runs (13/6/13). Report the mean of 2–3 runs, never a single lucky run
- [ ] **FAILED, 1 of 3 met** — `shot_005` matches on all six `p3` runs; `shot_105` on 2 of 6;
      **`shot_059` on 0 of 6** (softened to *partial* twice at `fps=1.0`: right place, right person,
      wrong action)
- [x] Exactly one Gemini call per video, from the counter — held on all six runs
- [x] Token cost recorded against the 38,956 baseline — 42,553 mean at `fps=0.5`, 55,500 at `fps=1.0`
- [x] **CLOSED as not achievable this way** — `understand()` detects a bad mapping. The validity
      checks pass on every run including the 6/17 one; no detector exists that does not look at
      frames, and that is a second model call, outside `understand()` by hard constraint 1
- [x] **MET** — `fps` justified with agreement *and* token cost at both values, logged as **D-030**;
      default stays 0.5
- [x] `uv run pytest`, `uv run ruff check .`, `uv run mypy elvideo` all clean — 211 fast tests, ruff
      clean, mypy strict clean (14 files). Keep it that way
- [x] Result written into `docs/run-report.md` beside the T009 numbers — two sections now; **extend,
      do not replace**

## Constraints that bite on this task specifically

- **One Gemini call per video, never per shot** (hard constraint 1). Unchanged, and the grading
  harness obeys it too — all 17 pairs in one request.
- **The daily quota is 20 requests, and grading calls share the pool** (D-031). This is the
  constraint that actually stops a session. **State the request count before starting**, not the
  token count. Session 009 ran out mid-plan.
- **Free tier only** (hard constraint 2). `fps` stays 0.5 (D-030) unless the footage genuinely
  differs — it is still a per-video knob, just not a fix for attribution.
- **`gemini-3.5-flash` is pinned** (hard constraint 3). "Try a bigger model" remains unavailable.
- **Gemini's own timestamps are never `t_start`/`t_end`** (hard constraint 4), and are not usable as
  hints either.
- **The schema is a contract** (hard constraint 6). Path A changes `shots[]`'s *content*, not its
  *shape* — but if it needs a new field (e.g. recording that shots were merged), that goes to
  `state/decisions-log.md` first.
- **Do not re-run the full pipeline to test the understanding stage.** The session-009 driver
  (~110 lines, scratchpad) loads `work/footage_index.json` and calls `understand()` directly:
  ~100s instead of 235s. **It does not apply to Path A** — changing `--threshold` changes the
  boundaries, so the full pipeline is required there.

## Blockers and open decisions affecting this

- **No blockers.** `blockers` is empty and **`open_decisions` is empty** — D-027 resolved this
  session, D-030 and D-031 were resolved as written.
- **A live constraint, not a blocker:** the 20-request daily quota was spent on 2026-07-26. Confirm
  it has reset before planning live runs.
- **The slow tests have not been re-run since the threshold change.** `tests/test_gemini.py`'s
  score-range assertion moved 0.3 → 0.2 on six recorded runs (D-030) but has **not** been exercised
  against the real API. If this session makes any live call, `uv run pytest -m slow` is worth one of
  the 20 requests.
- **Two items sit with the owner and block nothing:** D-016 (`.claude/CLAUDE.md` hard constraint 6
  and `docs/IDEA.md` still describe a Path A counterparty that does not exist), and now D-031
  (`docs/IDEA.md`'s "TPM cap is 250K/min → iterate freely all day", which the daily request cap
  contradicts). Both were logged rather than silently edited, per the CLAUDE.md conflict rule.

## Definition of done for the session

**Path A:** a new task file exists for the coarser-shots experiment, the sample-comparability
problem has a stated solution, at least two runs at the new threshold are measured and graded, and
`docs/run-report.md` gains a third section with the request count spent. T011 itself stays
`partial` unless the result is a stable ≥12/17 on a stated denominator.

**Path B:** T011 is closed as `partial` **by design**, with a "what a consumer may trust" statement
in `docs/run-report.md`, the coarser-shots idea recorded as the named successor, and the A/B writeup
saying precisely which half of the Path B claim holds. `completed_tasks` does **not** gain T011 —
its criteria still fail, and the closure is a scope decision, not a pass.

Either way: `uv run pytest` / `uv run ruff check .` / `uv run mypy elvideo` clean, and the call
count still 1 per index from the counter.

**A session that picks Path B deliberately and argues it is a good session.** So is one that picks
Path A and fails to beat 10.7/17, provided it says so with the per-run numbers. The failure mode to
avoid is drifting into more prompt experiments — that route is measured and exhausted.

End with `/checkpoint`.

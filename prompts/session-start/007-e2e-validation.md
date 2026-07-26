# Session 007 — T009: E2E validation on the A/B test video

## Read these first, in this order

1. `state/progress.json` — what's live, what's blocked (`blockers` and `open_decisions` are both
   empty; the `build`, `gemini` and `cli` blocks hold the numbers this task has to report)
2. Last ~3 entries of `state/session-log.md` — what the previous sessions left behind
3. `.claude/CLAUDE.md` — hard constraints and session protocol
4. `tasks/T009-e2e-validation.md` — **in full**, including its "Known before you start" table
5. `docs/IDEA.md` § *Definition of done (s1)*, § *Gemini call settings*, § *Storage & speed*
6. `state/decisions-log.md` — **D-003** (the test video), **D-025** (the ~38K token finding),
   **D-024** (prompt `p1` → `p2`), **D-019** (pinned call settings)

Then run `/start-task T009`.

## Where things stand

**The pipeline is finished and has been run end to end for real.** Every module is implemented and
every task except this one is `done`. `python -m elvideo index in.mp4` produced a validated
117-shot `work/footage_index.json` on 2026-07-26 in **234.7s**, with **one** Gemini call and
**38,956 tokens**. Gates at last checkpoint: `pytest -m "not slow"` **191 passed**, `ruff` clean,
`mypy elvideo` strict clean.

**So T009 is mostly a writing task, not a measuring one.** The numbers exist; what does not exist
is a report in a **tracked** file (`work/` is gitignored) and a human having actually looked at the
captions. Re-running the pipeline is optional — one live run costs ~38K free-tier tokens and ~4
minutes, and the recorded numbers are current. Re-run only if you change something that could move
them.

**Measured on `in.mp4` (7:08, 1280x720, 25 fps), laptop, cpu-only torch 2.8.0:**

| | |
|---|---|
| Wall clock | **234.7s** (78% of the 300s budget) |
| Per stage | probe 0.05s · shots 20.95s · transcript 107.76s · **understand 86.77s** · quality 19.04s · join 0.01s · validate 0.06s · write 0.02s |
| Understand, inside | upload 18.7s + call 64.9s |
| Gemini calls | **1** (read back from the counter, not assumed) |
| Tokens | **38,956** = prompt 27,693 + output 11,263 |
| Shots / words | 117 / 1436 |
| `editorial_score` | min 0.10 · median 0.61 · max 0.85 · 37 distinct at 2dp |
| Candidates | 43 of 117 at the 0.65 threshold (D-023) |
| Settings | `fps=0.5`, `media_resolution=low`, `threshold=27.0`, model `gemini-3.5-flash`, prompt `p2` |

## This session: T009 — E2E validation

**Goal:** turn "it works" into evidence. Prove every Definition-of-Done claim with a number in a
file someone else can read, and confirm by hand that the captions describe what is actually on
screen — schema validity proves shape, not sense.

**Acceptance criteria** (restated in full — `tasks/T009-e2e-validation.md` is authoritative if they
disagree):

- [ ] `python -m elvideo index in.mp4` produces a `footage_index.json` that **validates against
      the shared schema**.
- [ ] **Exactly one Gemini call** for the video — verified from the logged call counter, not
      assumed.
- [ ] Full shot list with `t_start` / `t_end` frame-accurate, from PySceneDetect.
- [ ] `words[]` present with word-level timing.
- [ ] Runs on a **free-tier** key, **≤ ~30K tokens**, **no 429** on a single video.
- [ ] **Per-stage timing logged**, and total wall-clock **<5 min**.
- [ ] Same command, same schema output as Path A → A/B-ready.
- [ ] The run report is committed (`work/` is gitignored — put it somewhere tracked, e.g. `docs/`
      or the session log).
- [ ] Actual token count recorded against the ~30K estimate. A large miss is a finding worth
      writing down, not a number to quietly round.
- [ ] `editorial_score` values are **spread**, not clustered at one value — a model scoring
      everything `0.8` passes schema validation while being useless.
- [ ] Spot-check ~5 shots by hand: does the caption describe what's actually on screen, and does
      `moment_reason` justify its score?
- [ ] The exact `fps` and `media_resolution` used are recorded, since they're per-video knobs.

**Two criteria will not pass as written, and that is the expected outcome — record it, don't
engineer around it:**

1. **"≤ ~30K tokens" fails: the real cost is ~38–39K.** D-025 already diagnosed why — the spec's
   estimate counted sampled frames and omitted the audio track, which Gemini bills per second
   regardless of `fps` or `media_resolution`. The task file says so explicitly: *"If the token
   count comes in at 60K, the useful output is the measured number plus the reason, not a tuned
   run that hits 30K by shortening the video."* Report ~39K against a corrected ~40K target.
2. **"Same schema output as Path A" cannot be verified.** There is no Path A counterparty — D-016
   resolved this repo as solo, and the contract decisions are owner-locked. Mark it not-verifiable
   with the reason rather than ticking or silently dropping it.

**One more caveat that belongs in the report:** `in.mp4` is **7:08, not 10:00**. Transcription and
quality scale with duration, so a true 10-minute clip projects to roughly **300–330s — at or just
over the 300s budget**. 234.7s is a real pass on the agreed test video, not proof of headroom.

## Constraints that bite on this task specifically

- **Free tier only.** If the run needs a paid key, that is a finding, not a workaround to route
  around.
- **No 429 on a single video.** One 429 that backoff silently absorbed still means the design sits
  closer to the cap than intended — log it either way. `gemini.py` retries up to 5 times with
  exponential backoff (D-020), so a 429 will not necessarily be visible in the exit code.
- **One Gemini call per video.** `build_index` reads the counter back and aborts on anything but 1;
  the report should quote the counter, not the intent.
- **Gemini's timestamps are never `t_start` / `t_end`** — those come from PySceneDetect and the
  join is an index lookup on `shot_index` (D-010). Verifying frame-accuracy means checking against
  the detector, not against the model's hints.
- **Local filesystem only.** The report goes in the repo, not a cloud doc.
- **`work/` is gitignored** — a report written there does not satisfy the "committed" criterion.

## Blockers and open decisions affecting this

- **None.** `blockers` and `open_decisions` in `progress.json` are both empty, and the API key
  works.
- The D-016 owner follow-up — `.claude/CLAUDE.md` hard constraint 6 and `docs/IDEA.md` still
  describe the co-founder's Path A repo as a live sync risk, which it is not — is still open and
  still blocks nothing. It only matters here because it is why the A/B criterion cannot pass.

## Definition of done for the session

A tracked report file exists (suggested: `docs/run-report.md`) carrying the command, the machine,
the per-stage timings, the token count against the corrected target, the call count, the score
distribution, and the five hand-checked shots quoted with their captions and `moment_reason`. Every
criterion above is marked pass / fail / not-verifiable **with its reason**, including the two that
fail. `tasks/T009-e2e-validation.md` reflects the same verdicts, and `uv run pytest`,
`uv run ruff check .` and `uv run mypy elvideo` are all clean.

If a criterion fails, T009 still closes — with the failure recorded. A tuned run that hits 30K by
shortening the clip would be the wrong outcome.

End with `/checkpoint`.

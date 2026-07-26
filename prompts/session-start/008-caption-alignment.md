# Session 008 — T011: caption ↔ `shot_index` alignment

## Read these first, in this order

1. `state/progress.json` — what's live and what's blocked (`blockers` is empty; `open_decisions`
   holds **D-027**, which is this task's subject, not an obstacle to it)
2. Last ~3 entries of `state/session-log.md` — what the previous sessions left behind
3. `.claude/CLAUDE.md` — hard constraints and session protocol
4. `tasks/T011-caption-shot-alignment.md` — **in full**
5. `docs/run-report.md` § *The alignment failure* — the 17-shot evidence table, the ruled-out
   explanations, and the two hypotheses. This is the baseline you are trying to beat.
6. `docs/IDEA.md` § *Gemini call settings (locked)*, § *Definition of done (s1)*
7. `state/decisions-log.md` — **D-027** (the finding), **D-010** (why the shot list is passed as
   numbered text), **D-024** (the `p2` prompt you would be modifying), **D-019** (pinned call
   settings), **D-025** (the token budget any fix spends against)

Then run `/start-task T011`.

## Where things stand

**The s1 pipeline is finished and structurally correct.** T001–T010 are all `done`. A real run of
`python -m elvideo index in.mp4` on 2026-07-26 produced a validated 117-shot index in **234.7s**
with **one** Gemini call and **38,956 tokens** on a free-tier key, no 429. Shot boundaries are
frame-accurate (0 of 234 values off the 1/25s grid), `words[]` carries 1,436 word-level timings,
and the score distribution is healthy (37 distinct values at 2dp). Gates: `pytest -m "not slow"`
**191 passed**, `ruff` clean, `mypy elvideo` strict clean.

**And it is substantively wrong in one place.** T009's hand spot-check — the one criterion that
required a human to look at frames — found that the captions and scores are attached to the
**wrong shots**. 17 shots checked against their keyframes: **2 clean matches, 2 partial, 13
mismatches.** The top-scored shot in the whole clip (`shot_059`, 0.85, "three men sit side-by-side
in the back seat and give a thumbs up") is a frame of the presenter standing at an empty boot.

**Nothing automated caught this and nothing automated would have.** The schema validates,
`validate_index()` passes, `t_end > t_start` holds, the anti-clustering assertions pass. Every gate
in the repo is a shape check, and a caption on the wrong shot has the right shape.

**What was already ruled out** — do not re-litigate it, extend it:

- **Keyframes and boundaries are correct.** Frames re-extracted with
  `ffmpeg -ss <midpoint> -frames:v 1` for shots 025, 059 and 105 are identical to what
  `quality.score_shot()` wrote.
- **`transcript` is unaffected.** It joins by time window from WhisperX and matches the picture on
  the same shots whose captions are wrong. The classical half of the pipeline is sound.
- **It is not a constant offset.** `shot_022`'s caption lands on `shot_025` (+3); `shot_048`'s
  caption describes what `shot_033` shows (−15). No index shift repairs it.
- **It is not a captioning failure.** The captions are accurate, specific English about things that
  genuinely happen in this video. The model watched and understood the whole clip in one pass —
  the thing this path exists to prove. Attribution to a shot is what fails.

**The measured baseline you must beat:** `work/footage_index.json`, 2 match / 2 partial / 13
mismatch of 17. That file is on disk and is gitignored; it is the artifact the numbers describe.

## This session: T011 — caption ↔ `shot_index` alignment

**Goal:** make a caption describe the shot it is stored on, and make the pipeline able to tell when
it doesn't. Measure first, change second — 17 hand-checked shots prove the problem is real and are
not enough to attribute a cause.

**Acceptance criteria** (restated in full — `tasks/T011-caption-shot-alignment.md` is authoritative
if they disagree):

- [ ] A **repeatable measurement** of caption/frame agreement exists and is recorded: N shots
      sampled from `in.mp4` by a fixed rule (not hand-picked), each scored match / partial /
      mismatch against its keyframe, with the sample list committed so a later run compares like
      with like. The T009 baseline for this measure is **2 match / 2 partial / 13 mismatch of 17**.
- [ ] Agreement after the fix is **≥ 12 of 17 clean matches** on that same sample. A smaller
      improvement is a legitimate result to record, but it does not close this task.
- [ ] The three unambiguous failures named in `docs/run-report.md` — `shot_059` (top-scored 0.85,
      captioned "three men in the back seat", frame shows an empty boot), `shot_105` (captioned
      "presenter exits", frame is a parked car with no presenter), and `shot_005` (captioned "walks
      around the front", frame is a static front-on car) — each either match their frames or are
      demonstrably absent from the fixed sample for a stated reason.
- [ ] **Still exactly one Gemini call per video**, verified from the counter, not intent.
- [ ] Token cost after the fix recorded against the **38,956** baseline. A rise is acceptable if
      stated; the ceiling is the 250K/min TPM cap, not the old ~30K estimate (D-025).
- [ ] `understand()` **detects** a bad mapping rather than trusting it: every returned `shot_index`
      in `[0, len(shots))`, appearing at most once, covering every shot, with a named exception on
      violation. Note whether the current run already satisfies this — if it does, index *validity*
      was never the failure and the check is a regression guard, not the fix.
- [ ] If `fps` is raised, the new default is justified with the measured agreement rate **and** the
      token cost at both values, and logged as a decision.
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run mypy elvideo` all clean.
- [ ] The result — including a failure to reach ≥12/17 — is written into `docs/run-report.md`
      alongside the T009 numbers, so the two read side by side.

## Constraints that bite on this task specifically

- **One Gemini call per video, never per shot** (hard constraint 1). The obvious fix — ask about
  each shot individually — is exactly the design this project exists to avoid and would blow the
  10 RPM free-tier cap on a 117-shot clip. **Any per-shot loop is out of bounds**, however well it
  aligns.
- **Free tier only** (hard constraint 2). Each experimental run costs ~39K tokens and ~4 minutes.
  Decide how many live runs you are spending before you start — D-024's prompt iteration took
  three, and that is a reasonable ceiling here too.
- **`gemini-3.5-flash` is pinned** (hard constraint 3). "Try a bigger model" is not on the table.
- **Gemini's own timestamps are never `t_start`/`t_end`** (hard constraint 4). They may be used as
  a *hint* for matching a judgment to a shot — the `_JudgmentWithHints` wire model already exists
  for exactly this — but the boundaries in the output stay PySceneDetect's.
- **The schema is a contract** (hard constraint 6). This is an accuracy fix, not a shape change. If
  a fix genuinely needs a new field, log it in `state/decisions-log.md` first.
- **`fps` and `media_resolution` are per-video knobs, and their defaults are pinned settings**
  (hard constraint 2, D-019). Changing a default is a decision, not a tweak.

## Blockers and open decisions affecting this

- **No blockers.** `blockers` in `progress.json` is empty and the API key works.
- **D-027 is `open`** — it is this task's subject. It records the measurement and two **untested**
  hypotheses:
  1. **Timestamp granularity.** Gemini's timestamps are second-granular while the median shot on
     `in.mp4` is **2.68s** and **36 of 117** shots are under 2s.
  2. **Frame starvation.** At `fps=0.5` there are ~214 sampled frames for 117 shots — 1.8 each, and
     the sub-2s shots get one frame or none. A shot the model never saw still gets a row in the
     response, and the `p2` rubric asks for a confident judgment on it.

  If (2) dominates, raising `--fps` to 1.0 costs roughly +14K visual tokens on this clip and is
  worth measuring first because it is one flag. If (1) dominates, the fix is a different shape —
  anchoring on something the model can see rather than on a number it has to infer. **D-027 closes
  when a cause is attributed, not when the numbers improve.**
- The D-016 owner follow-up (`.claude/CLAUDE.md` hard constraint 6 and `docs/IDEA.md` still
  describe a Path A counterparty that does not exist) is still open and still blocks nothing.

## Definition of done for the session

A repeatable agreement measurement exists with its sample committed, and its result is recorded in
`docs/run-report.md` next to the T009 numbers — **whether or not the fix worked**. If a change was
made, the call count is still 1 from the counter, the token cost is recorded against 38,956, and
`uv run pytest` / `uv run ruff check .` / `uv run mypy elvideo` are clean. If the cause was
attributed, D-027 moves to `resolved` with the evidence; if it was not, D-027 stays `open` and the
session log says which hypothesis was tested and what it showed.

A session that measures honestly and does not reach ≥12/17 is a good session. A session that
reports an improvement without a repeatable baseline is not.

End with `/checkpoint`.

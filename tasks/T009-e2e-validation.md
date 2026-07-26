# T009 — E2E validation on the A/B test video

**Status:** `done` — **8 pass, 2 fail, 1 not-verifiable, all recorded.** Report:
[`docs/run-report.md`](../docs/run-report.md). The video was `in.mp4`, 7:08, 117 shots — see
`state/decisions-log.md` D-003 for its full measured profile.

The task closes with its failures written down rather than engineered around, which is what its
own Notes section asks for. The serious one is **criterion 11**: the captions are attached to the
wrong shots. That is now [T011](T011-caption-shot-alignment.md), and it is the repo's top defect.

## Goal

Run the whole pipeline on the agreed A/B test video and prove every Definition-of-Done claim with
a number, not an impression.

This is the task that turns "it works" into evidence — for the architecture decision now, and for
the hackathon writeup later.

## Reads / depends on

- `docs/IDEA.md` § *Definition of done (s1)* — the checklist this task exists to satisfy
- `docs/IDEA.md` § *Gemini call settings*, § *Storage & speed*
- `state/decisions-log.md` **D-003** (the agreed test video) — resolved, with the clip's measured
  profile
- Tasks: T001–T008, all complete.

## Known before you start

From D-003 and D-012, so a failure is recognisable rather than merely surprising:

| | |
|---|---|
| Clip | `in.mp4` — 7:08 (428.11s), 1280×720, 25 fps, AAC stereo |
| Expected shots | **117** at `ContentDetector(threshold=27.0)` |
| Expected visual tokens | 214 frames × 66 ≈ **~14K**, roughly half the 30K target |

A shot count far off 117 means the detector settings drifted, not that the footage changed.

## Inputs / outputs

**In:** the one agreed ~10-min clip both paths run on.
**Out:** a `footage_index.json` that validates, plus a recorded run report: token count, call
count, per-stage timings, shot count, wall-clock total.

## Acceptance criteria

Straight from `docs/IDEA.md` § *Definition of done*. Verdicts measured 2026-07-26 on the live run;
full evidence in [`docs/run-report.md`](../docs/run-report.md).

- [x] `python -m elvideo index in.mp4` produces a `footage_index.json` that **validates against
      the shared schema**. — **PASS.** Three independent validators: `validate_index()`,
      `jsonschema` draft 2020-12, and `pydantic`.
- [x] **Exactly one Gemini call** for the video — verified from the logged call counter, not
      assumed. — **PASS.** Counter read back = 1.
- [x] Full shot list with `t_start` / `t_end` frame-accurate, from PySceneDetect. — **PASS.**
      117 shots, **0** off-grid boundaries at 1/25s, contiguous, 10,701 of 10,701 frames covered.
- [x] `words[]` present with word-level timing. — **PASS.** 1,436 words as `{t, d, w}`.
- [ ] Runs on a **free-tier** key, **≤ ~30K tokens**, **no 429** on a single video. — **FAIL on
      tokens: 38,956.** Free tier and 0×429 both pass. The estimate was wrong, not the run — it
      counted frames and omitted the audio track, which is billed per second regardless of `fps`
      or `media_resolution` (D-025). Passes against the corrected ~40K. Not tuned to chase 30K.
- [x] **Per-stage timing logged**, and total wall-clock **<5 min**. — **PASS.** 8 stages logged,
      **234.7s**. Caveat kept: the clip is 7:08, so a true 10:00 clip projects to 300–330s.
- [ ] Same command, same schema output as Path A → A/B-ready. — **NOT VERIFIABLE.** No Path A
      counterparty exists (D-016). The repo side is ready; there is nothing to diff against.

Plus, so the result is reviewable later:

- [x] The run report is committed (`work/` is gitignored — put it somewhere tracked, e.g.
      `docs/` or the session log). — **PASS.** [`docs/run-report.md`](../docs/run-report.md).
- [x] Actual token count recorded against the ~30K estimate. A large miss is a finding worth
      writing down, not a number to quietly round. — **PASS.** 38,956 recorded with the reason.
- [x] `editorial_score` values are **spread**, not clustered at one value — a model scoring
      everything `0.8` passes schema validation while being useless. — **PASS.** 37 distinct at
      2dp, 32/117 on the 0.05 grid, largest cluster 10 shots at 0.58.
- [ ] Spot-check ~5 shots by hand: does the caption describe what's actually on screen, and does
      `moment_reason` justify its score? Schema validity proves shape, not sense. — **FAIL.**
      **17 shots checked: 2 match, 2 partial, 13 wrong.** The captions describe things that really
      happen in the video, filed under the wrong `shot_index`. Keyframes and boundaries were ruled
      out first by re-extracting frames with `ffmpeg` independently of the pipeline. Not a constant
      offset, so not repairable by shifting. → **[T011](T011-caption-shot-alignment.md)**.
- [x] The exact `fps` and `media_resolution` used are recorded, since they're per-video knobs. —
      **PASS.** `fps=0.5`, `media_resolution=low`, also carried in `index_meta`.

## Constraints that bite here

- **Free tier.** If this run needs a paid key, the constraint is violated and that's a finding,
  not a workaround.
- **No 429** on a single video. One 429 that backoff silently absorbed still means the design is
  closer to the cap than intended — log it either way.
- The <5 min target is on a **laptop**, not a workstation. Record which machine.

## Notes

Run Path A on the same clip if the co-founder's side is ready — the diff between the two indexes
*is* the architecture decision, and it's cheapest to capture while both are fresh.

Failing a criterion is a legitimate outcome of this task. If the token count comes in at 60K, the
useful output is the measured number plus the reason, not a tuned run that hits 30K by shortening
the video. Record what actually happened.

**Outcome, 2026-07-26.** Both expected failures landed as expected (tokens ~39K, no Path A to A/B
against). The unexpected one is the spot-check, and it is the reason this task was worth doing: the
only criterion that required a human to look at pictures is the only criterion that found a defect.
Every automated gate in the repo is a shape check, and a caption on the wrong shot has the right
shape. Logged as **D-027**, filed as **[T011](T011-caption-shot-alignment.md)**, not fixed here —
T009's job was to measure.

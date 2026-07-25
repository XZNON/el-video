# T009 — E2E validation on the A/B test video

**Status:** `not_started` — **unblocked.** The video is picked: `in.mp4`, 7:08, 117 shots. See
`state/decisions-log.md` D-003 for its full measured profile.

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

Straight from `docs/IDEA.md` § *Definition of done*:

- [ ] `python -m elvideo index in.mp4` produces a `footage_index.json` that **validates against
      the shared schema**.
- [ ] **Exactly one Gemini call** for the video — verified from the logged call counter, not
      assumed.
- [ ] Full shot list with `t_start` / `t_end` frame-accurate, from PySceneDetect.
- [ ] `words[]` present with word-level timing.
- [ ] Runs on a **free-tier** key, **≤ ~30K tokens**, **no 429** on a single video.
- [ ] **Per-stage timing logged**, and total wall-clock **<5 min**.
- [ ] Same command, same schema output as Path A → A/B-ready.

Plus, so the result is reviewable later:

- [ ] The run report is committed (`work/` is gitignored — put it somewhere tracked, e.g.
      `docs/` or the session log).
- [ ] Actual token count recorded against the ~30K estimate. A large miss is a finding worth
      writing down, not a number to quietly round.
- [ ] `editorial_score` values are **spread**, not clustered at one value — a model scoring
      everything `0.8` passes schema validation while being useless.
- [ ] Spot-check ~5 shots by hand: does the caption describe what's actually on screen, and does
      `moment_reason` justify its score? Schema validity proves shape, not sense.
- [ ] The exact `fps` and `media_resolution` used are recorded, since they're per-video knobs.

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

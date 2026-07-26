# Run report — s1 end-to-end validation (T009)

**Date:** 2026-07-26 · **Task:** [T009](../tasks/T009-e2e-validation.md) · **Clip:** `in.mp4`
(D-003) · **Verdict: 8 pass, 2 fail, 1 not-verifiable.**

This is the evidence file for `docs/IDEA.md` § *Definition of done (s1)*. `work/` is gitignored, so
the artifact this describes (`work/footage_index.json`) is not in the repo — the numbers are.

**Headline:** the pipeline runs, is fast, costs one Gemini call, and emits a schema-valid index.
The **captions and scores are attached to the wrong shots** for most of the video. That failure is
invisible to schema validation and is the most important thing in this report — see
[The alignment failure](#the-alignment-failure).

---

## Command and machine

```
python -m elvideo index in.mp4
```

Defaults throughout — no flags. `--fps`, `--media-resolution` and `--threshold` were all left at
their pinned defaults, so the run reproduces from the command above alone.

| | |
|---|---|
| Machine | Laptop. AMD Ryzen 7 5800H, 8C/16T, 15.3 GB RAM, Windows 11 Home 10.0.26200 |
| Compute | **CPU-only** — torch 2.8.0, no CUDA. WhisperX on `cpu` / `int8` (D-015) |
| Python | 3.12.11 · ffmpeg 8.1.1 |
| Model | `gemini-3.5-flash`, free-tier key |
| Prompt | `p2` (D-024) |
| Knobs used | **`fps=0.5`**, **`media_resolution=low`**, `threshold=27.0`, `temperature=0.4`, `seed=7`, `thinking=LOW` |

`fps` and `media_resolution` are per-video knobs (hard constraint 2), so they are recorded here as
run inputs, not as settings. `index_meta` in the output carries the same values:

```json
{"path_variant": "gemini", "model": "gemini-3.5-flash", "media_resolution": "low",
 "sample_fps": 0.5, "scene_detector": "ContentDetector", "scene_threshold": 27.0}
```

## Timing

**Total wall clock: 234.7s** — 78% of the 300s budget.

| Stage | Seconds | Share |
|---|---:|---:|
| probe | 0.05 | 0.0% |
| shots (PySceneDetect) | 20.95 | 8.9% |
| transcript (WhisperX) | 107.76 | 45.9% |
| **understand (Gemini)** | **86.77** | **37.0%** |
| quality (OpenCV) | 19.04 | 8.1% |
| join | 0.01 | 0.0% |
| validate | 0.06 | 0.0% |
| write | 0.02 | 0.0% |

`understand` splits into **upload 18.7s + call 64.9s**. Transcription plus the single Gemini call
are 83% of the run, which is what `docs/IDEA.md` § *Storage & speed* predicts.

**Caveat on the <5 min claim.** `in.mp4` is **7:08, not 10:00**. Transcription and quality scoring
scale with duration; extrapolating those two stages linearly puts a true 10-minute clip at roughly
**300–330s — at or just over the budget**. 234.7s is a pass on the agreed test video, not proof of
headroom on the spec's stated 10-minute target.

## Cost

| | Measured | Target |
|---|---:|---:|
| Gemini calls | **1** | 1 |
| Prompt tokens | 27,693 | — |
| Output tokens | 11,263 | — |
| **Total tokens** | **38,956** | ~30K (spec) / **~40K (corrected, D-025)** |
| HTTP 429s | **0** | 0 |

The call count is read back from the counter inside `build_index`, which aborts on anything but 1
— the number is measured, not asserted by intent.

**The ~30K target is wrong, not the run.** D-025 diagnosed it: the spec's estimate counted sampled
frames (214 × 66 ≈ 14K) and omitted the audio track, which Gemini bills per second of duration
regardless of `fps` or `media_resolution`. Roughly 14K visual + 12K audio + 2K for the 117-line
boundary list and rubric. A 10-minute clip should land near **~54K**, still far under the 250K/min
TPM cap, so the spec's "iterate freely all day" conclusion survives — only its number was wrong.
Nothing was tuned to chase 30K.

No 429 was observed, and `gemini.py` retries with backoff (D-020), so absence of a 429 in the exit
code would not by itself be evidence — the retry counter also stayed at zero.

## Output

117 shots, 1,436 words, 428.04s covered of a 428.11s container.

**Schema validity — three independent checks, all pass:**

| Check | Result |
|---|---|
| `build_index`'s own `validate_index()` (includes `t_end > t_start`, D-022) | PASS |
| `jsonschema` draft 2020-12 against `elvideo/schema/footage_index.schema.json` | PASS |
| `pydantic` `FootageIndex.model_validate()` | PASS |

**Shot boundaries — frame-accurate, from PySceneDetect.** All 234 boundary values are exact
multiples of 1/25s: **0 of 117 shots are off-grid.** Shots are contiguous (`t_end[i] == t_start[i+1]`
for all i) and cover frames 0–10,701, matching the container's 10,701 frames exactly. Gemini's own
timestamps are not used anywhere in `t_start`/`t_end` — the join is an index lookup on `shot_index`
(D-010), which is precisely why the alignment failure below is possible.

**`words[]` — present with word-level timing.** 1,436 entries, each `{t, d, w}` (start, duration,
word). First `{"t": 0.928, "d": 0.22, "w": "This"}`, last `{"t": 427.017, "d": 0.46, "w":
"antiseptic."}`.

**`editorial_score` — spread, not clustered.**

| | |
|---|---|
| min / median / max | 0.10 / 0.61 / 0.85 |
| mean / stdev | 0.6124 / 0.1028 |
| Distinct values at 2dp | **37** of 117 |
| Landing on the 0.05 grid | **32** of 117 |
| Largest single cluster | 0.58, **10 shots** |
| Candidates (`>= 0.65`, D-023) | **43** of 117 — flag agrees with the threshold on all 117 |

This passes the anti-clustering criterion on the numbers, and it is a real improvement over `p1`
(11 distinct, 117/117 on the 0.05 grid, ceiling 0.75 — D-024). **It does not mean the scores are
correct**, only that they are differentiated: a score attached to the wrong shot is spread and
wrong at the same time.

`quality` (OpenCV, deterministic): min 0.0607, median 0.4803, max 0.8574 — nothing at the ceiling.

---

## The alignment failure

**17 shots were hand-checked against their extracted keyframes. 2 matched, 2 were partial, 13 were
wrong.**

The check was done by looking at `work/keyframes/shot_###.png` — the frame at the midpoint of
`[t_start, t_end)` — and asking whether the caption describes it.

**Ruled out first: the keyframes and boundaries are correct.** Frames re-extracted independently
with `ffmpeg -ss <midpoint> -frames:v 1` for shots 025, 059 and 105 are the same images the
pipeline wrote, so `quality.score_shot()` is sampling where it claims to and the shot times are
right. The defect is in **which shot each Gemini judgment is attached to**.

| Shot | t_start | Caption (Gemini) | Keyframe actually shows | |
|---|---:|---|---|---|
| `shot_000` | 0.0 | Man in striped polo gestures toward a silver Tiguan on a wooded road | Exactly that | ✅ |
| `shot_005` | 21.2 | Presenter walks around the front and opens the driver's door | Static front-on shot of the parked car, **no presenter** | ❌ |
| `shot_022` | 75.2 | Presenter holds up a large water bottle in the driver's seat | Close-up of a hand on a dark storage tray under the dash | ❌ |
| `shot_025` | 79.4 | Close-up of the bottle placed in the **rear door bin** | Presenter in the **driver's seat** holding the bottle — i.e. `shot_022`'s caption | ❌ |
| `shot_033` | 111.5 | Presenter sits back in the side seat and gestures | Close-up of a hand on the folded rear seat / boot floor | ❌ |
| `shot_040` | 133.4 | Presenter taps the armrest, then folds the centre seat | Presenter in the rear seat, gesturing — right segment, action not visible | ◐ |
| `shot_048` | 154.2 | Hand points to the 12V socket, then lifts the boot floor | Presenter raising the tailgate — boot context, wrong action | ❌ |
| `shot_057` | 174.8 | A golf bag and luggage packed into the boot | Presenter at the open boot, load area **empty** | ❌ |
| `shot_058` | 175.6 | A child car seat being fitted into the rear seats | Interior looking forward over folded seats, **no seat, no child seat** | ❌ |
| `shot_059` | 177.2 | **Three men side-by-side in the back seat, thumbs up** — scored **0.85, the clip's top score** | Presenter standing at the open boot, rear seats up, nobody in them | ❌ |
| `shot_060` | 183.4 | Close-up tracking shot of the front grille, driving | Static interior view of the boot with seats folded flat | ❌ |
| `shot_061` | 186.1 | Tracking shot of the Tiguan driving along a wooded road | Presenter at the open boot | ❌ |
| `shot_075` | 235.6 | Tiguan drives towards the camera on a highway | Tiguan driving towards camera — a country road, not a highway | ✅ |
| `shot_090` | 290.8 | Presenter demonstrates the adjustable boot floor height | Driving shot of the car on a road | ❌ |
| `shot_098` | 322.1 | Presenter leans on the dashboard, talks about safety | Close-up of the front wheel and tyre | ❌ |
| `shot_105` | 349.0 | Presenter exits the car and begins his final verdict | Static side profile of the parked car, **no presenter** | ❌ |
| `shot_116` | 412.4 | A **black** screen with the Carwow logo and social handles | The carwow outro card — **blue**, with a presenter inset, a Subscribe button and three video thumbnails | ◐ |

**What is and is not broken:**

- **The captions are good English descriptions of things that genuinely happen in this video.**
  There is a three-men-in-the-back-seat shot, a child-seat shot, a 12V-socket shot. The model
  watched the video and understood it. It then filed its observations under the wrong indices.
- **It is not a constant offset, so it cannot be repaired by shifting.** `shot_022`'s caption lands
  on `shot_025` (+3); `shot_048`'s caption describes what `shot_033` shows (−15); others have no
  visible partner nearby. The misassignment is per-shot, not global.
- **`transcript` is not affected.** Word timings come from WhisperX and are joined by time window,
  not by index. Spot-checking the same shots, the transcript matches the picture (`shot_059`'s
  "can't be bothered to walk round to the back doors" over a shot of the presenter at the boot).
  The classical half of the pipeline is sound; the LLM half is misaligned against it.
- **`moment_reason` justifies its score internally but not against the footage.** "Hero shot
  demonstrating real-world rear seat width with three adults" is a good reason for 0.85 — for a
  shot that is not `shot_059`. Judged as text, the reasons pass; judged against the frame, they
  inherit the caption's error.

**Most likely cause, stated as a hypothesis, not a diagnosis.** `understand()` sends the shot list
as **numbered text** (D-010, option 2) and asks the model to return a `shot_index` per judgment.
Two things make that mapping fragile on this clip:

1. **Gemini's own timestamps are second-granular** (hard constraint 4) while the **median shot is
   2.68s and 36 of 117 shots are under 2s**. The model cannot resolve a boundary list finer than
   its own clock.
2. **At `fps=0.5` there are ~214 sampled frames for 117 shots** — 1.8 per shot on average, and the
   36 sub-2s shots get one frame or none. Shots the model never saw a frame of still need a row in
   the response, and the rubric asks for one.

Both point the same way: raising `--fps` and/or making the index assignment verifiable rather than
trusted. **No fix was attempted in T009** — the task's job is to measure. Filed as
[T011](../tasks/T011-caption-shot-alignment.md).

**Why nothing caught this.** Every automated gate the pipeline has is a shape check. The schema
validates types and ranges; `validate_index()` adds `t_end > t_start`; the slow test asserts score
*granularity*. A caption on the wrong shot violates none of them. This is the exact failure mode
T009's spot-check criterion exists to find, one level deeper than the "everything scores 0.8" case
it was written for — and it was found only by a human looking at frames.

---

## Criteria

| # | Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | `python -m elvideo index in.mp4` produces a `footage_index.json` that validates | **PASS** | Three validators, all clean |
| 2 | Exactly one Gemini call, from the counter | **PASS** | Counter read back = 1; `build_index` aborts otherwise |
| 3 | Full shot list, `t_start`/`t_end` frame-accurate from PySceneDetect | **PASS** | 117 shots, 0 off-grid boundaries, contiguous, 10,701/10,701 frames |
| 4 | `words[]` with word-level timing | **PASS** | 1,436 words, `{t, d, w}` |
| 5 | Free-tier key, **≤ ~30K tokens**, no 429 | **FAIL (tokens)** · PASS (free tier, 0×429) | **38,956 tokens.** Target was wrong, not the run — D-025. Passes the corrected ~40K |
| 6 | Per-stage timing logged, total <5 min | **PASS** | 8 stages logged, 234.7s. Caveat: 7:08 clip, a 10:00 clip projects to 300–330s |
| 7 | Same command, same schema output as Path A → A/B-ready | **NOT VERIFIABLE** | No Path A counterparty exists (D-016). Output is schema-conformant and the command matches the spec, so the *repo side* is ready; there is nothing to diff against |
| 8 | Run report committed outside `work/` | **PASS** | This file |
| 9 | Token count recorded against the estimate | **PASS** | 38,956 vs ~30K, with the audio-omission reason — recorded, not rounded |
| 10 | `editorial_score` spread, not clustered | **PASS** | 37 distinct at 2dp, 32/117 on the 0.05 grid, largest cluster 10 |
| 11 | Spot-check ~5 shots: caption matches the frame, `moment_reason` justifies the score | **FAIL** | 17 checked: 2 match, 2 partial, **13 wrong**. See above |
| 12 | Exact `fps` and `media_resolution` recorded | **PASS** | `fps=0.5`, `media_resolution=low`; also in `index_meta` |

**Gates at time of writing:** `uv run pytest -m "not slow"` 191 passed · `uv run ruff check .`
clean · `uv run mypy elvideo` strict clean (12 files).

## What this means for the A/B

The Gemini-native path delivers on its structural claims — **one call, 39K tokens, 234.7s, a
schema-valid shot-level index of a 7-minute video on a free-tier key with no 429**. Long-context
understanding is real: the captions prove the model watched and understood the whole video in a
single pass.

What is not yet delivered is **trustworthy shot-level attribution**. An agent reasoning over this
index would confidently pick `shot_059` for "three adults in the back seat" and cut to a shot of
an empty boot. Until [T011](../tasks/T011-caption-shot-alignment.md) lands, treat
`caption` / `editorial_score` / `moment_reason` as *video-level* evidence that happens to be
stored per shot — accurate about the footage, unreliable about which second of it.

---

# T011 — caption ↔ `shot_index` alignment (2026-07-26, same day)

**Task:** [T011](../tasks/T011-caption-shot-alignment.md) · **Verdict: improved, criterion not
met, cause partly attributed.** Read this section next to the T009 numbers above — it is the same
clip, the same machine, and the same measurement, taken again.

**Headline:** anchoring the prompt on timestamps instead of letting the model count shots moved
clean caption/frame agreement from **2/17** to **13/17** on one run — and then **6/17** on a
replicate of the identical configuration. The defect is real, the direction of the fix is
evidenced, and **the result is not stable enough to call the task done**. `p3` ships as the new
default because both of its runs beat the baseline; the ≥12/17 criterion does not pass.

## How agreement is measured now

T009's spot-check was a human reading 17 keyframes. That number could not be reproduced, so it
could not be improved against. It is now a committed measurement:

- **Sample:** `elvideo/eval/alignment_sample.json` — the same 17 shots T009 checked, frozen
  verbatim so runs compare like with like. They span 0.0s–412.4s and the score range. Honest
  caveat: they were **hand-picked in T009**, not rule-generated, which T011's criterion 1 mildly
  disfavours; comparability with the published baseline was judged worth more.
- **Grader:** one Gemini call, `gemini-3.5-flash`, rubric `g1`, `temperature=0.0`, all 17
  `(keyframe, caption)` pairs interleaved in a **single** request — the measurement obeys the same
  one-call rule as the thing it measures. Code: `elvideo/eval/alignment.py`.
- **Calibration:** on the T009 index the grader returned **2 match / 1 partial / 14 mismatch** and
  agreed with the human column on **16 of 17** — it reproduced the hand check without being shown
  it. The single disagreement is `shot_116` (human *partial*, grader *mismatch*).
- **Cost:** ~3K tokens per grading call. It never touches `gemini.generate_call_count()`, which
  counts index calls only.

Reproduce with `python -m elvideo.eval.alignment work/footage_index.json`.

## Results

Four indexes of the same clip, same boundaries, same `fps=0.5`, `media_resolution=low`, one Gemini
call each. Only the prompt changed.

| Index | Prompt | **Clean match /17** | Partial | Mismatch | Tokens | Score range | Distinct @2dp |
|---|---|---:|---:|---:|---:|---:|---:|
| T009 baseline | `p2` | **2** | 1 | 14 | 38,956 | 0.75 | 37 |
| Run 1 | `p3` | **13** | 1 | 3 | 42,764 | 0.27 | 27 |
| Run 2 | `p4` | **4** | 2 | 11 | 41,402 | 0.60 | 39 |
| Run 3 | `p3` (replicate) | **6** | 0 | 11 | 42,131 | 0.48 | 30 |

**Call count is 1 on every row, read from the counter.** Token cost rises ~3K over the 38,956
baseline (+8%), from the longer prompt and the returned hints — far under the 250K/min TPM cap
(D-025). `fps` was **not** raised, so no `fps` decision is owed.

## What `p3` changes, and why it worked at all

`p2` handed the model a numbered boundary list and asked for a `shot_index` back. `p3` adds three
things and keeps the rubric identical:

1. **"Find each shot by its timestamp, not by counting."** With the reason: this detector cuts far
   more finely than a person would, so several listed shots can look like one continuous action —
   a model counting cuts as it watches drifts out of step and files the right moments under the
   wrong indices. That is precisely the D-027 signature.
2. **Hints are now requested on the shot-list path too** (`t_start_hint` / `t_end_hint`), where
   `p2` deliberately skipped them as redundant output tokens.
3. **A self-check:** if the moment you describe for index *k* is not inside the *k*-th interval,
   you have described the wrong moment — the list is authoritative, your reading of the clock bends.

## The negative result: the hints do not detect the failure

`hint_drift()` reports **0 of 117** judgments outside their own shot — on *every* run, including
the 6/17 and 4/17 ones where a third to two-thirds of the sampled captions demonstrably describe
other footage. **The model echoes the timestamps we gave it back verbatim, whatever it actually
looked at.** Its self-report is not independent evidence and cannot be used as a detector.

This is worth stating plainly because it was the most promising idea going in. `hint_drift()` is
kept as a regression guard — it would catch a model that starts free-segmenting or drifting
openly — but it is **not** the answer to T011's "detect a bad mapping rather than trust it". The
only thing that detected the failure, before and after, is looking at the frames.

## `p4`, and the trade-off it exposed

`p3` aligned well on run 1 but flattened the scoring: range **0.27**, which fails the slow test's
`max - min > 0.3` guard from D-024. `p4` = `p3` plus one paragraph re-asserting the ranking rubric.
It restored the scores (range 0.60, 39 distinct — better than `p2`) and **collapsed the alignment
to 4/17**. The two instructions compete: attention spent on localising is attention not spent on
ranking, and vice versa. `p3`'s replicate then scored range 0.48 unaided, so `p3`'s flatness was
itself partly run variance rather than a property of the prompt.

## Run-to-run variance is the finding that limits all the others

Identical prompt, identical settings, `seed=7`, `temperature=0.4`: **13/17 then 6/17.** D-024
already recorded that `seed` is best-effort for scores; it is now measured for *alignment* too, and
the swing is far larger. Consequences, stated so the next session does not repeat the mistake:

- **A single run cannot rank two prompts.** `p3` vs `p4` on one run each (13 vs 4) is not evidence
  that `p3` is three times better; the `p3` replicate lands closer to `p4` than to itself.
- **The honest summary of `p3` is "2/17 → 6–13/17, n=2".** Both runs beat the baseline, which is
  why it ships; the mean does not reach 12.
- Any future comparison needs **2–3 runs per configuration**, ~42K tokens each.

## The three named shots (criterion 3)

| Shot | Frame shows | `p2` | `p3` run 1 | `p3` replicate |
|---|---|---|---|---|
| `shot_005` | Static front-on parked car, no presenter | mismatch | **match** | **match** |
| `shot_059` | Presenter at the open boot, rear seats up, nobody in them | mismatch | mismatch | mismatch |
| `shot_105` | Side profile of the parked car, no presenter | mismatch | **match** | mismatch |

`shot_059` — the one that made D-027 alarming, the clip's top-scored shot captioned "three men in
the back seat" — **never matches**. It no longer invents people: `p3` calls it "the presenter
climbs into the boot to demonstrate the flat loading area" against a frame of the presenter
standing outside the boot. Wrong action, right place, and no longer the top-scored shot (0.69).
That is a smaller error than `p2`'s, and it is still a mismatch. Criterion 3 is **not met**.

## Criteria

| # | Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | Repeatable measurement, sample committed | **PASS** | `elvideo/eval/alignment.py` + `alignment_sample.json`; grader agrees with the T009 human column 16/17 |
| 2 | ≥ 12 of 17 clean matches | **FAIL** | 13/17 once, **6/17** on replicate. Both beat 2/17; neither is a stable ≥12 |
| 3 | `shot_059` / `shot_105` / `shot_005` match or are absent for a stated reason | **FAIL** | `shot_005` matches on both `p3` runs; `shot_105` on one; **`shot_059` on neither** |
| 4 | Still exactly one Gemini call, from the counter | **PASS** | 1 on all three runs; grading calls are a separate consumer and never increment it |
| 5 | Token cost recorded against 38,956 | **PASS** | 42,764 / 41,402 / 42,131 — +8%, stated, far under the 250K TPM cap |
| 6 | `understand()` detects a bad mapping rather than trusting it | **PARTIAL** | Range/duplicate/coverage checks already passed on the failing `p2` run, so index *validity* was never the failure — they are a regression guard, as the criterion anticipated. The new `hint_drift()` detector returns 0 drift on runs that are 65% wrong: **the model's self-report is not independent evidence** |
| 7 | If `fps` is raised, justify it | **N/A** | `fps` stayed at 0.5. Frame starvation (D-027 hypothesis 2) is therefore **still untested** |
| 8 | `pytest`, `ruff`, `mypy` clean | **PASS** | 211 fast tests, ruff clean, mypy strict clean (14 files) |
| 9 | Result written up beside the T009 numbers | **PASS** | This section |

## What this means for the A/B

The T009 verdict stands, softened. `caption` / `editorial_score` / `moment_reason` are still more
reliable about *the video* than about *which second of it*, but the gap narrowed measurably and the
cause is no longer a mystery: **the model was not locating shots by timestamp, it was counting
them.** Telling it not to helps, by a lot, inconsistently.

An agent reasoning over a `p3` index is meaningfully less likely to cut to the wrong footage than
over a `p2` one, and still cannot be trusted to pick the hero shot unattended. The remaining lever
that has never been pulled is **`fps`** — hypothesis 2 in D-027, roughly +14K tokens to test, and
the natural first move for whoever picks this up.

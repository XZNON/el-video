# T004 — `gemini.py`: native understanding pass

**Status:** `done` (2026-07-26) — every acceptance criterion met, **verified against the live API**.
D-021 (the dead key) is cleared. The prompt was iterated `p1` → `p2` on the strength of the first
real run, which clustered: see **D-024** for the before/after, and **D-025** for the token budget,
which measures ~38K rather than the ~30K the spec assumes.

**Live run, `in.mp4` (7:08, 117 shots), prompt `p2`:** one `generate_content` call · 117 shots
judged · 96.8s wall-clock (upload 24.6s, call 70.3s) · 38,390 tokens (prompt 27,693 / output
10,697) · `editorial_score` min 0.50, median 0.64, max 0.88, 26 distinct values at 2dp · upload
deleted.

## Goal

Watch the whole video in **exactly one** Gemini call and get back per-shot judgment: caption,
editorial score, moment reason, tags.

**This is the Path B core** — the module the entire A/B is about. Everything else in this repo is
shared with Path A; this is the part that's different.

## Reads / depends on

- `docs/IDEA.md` § *Gemini call settings (locked)* — read this in full, the numbers are not
  suggestions
- `docs/IDEA.md` § *Architecture (Path B)*, § *Why this slice, this way*
- `docs/architecture.md` § *The one rule*, § *Division of labour*
- Tasks: T006 for `ShotUnderstanding` (seeded in scaffold). T007 consumes this output.

## Inputs / outputs

**In:** `path: str`, `fps: float = 0.5`, `media_resolution: MediaResolution = "low"`.
**Out:** `list[ShotUnderstanding]` — judgment only, chronological.

The video is uploaded to the **Gemini File API**, which holds it 48h free. We don't store it.

## Acceptance criteria

Legend: `[x]` verified. The four criteria that were `[~]` pending a working key are now settled
against the live API — each carries the measured number.

- [x] **Exactly one** `generate_content` call per invocation, independent of shot count. Assert
      it — instrument a call counter that T009 can read out of the log, don't just intend it.
      → `generate_call_count()`; `test_exactly_one_call_regardless_of_shot_count` drives 117 shots
      through a mocked client and asserts one request. Logged as
      `gemini generate_content request #1 model=… fps=… media_resolution=… prompt=p1`. A 429 retry
      increments the counter on purpose — hidden retries would defeat the instrument.
- [x] Model string is `gemini-3.5-flash`, read from the `MODEL` constant. Not parameterized, not
      swapped. → asserted against the captured request, not the constant alone.
- [x] `media_resolution` is passed as `low` by default and actually reaches the request (verify
      against the request payload, not just the function signature). → the mock captures `config`;
      `config.media_resolution == MediaResolution.MEDIA_RESOLUTION_LOW`, and `"medium"` maps
      through too.
- [x] `fps` is passed through as the video sampling rate and defaults to `0.5`. Overridable
      **per call**, never by editing the default. → reaches
      `Part.video_metadata.fps` on the video part; override test also asserts the module default is
      still 0.5.
- [x] Structured output is enforced with a response schema — strict JSON, no prose, no markdown
      fences to strip. → `response_mime_type="application/json"` +
      `response_schema=list[_Judgment]`. No fence-stripping anywhere in the parser: a fenced body
      is a `RuntimeError`, not something to salvage.
- [x] Exponential backoff on HTTP 429, via `tenacity`. Bounded retries, and the final failure
      surfaces as a clear error rather than an empty list. → `_with_backoff()`, 5 attempts, 4s
      doubling to 60s. **Wraps the File API upload as well as the generate call** — the real 429
      arrived at upload time (D-020). Non-429 errors are not retried.
- [x] `RuntimeError` with an actionable message when `GEMINI_API_KEY` is unset (loaded via
      `python-dotenv` from `.env`). → also treats a whitespace-only key as unset; message names
      `.env.example` and the AI Studio URL.
- [x] `RuntimeError` when the response can't be parsed as the expected schema after retries.
      → covered for: non-JSON text, JSON object instead of array, empty array, empty body (with the
      finish reason quoted), score out of `0..1`, and a non-object entry.
- [x] The returned `shot_index` values are validated against the real shot count and fail loudly
      out of range (added by D-010). → out-of-range **and** duplicates both raise; a short list
      warns instead, since a missing caption is visible and recoverable while a misnumbered one is
      neither.
- [x] Token usage from the response is logged, so T009 can check the ≈30K target against a real
      number. → `gemini tokens: prompt=… output=… thoughts=… total=…`. **Measured: 38,390 total
      (prompt 27,693 / output 10,697) across three runs within 2% of each other.** That is above
      the spec's ≈30K, because D-003's estimate counted sampled frames and omitted the audio track
      — see **D-025**. Not a regression and not blocking: it is ~15% of the 250K TPM cap.
- [x] `editorial_score` values come back in `0.0`–`1.0` and are not all identical — a model that
      scores everything `0.8` is a prompt bug, not a passing run. → **`p1` failed this in
      substance while passing in form**: 11 distinct values, all on the 0.05 grid, ceiling 0.75,
      97/117 inside 0.50–0.65. `p2` fixed it — 26–37 distinct values, only 32/117 on the grid, hero
      band reached (0.85–0.88). Guarded going forward: every run logs
      `min/median/max/stdev/distinct@2dp` and warns below stdev 0.05, and the slow test asserts
      **granularity** (≥15 distinct, <90% on the 0.05 grid), which `p1` fails on every run. See
      **D-024**.
- [x] `moment_reason` is a short justification, not a restatement of the caption. → verified by
      reading all 117. Typical output: *"Hero shot demonstrating real-world rear seat width with
      three adults"*, *"Third exterior pan of the same car"*, *"Basic front-on shot, slightly
      redundant"* — evidence, not a second caption. **4 of 117 still open with a category label**
      ("Standard b-roll showing the exterior profile"); logged in D-024 as accepted rather than
      chased with another prompt round.
- [x] Uploaded File API handle is cleaned up or allowed to expire deliberately — don't leak a
      new upload on every debug run without noticing. → deleted in a `finally`, so it happens on
      the failure path too; a failed delete warns rather than masking the real result.
- [x] Token budget for a 10-min clip at `low`/`0.5fps`. **Measured ~38K for 7:08, so ~54K
      extrapolated to 10 min** — above the spec's ≈30K, restated with the reasoning in **D-025**.
      The conclusion the number was serving ("iterate freely all day") survives: still ~20% of the
      250K TPM cap.

**One thing deliberately not verified live** (not an acceptance criterion — the task file never
asked for it; recorded so nobody later assumes it was covered): the `shots=None`
free-segmentation fallback has only ever run against mocks. It costs a second call on the same
clip, and every consumer in this repo uses the boundary path. If the Path A seam is ever exercised
for real, run that path first.

## Constraints that bite here

- **One Gemini call per video, never per shot.** A 10-min video is 100–300 shots; per-shot calls
  blow the 10 RPM cap instantly. A design that drifts toward per-shot calls is wrong **even if it
  works** — it throws away the cross-shot context that is the whole differentiator.
- **Free tier.** ≈30K tokens per 10-min video at `low` / `0.5fps`. TPM cap 250K/min.
- **Model pinned:** `gemini-3.5-flash`.
- **Gemini's timestamps are second-granular and never become `t_start` / `t_end`.** They may be
  returned as `t_start_hint` / `t_end_hint` for alignment only.

## Settled before starting: D-010 — the model is told our shot boundaries

**Resolved 2026-07-26, option 2.** `state/decisions-log.md` **D-010**. Not an open question any
more; implement it this way.

The PySceneDetect boundaries go into the **prompt text** as a numbered list, and the model returns
`shot_index` against it. Alignment in T007 becomes an index lookup instead of a fuzzy overlap
match against timestamps the constraints already declare untrustworthy.

- Boundaries arrive as an **optional keyword argument defaulting to `None`**, mirroring
  `detect_shots(path, threshold=)` (D-012). `understand(path, fps, media_resolution)` stays
  literally callable as `docs/IDEA.md` § *Module layout* writes it.
- Cost: ~117 lines of `idx t_start-t_end`, under 2K tokens against this clip's ~14K budget
  (D-003).
- With `None`, the model segments freely and returns hints — keep that path working, it's the
  fallback and the thing that makes the seam real.

Add to the acceptance criteria above: **the returned `shot_index` values must be validated
against the real shot count and fail loudly out of range** — a silent drop here produces an index
with captions on the wrong shots and no error anywhere.

## Notes

Prompt design is the real work here, not the API plumbing. The model needs to be told it's
judging moments for an editor: what makes a shot worth cutting to, why `editorial_score` should
spread across the range rather than cluster, and that `moment_reason` is evidence for the score.

Keep the prompt in a file or module-level constant, not inline in the call — it will be iterated
on, and the A/B writeup needs to quote the version that produced the numbers.

## What landed (2026-07-26)

`elvideo/index/gemini.py`, full implementation. `tests/test_gemini.py` — 47 fast tests + 1 slow
(real API, skips without a key). Settings pinned as module constants in the D-012 / D-015 / D-017
house style and guarded by `test_settings_are_recorded`: `TEMPERATURE=0.4`, `SEED=7`,
`THINKING_LEVEL=LOW`, `RETRY_MAX_ATTEMPTS=5`, `PROMPT_VERSION="p1"` — see **D-019**.

Prompt is split in two module constants: `SYSTEM_INSTRUCTION` (the editor's rubric — five scoring
bands, the anti-clustering instruction, `moment_reason` as evidence) and a user half that is either
the numbered boundary list (D-010) or the free-segmentation instruction. `PROMPT_VERSION` is the
handle the A/B writeup quotes.

**Live verification (2026-07-26, after the owner supplied a free-tier key):**
`uv run pytest tests/test_gemini.py -m slow --log-cli-level=INFO` — **1 passed**. Four live runs
total across the session: one on `p1`, one dumping `p1`'s full output for inspection, one on `p2`,
one final green gate. `PROMPT_VERSION` is now **`p2`**; D-024 holds the p1/p2 comparison table, and
the `p1` text is recoverable from git history if the writeup needs to quote what produced the
clustered numbers.

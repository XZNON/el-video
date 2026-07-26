# T004 — `gemini.py`: native understanding pass

**Status:** `blocked` — code complete, gates green, **no live API run possible**: the
`GEMINI_API_KEY` in `.env` returns `429 RESOURCE_EXHAUSTED — "Your prepayment credits are
depleted"` on every request, including a 5-token text-only call. Account-level, not this code.
See D-021. Four criteria below need one real call and are marked `[~]` rather than ticked.

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

Legend: `[x]` verified · `[~]` implemented, unverifiable without a working key (D-021).

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
      number. → `gemini tokens: prompt=… output=… thoughts=… total=…`, asserted in
      `test_token_usage_is_logged`. **The number itself is still unmeasured** — see D-021.
- [~] `editorial_score` values come back in `0.0`–`1.0` and are not all identical — a model that
      scores everything `0.8` is a prompt bug, not a passing run. → the range is enforced by the
      schema; the *spread* is what needs a live run. Instrumented rather than assumed: every run
      logs `min/median/max/stdev/distinct@2dp` and **warns** when stdev < 0.05, and the slow
      integration test fails if range ≤ 0.3 or fewer than 8 distinct values. Prompt gives a
      five-band rubric and says a run of identical scores is a failure of the task.
- [~] `moment_reason` is a short justification, not a restatement of the caption. → prompt asks
      for the *evidence* for the score in ≤15 words and forbids re-describing the shot; whether the
      model complies is a live-run question.
- [x] Uploaded File API handle is cleaned up or allowed to expire deliberately — don't leak a
      new upload on every debug run without noticing. → deleted in a `finally`, so it happens on
      the failure path too; a failed delete warns rather than masking the real result.
- [~] Token budget ≈30K for a 10-min clip at `low`/`0.5fps`. Unmeasured (D-021).
- [~] The `shots=None` free-segmentation fallback works against the real model. Unit-tested
      (schema swaps to include hints, prompt swaps to the segmentation instruction), not run live.

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

**To finish this task:** put a working key in `.env` and run
`uv run pytest tests/test_gemini.py -m slow --log-cli-level=INFO`. That one command settles every
`[~]` above and produces the token number D-021 is missing.

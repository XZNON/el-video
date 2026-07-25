# T004 — `gemini.py`: native understanding pass

**Status:** `not_started`

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

- [ ] **Exactly one** `generate_content` call per invocation, independent of shot count. Assert
      it — instrument a call counter that T009 can read out of the log, don't just intend it.
- [ ] Model string is `gemini-3.5-flash`, read from the `MODEL` constant. Not parameterized, not
      swapped.
- [ ] `media_resolution` is passed as `low` by default and actually reaches the request (verify
      against the request payload, not just the function signature).
- [ ] `fps` is passed through as the video sampling rate and defaults to `0.5`. Overridable
      **per call**, never by editing the default.
- [ ] Structured output is enforced with a response schema — strict JSON, no prose, no markdown
      fences to strip.
- [ ] Exponential backoff on HTTP 429, via `tenacity`. Bounded retries, and the final failure
      surfaces as a clear error rather than an empty list.
- [ ] `RuntimeError` with an actionable message when `GEMINI_API_KEY` is unset (loaded via
      `python-dotenv` from `.env`).
- [ ] `RuntimeError` when the response can't be parsed as the expected schema after retries.
- [ ] Token usage from the response is logged, so T009 can check the ≈30K target against a real
      number.
- [ ] `editorial_score` values come back in `0.0`–`1.0` and are not all identical — a model that
      scores everything `0.8` is a prompt bug, not a passing run.
- [ ] `moment_reason` is a short justification, not a restatement of the caption.
- [ ] Uploaded File API handle is cleaned up or allowed to expire deliberately — don't leak a
      new upload on every debug run without noticing.

## Constraints that bite here

- **One Gemini call per video, never per shot.** A 10-min video is 100–300 shots; per-shot calls
  blow the 10 RPM cap instantly. A design that drifts toward per-shot calls is wrong **even if it
  works** — it throws away the cross-shot context that is the whole differentiator.
- **Free tier.** ≈30K tokens per 10-min video at `low` / `0.5fps`. TPM cap 250K/min.
- **Model pinned:** `gemini-3.5-flash`.
- **Gemini's timestamps are second-granular and never become `t_start` / `t_end`.** They may be
  returned as `t_start_hint` / `t_end_hint` for alignment only.

## Open question to resolve while doing this

`understand()`'s signature (fixed by `docs/IDEA.md` § *Module layout*) does **not** take the
PySceneDetect shot list. So the model segments the video its own way, and T007 has to align two
lists that may differ in length.

Two options, and this task should settle it and log the answer in `state/decisions-log.md`:

1. **Keep the signature.** Model segments freely; `align_understanding()` matches on temporal
   overlap using the hints. Preserves the seam with Path A exactly.
2. **Pass the boundaries into the prompt** (as text, not as a signature change) so the model
   describes *our* shots by index. Alignment becomes trivial and captions get sharper, but it
   couples this module to T002's output.

Option 2 is likely better for output quality and costs almost nothing in tokens. It does not
change the function signature, so the seam survives — but it does mean `understand()` needs the
shot list from somewhere. Decide deliberately; don't let it happen by accident.

## Notes

Prompt design is the real work here, not the API plumbing. The model needs to be told it's
judging moments for an editor: what makes a shot worth cutting to, why `editorial_score` should
spread across the range rather than cluster, and that `moment_reason` is evidence for the score.

Keep the prompt in a file or module-level constant, not inline in the call — it will be iterated
on, and the A/B writeup needs to quote the version that produced the numbers.

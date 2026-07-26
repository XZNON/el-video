# Session 004 — T004: Gemini native understanding pass

## Read these first, in this order

1. `state/progress.json` — what's live, what's blocked
2. Last ~3 entries of `state/session-log.md` — what the previous sessions left behind
3. `.claude/CLAUDE.md` — hard constraints and session protocol
4. `tasks/T004-gemini-understanding.md` — **in full**
5. `docs/IDEA.md` § *Gemini call settings (locked)* — **in full; the numbers are not suggestions**
   — plus § *Architecture (Path B)* and § *Why this slice, this way*
6. `docs/architecture.md` § *The one rule*, § *Division of labour*
7. `state/decisions-log.md` **D-010** — settled, implement it as written

Then run `/start-task T004`.

## Where things stand

**All four classical stages are done and measured on the real clip `in.mp4`** (428.11s, 25 fps,
1280×720, has audio):

- **T001 `probe.py`** — ffprobe wrapper.
- **T002 `scenes.py`** — 117 shots in ~25s at `ContentDetector(threshold=27.0)`, gapless,
  frame-accurate. Settings pinned as module constants (D-012).
- **T003 `transcribe.py`** — 1436 words in 102.7s warm on CPU. Settings pinned (D-015).
- **T005 `quality.py`** — 117 shots in 18.8s, mean 0.465, spread 0.061–0.857, nothing at the
  ceiling. Formula and constants pinned (D-017); keyframe naming settled (D-018).

Gates green: `pytest -m "not slow"` 54 passed, `pytest -m "slow"` 2 passed in 144.9s, ruff clean,
mypy strict clean. Deps installed. `progress.json.blockers` is empty.

**T004 is the last unwritten pipeline stage before the orchestrator, and it is the Path B core** —
everything else in this repo is shared with Path A; this is the part that is different. The
contract is locked (D-016, solo repo): don't reshape the schema, and don't "simplify" away
`path_variant` or the nullable `editorial_score` / `moment_reason`.

**Checked at the end of the last session:** `.env` contains a non-empty `GEMINI_API_KEY`. This
task makes real API calls — the first one this project has made.

## This session: T004 — `gemini.py`

**Goal:** watch the whole video in **exactly one** Gemini call and get back per-shot judgment —
caption, `editorial_score`, `moment_reason`, tags — as `list[ShotUnderstanding]`.

**Signature** (`docs/IDEA.md` § *Module layout*):

```python
understand(path: str, fps: float = 0.5, media_resolution: MediaResolution = "low") -> list[ShotUnderstanding]
```

Plus the D-010 boundaries kwarg — see below. The video goes to the **Gemini File API**, which
holds it 48h free; we don't store it.

**Acceptance criteria** (restated in full — `tasks/T004-gemini-understanding.md` is authoritative
if they disagree):

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
- [ ] Uploaded File API handle is cleaned up or allowed to expire deliberately — don't leak a new
      upload on every debug run without noticing.
- [ ] **Added by D-010:** returned `shot_index` values are validated against the real shot count
      and **fail loudly out of range** — a silent drop produces an index with captions on the
      wrong shots and no error anywhere.

## Settled before you start: D-010 — the model is told our shot boundaries

Resolved 2026-07-26, **option 2**. Not an open question; implement it this way.

The PySceneDetect boundaries go into the **prompt text** as a numbered list, and the model returns
`shot_index` against it. Alignment in T007 becomes an index lookup instead of a fuzzy overlap
match against timestamps the constraints already declare untrustworthy.

- Boundaries arrive as an **optional keyword argument defaulting to `None`**, mirroring
  `detect_shots(path, threshold=)` (D-012) and `score_shot(..., shot_id=None)` (D-018), so
  `understand(path, fps, media_resolution)` stays literally callable as `docs/IDEA.md` writes it.
- Cost: ~117 lines of `idx t_start-t_end`, under 2K tokens against this clip's ~14K budget (D-003).
- With `None`, the model segments freely and returns `t_start_hint` / `t_end_hint`. **Keep that
  path working** — it is the fallback and the thing that makes the Path A seam real.

## Constraints that bite on this task specifically

- **One Gemini call per video, never per shot** (CLAUDE.md hard constraint 1). 117 shots means
  117 calls would blow the 10 RPM free-tier cap instantly. A design drifting toward per-shot calls
  is wrong **even if it works** — it throws away the cross-shot context that is the entire
  differentiator.
- **Free tier** (constraint 2). ≈30K tokens per 10-min video at `media_resolution=low` (66
  tok/frame, not 258) and `fps=0.5`. TPM cap 250K/min. On this 7:08 clip the visual budget is
  ~14K tokens (D-003), leaving room to try `fps=1.0` if 0.5 proves too coarse — **per-video knob,
  never a global edit**.
- **Model string is pinned: `gemini-3.5-flash`** (constraint 3). Do not "helpfully" swap it.
- **Gemini's timestamps are second-granular and never become `t_start` / `t_end`** (constraint 4).
  They may only be returned as `t_start_hint` / `t_end_hint` for alignment, and
  `ShotUnderstanding` already models them that way.
- **Pydantic models, never raw dicts** — `ShotUnderstanding` in `elvideo/schema/models.py` is the
  single source of truth and already exists. Don't hand-roll a parallel shape for the response
  schema without reconciling the two.
- **Prompt lives in a module-level constant or its own file, not inline in the call.** It will be
  iterated on, and the A/B writeup has to quote the exact version that produced the numbers.
- Type hints everywhere; docstrings citing `docs/IDEA.md` by section; ruff + mypy strict clean
  before checkpoint.

## Blockers and open decisions affecting this

- **None blocking.** `progress.json.blockers` is empty, D-010 is settled, `GEMINI_API_KEY` is
  present in `.env`.
- **Cost discipline is on you, not the tooling.** This is the first task that spends real quota.
  Free tier is 10 RPM — a retry loop with a bug in it is the realistic failure mode here, so
  bound the retries before running anything against a 48 MB upload.
- **Owner follow-up, blocks nothing:** CLAUDE.md hard constraint 6 and `docs/IDEA.md` still
  describe the Path A repo as a *live* manual-sync risk. Aspirational since D-016. Left unedited
  on purpose — don't act on it unprompted.

## Definition of done for the session

- `elvideo/index/gemini.py` implemented: `understand()` plus the pinned `MODEL` constant and the
  prompt constant. Every criterion above met, or explicitly recorded as not met.
- `tests/test_gemini.py` — the call-count assertion (mocked client, one `generate_content` per
  invocation regardless of shot count), the request payload carrying `gemini-3.5-flash` / `low` /
  the passed `fps`, the missing-`GEMINI_API_KEY` `RuntimeError`, the unparseable-response
  `RuntimeError`, 429 backoff behaviour, and out-of-range `shot_index` failing loudly. Mark any
  test that makes a real API call `slow` — `tests/test_transcribe.py` has the precedent.
- **One real run against `in.mp4`**, with the token usage and wall-clock recorded, and the
  returned `editorial_score` distribution eyeballed — if every shot scores ~0.8, that's a prompt
  bug, the same way a `quality` metric returning 0.8 for everything would be (D-017 has the
  precedent for how that check was written).
- `uv run pytest` passes, `uv run ruff check .` clean, `uv run mypy elvideo` strict clean.
- Gemini call settings, the prompt version, and the measured token count recorded in
  `state/decisions-log.md` as a new `D-0XX` — same treatment as D-012, D-015, D-017.

End with `/checkpoint`.

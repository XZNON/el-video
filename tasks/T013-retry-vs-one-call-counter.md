# T013 — A 429 retry trips the one-call assertion and discards the whole run

**Status:** `done` — found and fixed 2026-07-27 (session 011), **D-034**. Unblocks
[T012](T012-coarser-intervals.md). Zero Gemini requests spent: the 429 path is testable with a fake
client.

## Goal

Make the one-call-per-video instrument count what hard constraint 1 actually forbids — a second
*understanding request* — instead of counting transport retries of the same request. Today a single
HTTP 429 anywhere in the Gemini call aborts a run that has already succeeded, discards ~235s of
completed work, writes no index, and burns two of the day's twenty requests (D-031).

## The defect

`elvideo/index/gemini.py` increments `_calls` **inside** the closure that `tenacity` retries:

```python
def _once() -> types.GenerateContentResponse:
    global _calls
    _calls += 1
    logger.info("gemini generate_content request #%d ...", _calls, ...)
    return client.models.generate_content(...)

return _with_backoff("generate_content", _once)
```

`elvideo/index/build.py` then asserts the counter is exactly 1:

```python
calls = gemini.generate_call_count()
if calls != 1:
    raise RuntimeError(f"expected exactly 1 Gemini generate_content call for this video, counted {calls} ...")
```

**So the D-020 backoff and the hard-constraint-1 assertion cannot both fire in the same run.** The
backoff exists to survive a 429; surviving one guarantees the run is then thrown away.

Observed on T012 run 1, `--threshold 50`:

```
00:45:52 gemini generate_content request #1
00:45:57 gemini generate_content request #2
         gemini tokens: prompt=27325 output=9560 total=36885
         gemini understanding: 78 shots in 103.0s
error: expected exactly 1 Gemini generate_content call for this video, counted 2
```

The understanding **succeeded** — 78 shots, hint alignment 78 of 78, scores 0.45–0.78. The run
aborted after it, at the quality stage boundary, and wrote nothing.

**Why it went unseen until now.** T007, T009 and T011 made roughly two dozen live runs and never hit
a 429 mid-call, so the interaction was never exercised. `build.py`'s own docstring anticipates it
("A count above 1 is also what a 429 retry storm looks like from here") — the behaviour is
*documented*, just never *experienced*, and losing a completed run to it is plainly not the
intended trade.

## Reads / depends on

- `state/decisions-log.md` **D-020** (why backoff wraps both API steps), **D-031** (why a discarded
  run is expensive in the resource that binds), **D-019** (`RETRY_MAX_ATTEMPTS`)
- `.claude/CLAUDE.md` hard constraint 1 — the rule the instrument serves
- `docs/IDEA.md` § *Definition of done (s1)*, bullet 2 — "One Gemini call per video (assert call
  count == 1 in logs)"
- Tasks: T004 (`gemini.py`), T007 (`build.py`, where the assertion lives), T012 (blocked by this)

## Inputs / outputs

**In:** no new inputs. **Out:** no schema change, no change to `footage_index.json`. This is
instrumentation only — `gemini.generate_call_count()` changes meaning, and a second counter is
added beside it.

## Acceptance criteria

- [x] `generate_call_count()` counts **understanding requests**, one per `understand()` invocation,
      independent of how many transport attempts each took.
- [x] A separate `generate_attempt_count()` reports transport attempts, so a retry is **more**
      visible than before, not less. `reset_call_count()` zeroes both.
- [x] A retried call **still logs loudly** — the attempt number and the reason are in the log at
      `WARNING`, not buried at `INFO`.
- [x] `build.py`'s assertion still fails a genuine second understanding request — a per-shot loop is
      caught exactly as before. Covered by a test that calls `understand()` twice.
- [x] A test proves the new behaviour on the case that broke: one `understand()` whose first attempt
      raises 429 and whose second succeeds leaves `generate_call_count() == 1` and
      `generate_attempt_count() == 2`, and `build_index()` completes.
- [x] `uv run pytest`, `uv run ruff check .`, `uv run mypy elvideo` clean.
- [x] Logged as a decision — the instrument's meaning changed, and `docs/IDEA.md` § *Definition of
      done* bullet 2 says "assert call count == 1", which this reinterprets rather than breaks.

## Constraints that bite here

- **One Gemini call per video, never per shot** (hard constraint 1) — this task must not weaken it.
  The distinction being drawn is between *one request retried* and *two requests issued*; the second
  stays forbidden and stays asserted.
- **`gemini-3.5-flash` pinned** (hard constraint 3), **free tier only** (hard constraint 2). No live
  request is needed to close this task — the 429 path is testable with a fake client.
- **The schema is a contract** (hard constraint 6). Untouched: this changes no field.

## Notes

The cheap wrong fix is loosening `build.py` to `>= 1` or deleting the assertion. That removes the
only automated guard against the refactor CLAUDE.md names `build.py` as the place to catch, and
`docs/IDEA.md` makes the assertion part of s1's definition of done. Fix the counter, not the check.

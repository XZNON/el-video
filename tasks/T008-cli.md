# T008 — `cli.py`: entrypoint

**Status:** `done` — verified live on `in.mp4`, 2026-07-26. 234.7s, 117 shots, 43 candidates, 1 Gemini call.

## Goal

Make `python -m elvideo index in.mp4` work end to end.

One command, one file, no UI. This is the first line of the Definition of Done, and it's also the
interface the co-founder runs — **same command, same schema output as Path A**, or the A/B isn't
one command away.

## Reads / depends on

- `docs/IDEA.md` § *Scope* ("CLI on one file"), § *Definition of done* (bullets 1 and 7)
- Tasks: T007 (this is a thin wrapper over `build_index`).

## Inputs / outputs

**In:** CLI args — `video` (positional), `--work-dir`, `--fps`, `--media-resolution`.
**Out:** `{work_dir}/footage_index.json`, plus per-stage timing on stdout. Exit code 0 on
success, non-zero on failure.

## Acceptance criteria

- [x] `uv run python -m elvideo index in.mp4` produces a valid `work/footage_index.json`.
      **Live, not mocked:** 117 shots, 1436 words, 43 candidates, 0 `[MOCKED]` captions, one
      `generate_content` call, 38,956 tokens, `validate_index()` clean.
- [x] `--fps` overrides the sampling rate **for that run only** — the per-video knob, surfaced
      where a user can actually reach it. (`test_fps_override_does_not_touch_the_default`.)
- [x] `--media-resolution` accepts only `low` / `medium` / `high`, rejecting anything else with a
      usable message rather than passing it through to the API. A `StrEnum` choice, so the parser
      rejects it: `Invalid value for '--media-resolution': 'ultra' is not one of 'low', 'medium',
      'high'.`, exit 2, before any work starts.
- [x] `--work-dir` is respected, and the directory (plus `keyframes/`) is created if absent —
      up front, so an unwritable path fails at second zero rather than after the pipeline.
- [x] Per-stage timing is printed in human-readable form via `rich`. A `RichHandler` renders the
      lines `build_index` already logs; `build.py` was not changed to serve the CLI's formatting.
- [x] Exit code is **non-zero** on: missing video file, missing `GEMINI_API_KEY`, schema
      validation failure. Silent success on a broken run is the worst outcome here.
- [x] Error messages name the fix, not just the fault — "GEMINI_API_KEY not set; copy .env.example
      to .env" beats a stack trace.
- [x] `--help` explains the `--fps` knob well enough that someone picks the right value for
      talking-head vs action footage without reading the spec. Both cases named with numbers
      (0.2-0.5 vs 1-2), and the cost consequence stated; asserted in `test_cli.py`.
- [x] `.env` is loaded via `python-dotenv` at startup.

## Constraints that bite here

- **Same command as Path A.** The invocation is part of the contract, not just the schema. If
  Path A's entrypoint differs, log it in `state/decisions-log.md`.
- No UI, no upload form, no batch mode, no concurrent jobs — see `docs/IDEA.md` § *Non-goals*.
  One file per invocation.

## Notes

**Two traps already hit and fixed in the scaffold — don't reintroduce them.**

1. Typer collapses a single-command app, which drops the subcommand name and makes
   `python -m elvideo index in.mp4` invalid (it becomes `python -m elvideo in.mp4`). An
   `@app.callback()` forces multi-command mode. Adding a second command later would make it
   unnecessary, but leave it — the DoD depends on that exact invocation.
2. **Keep help strings ASCII-only.** The Windows console is cp1252; a `≤` in the app help
   crashed `--help` with `UnicodeEncodeError`. Docstrings and markdown are fine — anything Typer
   prints is not.

Keep this module thin. Everything real belongs in `build.py`; the CLI parses arguments, loads the
environment, formats output, and picks an exit code. If logic starts accumulating here, it's in
the wrong file — the co-founder's path has to be able to reuse `build_index` without inheriting
our argument parsing.

`elvideo/__main__.py` already exists to make `python -m elvideo` resolve (see D-006).

## Outcome (2026-07-26)

`elvideo/cli.py` is ~90 lines of parsing plus two guards; `build.py` was not touched.
41 tests in `tests/test_cli.py`, all with `build_index` mocked. Three decisions logged as **D-026**:
`--threshold` exposed (D-012 calls it a per-video knob), `gemini.check_api_key()` made public so a
missing key fails before the ~2.5-minute transcription stage, and timing rendered by attaching a
handler rather than by changing `build_index`'s return type.

**Two output defects the live run exposed, both fixed here:**

1. **Em dashes in log and exception messages** rendered as `?` on the cp1252 console — the same
   trap as the help strings, one layer down, and invisible until the CLI existed to print them.
   Five messages in `gemini.py`, one in `probe.py`, one in `transcribe.py` are now ASCII.
   Docstrings were left alone: nothing prints them.
2. **`lightning` printed at INFO despite the root logger being at WARNING**, because it sets a
   level on its own logger at import. Fixed with a filter on the handler (third-party `WARNING`
   and above still shows). The ffmpeg/h264 `mmco: unref short failure` chatter is *not* fixable
   from here — native code writes it to the process's stderr, below Python's logging.

**Not done:** `--verbose` / `--quiet`, a JSON output mode, and any progress bar. None are in the
criteria and each is a reason for this module to grow.

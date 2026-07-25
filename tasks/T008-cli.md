# T008 — `cli.py`: entrypoint

**Status:** `not_started`

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

- [ ] `uv run python -m elvideo index in.mp4` produces a valid `work/footage_index.json`.
- [ ] `--fps` overrides the sampling rate **for that run only** — the per-video knob, surfaced
      where a user can actually reach it.
- [ ] `--media-resolution` accepts only `low` / `medium` / `high`, rejecting anything else with a
      usable message rather than passing it through to the API.
- [ ] `--work-dir` is respected, and the directory (plus `keyframes/`) is created if absent.
- [ ] Per-stage timing is printed in human-readable form via `rich`.
- [ ] Exit code is **non-zero** on: missing video file, missing `GEMINI_API_KEY`, schema
      validation failure. Silent success on a broken run is the worst outcome here.
- [ ] Error messages name the fix, not just the fault — "GEMINI_API_KEY not set; copy .env.example
      to .env" beats a stack trace.
- [ ] `--help` explains the `--fps` knob well enough that someone picks the right value for
      talking-head vs action footage without reading the spec.
- [ ] `.env` is loaded via `python-dotenv` at startup.

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

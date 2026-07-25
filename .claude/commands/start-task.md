---
description: Load a task's full context, restate its goal + acceptance criteria, mark it in_progress
argument-hint: <task-id, e.g. T004>
---

Start work on task **$ARGUMENTS**.

## Step 1 — Read, in this order. Do not skip and do not skim.

1. `state/progress.json` — what's live, what's done, what's blocked.
2. The last ~3 entries of `state/session-log.md` — what the previous session actually left behind.
3. `state/decisions-log.md` — check whether any **unresolved** decision blocks this task. If one
   does, say so up front; don't code around it silently.
4. `tasks/$ARGUMENTS-*.md` — **in full**. This is the task contract.
5. The `docs/IDEA.md` section that task file cites under "Reads / depends on" — **in full**.
6. `.claude/CLAUDE.md` hard constraints, if not already in context.

## Step 2 — Restate before writing any code

Report back to the user, compactly:

- **Goal** — one or two sentences, in your own words.
- **Acceptance criteria** — the checklist, verbatim from the task file.
- **Inputs / outputs** — what this module consumes and emits, with types.
- **Dependencies** — which tasks must already be done. If a prerequisite is incomplete per
  `progress.json`, **stop and say so** rather than stubbing past it.
- **Constraint check** — name the hard constraints from `.claude/CLAUDE.md` that bear on this
  task specifically (e.g. for T004: one call per video, `gemini-3.5-flash` pinned,
  `media_resolution=low`, Gemini timestamps never used for `t_start`/`t_end`).
- **Open questions**, if any. Ask them now, not halfway through.

Then wait for the user to confirm or correct before implementing.

## Step 3 — Mark it live

Update `state/progress.json`:

- `current_task` = `"$ARGUMENTS"`
- `status` = `"in_progress"`
- `last_updated` = current ISO-8601 timestamp

Also flip the task's **Status** line in `tasks/$ARGUMENTS-*.md` and its row in `tasks/backlog.md`
to `in_progress`.

## Step 4 — Then implement

Follow the conventions in `.claude/CLAUDE.md`: type hints everywhere, pydantic models from
`elvideo/schema/models.py` (never ad hoc dicts), docstrings citing the relevant `docs/IDEA.md`
section, `ruff` clean, tests via `pytest`.

Work only the scope in the task file. Something else that needs doing turns up? `/new-task` it —
don't expand this one.

**End the session with `/checkpoint`.**

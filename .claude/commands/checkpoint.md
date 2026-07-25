---
description: End-of-session state update — progress.json, session-log, backlog, next session prompt
---

Close out this session. Do all four steps; a checkpoint that skips step 3 is not a checkpoint.

First, re-read `state/progress.json` and the tail of `state/session-log.md` so you're updating
what's actually on disk, not what you remember writing.

Be honest about what happened. If something is half-done, say half-done. If a test fails, record
that it fails and paste the shortest decisive line. A checkpoint that overstates progress makes
the next session start from a false premise — that costs more than the admission does.

## 1. Update `state/progress.json`

```json
{
  "current_task": "T0XX or null if the task closed cleanly",
  "status": "in_progress | blocked | task_complete | scaffold_complete",
  "completed_tasks": ["append the task id only if every acceptance criterion is met"],
  "blockers": ["concrete and actionable, e.g. 'T009 needs the agreed A/B video (D-003)'"],
  "open_decisions": ["drop ids resolved in decisions-log.md this session"],
  "last_updated": "<current ISO-8601 timestamp>"
}
```

A task moves to `completed_tasks` only when **all** its acceptance criteria pass — not when the
code is written. Partial work stays `in_progress` with a note in the log.

## 2. Append to `state/session-log.md`

Use the entry format in `prompts/templates/session-start-template.md`. Cover:

- **Date** and the task(s) worked.
- **Done** — what actually landed, with file paths.
- **Not done / deferred** — scope that was in the task file but isn't finished, and why.
- **Decisions made** — anything you chose that wasn't already specified. Cross-reference
  `state/decisions-log.md` and add an entry there if it touches the schema, the Gemini call
  settings, or the shared contract with Path A.
- **Blockers** — what's in the way, and what would unblock it.
- **Next** — the specific next task.

Append. Never rewrite or condense earlier entries.

## 3. Sync `tasks/` files

- Update the **Status** line in each `tasks/T0XX-*.md` you touched.
- Update the matching row in `tasks/backlog.md` so the index doesn't drift from the task files.

## 4. Generate the next session prompt

Write `prompts/session-start/NNN-<slug>.md`, where `NNN` is the next free 3-digit number in that
directory and `<slug>` names the upcoming task(s). Build it from
`prompts/templates/session-start-template.md`. It must be **paste-ready** — the user drops it
into a cold Claude Code session with zero other context and it works. So it must contain:

- Which state files to read first (`state/progress.json`, last ~3 of `state/session-log.md`,
  `.claude/CLAUDE.md`).
- The next task id and title, and the `/start-task T0XX` command to run.
- That task's **acceptance criteria restated in full** — not a link to them.
- The relevant `docs/IDEA.md` section to read.
- Any hard constraints that specifically bite on that task.
- Live blockers and unresolved decisions that affect it.

Finally, print the path of the generated prompt so the user knows what to paste next time.

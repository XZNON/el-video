---
description: Scaffold a new tasks/T0XX-<name>.md for work that came up mid-stream
argument-hint: <short-name, e.g. keyframe-cache>
---

Create a new task file for **$ARGUMENTS** — work that came up mid-stream and wasn't in the
original T001–T010 breakdown.

## 1. Pick the id

List `tasks/` and take the next free `T0XX`. Never renumber or reuse an existing id — session
logs and `progress.json` reference them.

## 2. Confirm it's actually a new task

Before writing the file, check it isn't already covered by an existing `tasks/T0XX-*.md`. If it
is, say so and extend that task's acceptance criteria instead of creating a duplicate.

If it's a *decision* rather than a unit of work (something needing a call with the co-founder,
say), it belongs in `state/decisions-log.md`, not here.

## 3. Write `tasks/T0XX-$ARGUMENTS.md`

Use the exact structure of the seeded tasks (open `tasks/T001-probe.md` as the reference):

```markdown
# T0XX — <Title>

**Status:** `not_started`

## Goal

<One paragraph. What exists at the end that doesn't exist now.>

## Reads / depends on

- `docs/IDEA.md` § <section name>
- Tasks: <ids that must land first, or "none">

## Inputs / outputs

**In:** <types and sources>
**Out:** <types and destinations>

## Acceptance criteria

- [ ] <checkable, not aspirational — "returns X for input Y", not "works well">

## Constraints that bite here

- <the hard constraints from .claude/CLAUDE.md that specifically apply>

## Notes

<Why this came up mid-stream, and what prompted it. Future sessions need the origin story.>
```

Acceptance criteria must be **checkable**. "Handles errors gracefully" is not a criterion;
"raises `ValueError` with the file path when ffprobe exits non-zero" is.

## 4. Register it

- Add a row to `tasks/backlog.md`: id, title, status, one-line note.
- If it blocks or is blocked by existing tasks, note that in **both** task files.
- If it changes the near-term plan, mention it at the next `/checkpoint`.

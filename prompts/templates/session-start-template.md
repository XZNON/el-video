# Templates

Two templates live here. `/checkpoint` uses both — one to append to `state/session-log.md`, one
to generate the next paste-ready kickoff prompt.

---

## A. Session-log entry format

Appended to `state/session-log.md` at every `/checkpoint`. Append only — never rewrite or
condense earlier entries; the drift between what a session planned and what it did is exactly
what a later session needs to see.

```markdown
## <YYYY-MM-DD> — <task id(s)> · <short title>

**Task(s):** T0XX — <title>
**Status at end:** not_started | in_progress | partial | blocked | done

### Done
- <what actually landed, with file paths>

### Not done / deferred
- <scope that was in the task file but isn't finished, and why>

### Decisions made
- <anything chosen that wasn't already specified; cross-reference decisions-log D-0XX>

### Blockers
- <what's in the way, and what specifically would unblock it>

### Next
- <the specific next task, and the generated prompt file for it>
```

Be honest. Half-done is "half-done"; a failing test is recorded as failing, with the shortest
decisive line of output. A log that overstates progress makes the next session start from a false
premise, which costs more than the admission does.

---

## B. Next-session kickoff prompt format

Written to `prompts/session-start/NNN-<slug>.md`. **This is the file the user pastes into a cold
Claude Code session**, so it has to stand alone: assume zero context, zero memory of this
conversation, and no knowledge beyond what it names.

Acceptance criteria get **restated in full**, not linked. A link is one more step between the
agent and the thing it must satisfy.

```markdown
# Session NNN — <task id(s)>: <title>

## Read these first, in this order

1. `state/progress.json` — what's live, what's blocked
2. Last ~3 entries of `state/session-log.md` — what the previous session left behind
3. `.claude/CLAUDE.md` — hard constraints and session protocol
4. `tasks/T0XX-<name>.md` — in full
5. `docs/IDEA.md` § <the section that task cites>

Then run `/start-task T0XX`.

## Where things stand

<2–4 sentences. What exists, what doesn't, what the last session actually finished.>

## This session: T0XX — <title>

**Goal:** <one or two sentences>

**Acceptance criteria** (restated in full — the task file is authoritative if they disagree):

- [ ] <criterion>
- [ ] <criterion>

## Constraints that bite on this task specifically

- <only the ones that actually apply here — not the whole list from CLAUDE.md>

## Blockers and open decisions affecting this

- <D-0XX — what it blocks, what would resolve it. "None" if none.>

## Definition of done for the session

<What must be true to run `/checkpoint` and call this task complete.>

End with `/checkpoint`.
```

---

## Numbering

`NNN` is the next free 3-digit number in `prompts/session-start/`, starting at `001`. Never
renumber — the session log references these by filename.

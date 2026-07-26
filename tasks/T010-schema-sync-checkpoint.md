# T010 — Schema-sync checkpoint

**Status:** `done` (2026-07-26) — resolved as a **self-lock**, not a sync. See `state/decisions-log.md` **D-016**.

> **This task was rewritten mid-project.** It was authored as *"a conversation with the
> co-founder — not a solo call, that's the whole point."* On 2026-07-26 the owner confirmed the
> repo is **solo**: there is no Path A counterparty. With nobody to sync with, the task's real
> content is the decisions themselves, made by the owner and logged with reasoning. The original
> framing is kept below for the record.

## Goal

Lock the `footage_index.json` contract so T006/T007 stop building on unconfirmed assumptions.

`docs/IDEA.md` on the contract: *"Lock it before either of us codes further."* That still holds
with one person — the cost of a late schema change is the same whether it was one repo or two.

## Outcome

| Decision | Resolution | Where |
|---|---|---|
| D-001 — full index vs top-N | **Full index + `is_candidate`**. Top-N is a view, not a format; the discarded shots are what downstream questions need. | log only, no code change — the scaffold already implemented it |
| D-002 — shared vs vendored | **Moot.** Vendored, settings pinned in code and guarded by tests: `ContentDetector`/`27.0` (D-012), `base`/`int8`/`cpu`/`en` (D-015). | `scenes.py`, `transcribe.py` |
| D-013 — `index_meta` records the detector | **Shipped.** `scene_detector` + `scene_threshold`, required, no defaults. | `models.py`, `footage_index.schema.json`, `tests/test_schema.py` |
| D-016 — governance | New entry: no counterparty, decisions owner-locked, reversal condition recorded. | `state/decisions-log.md` |

D-010 (does `understand()` see the shot list) was settled the same day — option 2, boundaries in
the prompt text — but it was never a cross-repo question and belongs to T004.

## Acceptance criteria

- [x] All open contract decisions resolved and logged in `state/decisions-log.md` with date and
      reasoning — **not** just a verbal "yeah sounds good."
- [x] `open_decisions` in `state/progress.json` is emptied of the resolved ids.
- [x] The A/B test video is identified and accessible. `in.mp4`, D-003 — resolved earlier.
- [x] Detector/threshold and WhisperX settings are agreed and written down. D-012, D-015, as
      module constants with tests asserting them.
- [ ] ~~`footage_index.schema.json` compared field-for-field against what Path A emits~~ — **N/A,
      no Path A exists.** The closest available substitute now runs instead:
      `tests/test_schema.py` asserts field parity between the two *local* artifacts, and the
      `index_meta` block was added to that check while landing D-013 (it had been missing).
- [ ] ~~If Path A's entrypoint differs from `python -m elvideo index in.mp4`, log it~~ — **N/A.**

## What stays true without a counterparty

- **The schema keeps its A/B shape.** `path_variant: "gemini" | "local"`, nullable
  `editorial_score` / `moment_reason`. Free to keep, expensive to re-add. Do not "simplify" these
  away on the grounds that only one path exists — that's a one-way door (D-016).
- **Settings stay pinned.** Reproducibility was the real requirement; a second reader was only
  the motivation.
- **Schema changes still get logged.** Cheap discipline, and the next reader is you in a month.

## Open follow-up for the owner

`.claude/CLAUDE.md` hard constraint 6 and `docs/IDEA.md` both describe the co-founder repo as a
**live** manual-sync risk. That is now aspirational. Deliberately **not** edited — CLAUDE.md's own
rule is to log conflicts rather than silently pick a side. Decide whether to soften constraint 6
or leave it as intended future state. Logged in D-016.

---

## Original framing (superseded, kept for the record)

Resolve the three open decisions from `docs/IDEA.md` § *Open decisions to confirm*, and confirm
the `footage_index.json` shape against what Path A actually emits.

**In:** a conversation with the co-founder. Not a solo call — that's the whole point.
**Out:** three resolved entries in `state/decisions-log.md`, each with the decision, the date,
and the reasoning.

Cheapest possible version: send the schema file and the three questions in one message, get one
reply, log it. That's it. It does not need a meeting.

**Constraint that bit here:** *"The schema is a two-repo change surface with no automated sync.
This task is the manual sync."* With one repo, the surface is one-sided — but the discipline of
writing the decision down survives the reason for it.

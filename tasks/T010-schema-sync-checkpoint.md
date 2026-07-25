# T010 — Schema-sync checkpoint with the co-founder

**Status:** `not_started` — **do this early, not last**

## Goal

Resolve the three open decisions from `docs/IDEA.md` § *Open decisions to confirm*, and confirm
the `footage_index.json` shape against what Path A actually emits.

Numbered last, but **it should happen first** — or at least before T009. `docs/IDEA.md` says of
the contract: *"Lock it before either of us codes further."* Every day this stays open, both
repos code further against an unconfirmed shape.

## Reads / depends on

- `docs/IDEA.md` § *Open decisions to confirm*, § *Shared contract*
- `docs/schema.md` § *Open decisions affecting this contract*
- `state/decisions-log.md` — D-001, D-002, D-003
- Tasks: blocks T009. Overlaps T006.

## Inputs / outputs

**In:** a conversation with the co-founder. Not a solo call — that's the whole point.
**Out:** three resolved entries in `state/decisions-log.md`, each with the decision, the date,
and the reasoning.

## The three decisions

### D-001 — Output shape: full index vs top-N

Full index + `is_candidate` flag (what the doc assumes and the scaffold implements), or a
separate top-N moments list?

Full index keeps both paths schema-identical, and "best moments" becomes a filter rather than a
format. **Recommend confirming the assumption.** Needs a yes, not a guess — T006 and T007 both
build on it.

### D-002 — Shared vs vendored PySceneDetect + WhisperX

One shared module, or each path vendors its own?

`docs/IDEA.md` recommends **shared**, to isolate the experimental variable to Understanding only.
If vendored, shot boundaries and transcripts may differ between paths and the diff stops being
clean — a caption difference could then be caused by a threshold difference, and the A/B answers
nothing.

Whatever's chosen, the concrete settings must match: detector type and threshold (T002), model
size, compute type, device (T003).

### D-003 — The A/B test video

One agreed ~10-min clip both paths run on, checked into the repo or on a shared drive link.

**Pick it before coding further** so "done" is comparable. Blocks T009 entirely. Criteria worth
agreeing: ~10 min, representative footage (SMB b-roll, not a stock demo reel), has speech (or
`words[]` is untested), has real cuts (or shot detection is untested), and is legally shareable
if it ends up in a hackathon writeup.

## Acceptance criteria

- [ ] All three decisions resolved and logged in `state/decisions-log.md` with date and
      reasoning — **not** just a verbal "yeah sounds good."
- [ ] `open_decisions` in `state/progress.json` is emptied of the resolved ids.
- [ ] The A/B test video is identified and accessible to both sides.
- [ ] `footage_index.schema.json` is compared field-for-field against what Path A emits, and any
      divergence is either fixed or logged.
- [ ] Detector/threshold and WhisperX settings are agreed and written down in both repos.
- [ ] If Path A's entrypoint command differs from `python -m elvideo index in.mp4`, that's
      logged too — the invocation is part of the contract.

## Constraints that bite here

- **The schema is a two-repo change surface with no automated sync.** This task is the manual
  sync. Skipping it doesn't make the risk go away, it just makes it show up later, in the merge.
- The A/B only means something if the *only* difference between the two runs is Understanding.
  Every unresolved decision here is a second variable.

## Notes

`docs/IDEA.md`'s own framing: this is *"a 10-minute message with the co-founder, not a solo
call."* Resolving these alone defeats the purpose — an assumption confirmed by yourself is still
an assumption.

Cheapest possible version: send the schema file and the three questions in one message, get one
reply, log it. That's it. It does not need a meeting.

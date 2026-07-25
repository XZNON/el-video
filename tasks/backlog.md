# Backlog

Index only. The task files are the contract — read those, not this table.
Kept in sync by `/checkpoint`.

| ID | Title | Status | Note |
|---|---|---|---|
| [T001](T001-probe.md) | `probe.py` — ffprobe wrapper | `not_started` | Root of the graph. Small; proves ffmpeg is really on PATH. |
| [T002](T002-scenes.md) | `scenes.py` — shot detection | `not_started` | Frame-accurate `t_start`/`t_end`. Everything downstream indexes off these. |
| [T003](T003-transcribe.md) | `transcribe.py` — WhisperX | `not_started` | Word-level timing + `words_in_range()`. Slowest stage. |
| [T004](T004-gemini-understanding.md) | `gemini.py` — native understanding | `not_started` | **Path B core.** Exactly one call per video. Has an open design question inside. |
| [T005](T005-quality.md) | `quality.py` — OpenCV scoring | `not_started` | Laplacian + exposure. Deterministic, no LLM. Needs T002. |
| [T006](T006-schema-and-models.md) | `schema/` — contract + validator | `partial` | Models + JSON Schema seeded by scaffold; `validate_index()` and the co-founder sign-off remain. |
| [T007](T007-build-orchestrator.md) | `build.py` — orchestrator | `not_started` | The join point. Alignment is the hard part. Per-stage timing. Needs T001–T006. |
| [T008](T008-cli.md) | `cli.py` — entrypoint | `not_started` | Thin wrapper over `build_index`. Needs T007. |
| [T009](T009-e2e-validation.md) | E2E validation | `not_started` | Unblocked — video picked (`in.mp4`, 7:08, 117 shots). Proves every DoD claim with a number. |
| [T010](T010-schema-sync-checkpoint.md) | Schema-sync checkpoint | `not_started` | D-003 done. D-001/D-002 remain, plus D-013. |

## Suggested order

**T010 first** (or at least its D-003 half) — it's a message, not a work session, and it unblocks
T009 while stopping T006/T007 from building further on unconfirmed assumptions.

Then: T001 → T002 → T003 → T005 → T004 → T007 → T008 → T009.

T004 sits after the classical stages on purpose: the prompt work is easier to judge once there's
a real shot list and transcript to look at.

## Statuses

`not_started` · `in_progress` · `partial` · `blocked` · `done`

`done` means every acceptance criterion in the task file passes — not that the code is written.

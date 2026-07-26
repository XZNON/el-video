# Backlog

Index only. The task files are the contract — read those, not this table.
Kept in sync by `/checkpoint`.

| ID | Title | Status | Note |
|---|---|---|---|
| [T001](T001-probe.md) | `probe.py` — ffprobe wrapper | `done` | Smoke-tested on `in.mp4`; matches D-003 numbers. |
| [T002](T002-scenes.md) | `scenes.py` — shot detection | `done` | 117 shots on `in.mp4` in 25.3s, gapless, frame-accurate. See D-014. |
| [T003](T003-transcribe.md) | `transcribe.py` — WhisperX | `done` | 1436 words on `in.mp4` in 102.7s warm, CPU. Settings pinned in D-015. |
| [T004](T004-gemini-understanding.md) | `gemini.py` — native understanding | `not_started` | **Path B core.** Exactly one call per video. Design question settled: D-010 option 2. |
| [T005](T005-quality.md) | `quality.py` — OpenCV scoring | `not_started` | Laplacian + exposure. Deterministic, no LLM. Needs T002. |
| [T006](T006-schema-and-models.md) | `schema/` — contract + validator | `partial` | Shape locked (D-001, D-013 shipped). Only `validate_index()` remains. |
| [T007](T007-build-orchestrator.md) | `build.py` — orchestrator | `not_started` | The join point. Alignment is the hard part. Per-stage timing. Needs T001–T006. |
| [T008](T008-cli.md) | `cli.py` — entrypoint | `not_started` | Thin wrapper over `build_index`. Needs T007. |
| [T009](T009-e2e-validation.md) | E2E validation | `not_started` | Unblocked — video picked (`in.mp4`, 7:08, 117 shots). Proves every DoD claim with a number. |
| [T010](T010-schema-sync-checkpoint.md) | Schema-sync checkpoint | `done` | Solo repo (D-016) — resolved as a self-lock. D-001/D-002/D-013 all closed. |

## Suggested order

T010 is closed, so nothing gates the contract any more. Remaining: **T005 → T004 → T007 → T008 →
T009**.

T004 sits after T005 on purpose: the prompt work is easier to judge with a real shot list,
transcript, and quality score already on the page.

## Statuses

`not_started` · `in_progress` · `partial` · `blocked` · `done`

`done` means every acceptance criterion in the task file passes — not that the code is written.

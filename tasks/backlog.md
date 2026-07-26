# Backlog

Index only. The task files are the contract — read those, not this table.
Kept in sync by `/checkpoint`.

| ID | Title | Status | Note |
|---|---|---|---|
| [T001](T001-probe.md) | `probe.py` — ffprobe wrapper | `done` | Smoke-tested on `in.mp4`; matches D-003 numbers. |
| [T002](T002-scenes.md) | `scenes.py` — shot detection | `done` | 117 shots on `in.mp4` in 25.3s, gapless, frame-accurate. See D-014. |
| [T003](T003-transcribe.md) | `transcribe.py` — WhisperX | `done` | 1436 words on `in.mp4` in 102.7s warm, CPU. Settings pinned in D-015. |
| [T004](T004-gemini-understanding.md) | `gemini.py` — native understanding | `blocked` | **Path B core.** Code complete, 47 tests green, settings pinned in D-019. **API key has no quota (D-021)** — 4 criteria need one live call. |
| [T005](T005-quality.md) | `quality.py` — OpenCV scoring | `done` | 117 shots in 18.8s on `in.mp4`, mean 0.465, spread 0.06–0.86. Formula pinned in D-017. |
| [T006](T006-schema-and-models.md) | `schema/` — contract + validator | `partial` | **Next up.** Shape locked (D-001, D-013 shipped). Only `validate_index()` remains — and T007 needs it. |
| [T007](T007-build-orchestrator.md) | `build.py` — orchestrator | `not_started` | The join point. Alignment is the hard part. Per-stage timing. Needs T001–T006. |
| [T008](T008-cli.md) | `cli.py` — entrypoint | `not_started` | Thin wrapper over `build_index`. Needs T007. |
| [T009](T009-e2e-validation.md) | E2E validation | `blocked` | Video picked (`in.mp4`, 7:08, 117 shots), but **needs a usable API key (D-021)** — an E2E run with no Gemini call proves nothing. |
| [T010](T010-schema-sync-checkpoint.md) | Schema-sync checkpoint | `done` | Solo repo (D-016) — resolved as a self-lock. D-001/D-002/D-013 all closed. |

## Suggested order

T010 is closed, so nothing gates the contract any more. Remaining: **T004 → T007 → T008 → T009**.

T004 sat after T005 on purpose: the prompt work is easier to judge with a real shot list,
transcript, and quality score already on the page — all three now exist.

Corrected order: **T006 → T007 → T008**. T006 is one function (`validate_index()`) and T007 cannot
satisfy "validates before it is written" without it, so it goes first rather than being absorbed
into T007's session.

**T004 is code-complete but cannot be signed off without a key that has quota (D-021).** T006/T007
do not wait on it — `understand()`'s signature and output are settled, so the orchestrator can be
built and tested against a mocked understanding pass. T009 does wait on it: an end-to-end run with
no Gemini call proves nothing about the Path B claim.

## Statuses

`not_started` · `in_progress` · `partial` · `blocked` · `done`

`done` means every acceptance criterion in the task file passes — not that the code is written.

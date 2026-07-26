# Backlog

Index only. The task files are the contract — read those, not this table.
Kept in sync by `/checkpoint`.

| ID | Title | Status | Note |
|---|---|---|---|
| [T001](T001-probe.md) | `probe.py` — ffprobe wrapper | `done` | Smoke-tested on `in.mp4`; matches D-003 numbers. |
| [T002](T002-scenes.md) | `scenes.py` — shot detection | `done` | 117 shots on `in.mp4` in 25.3s, gapless, frame-accurate. See D-014. |
| [T003](T003-transcribe.md) | `transcribe.py` — WhisperX | `done` | 1436 words on `in.mp4` in 102.7s warm, CPU. Settings pinned in D-015. |
| [T004](T004-gemini-understanding.md) | `gemini.py` — native understanding | `done` | **Path B core.** Live: 1 call, 117 shots, 96.8s, 38.4K tokens, scores 0.50–0.88 / 26 distinct. Prompt iterated p1→p2 (**D-024**); token target restated (**D-025**). |
| [T005](T005-quality.md) | `quality.py` — OpenCV scoring | `done` | 117 shots in 18.8s on `in.mp4`, mean 0.465, spread 0.06–0.86. Formula pinned in D-017. |
| [T006](T006-schema-and-models.md) | `schema/` — contract + validator | `done` | `validate_index()` landed, 31 tests. `t_end > t_start` is enforced in code — JSON Schema can't express it (**D-022**). |
| [T007](T007-build-orchestrator.md) | `build.py` — orchestrator | `partial` | Implemented, 33 tests. 117 shots / 1436 words / 158.5s on `in.mp4` with Gemini mocked. **Only the <5 min criterion is open, and it is now runnable** — the real stage measures 96.8s, so a live run projects to ~230–255s. Threshold in D-023. |
| [T008](T008-cli.md) | `cli.py` — entrypoint | `not_started` | **Next.** Thin wrapper over `build_index`. Two Typer bugs from bootstrap already recorded in the task file. |
| [T009](T009-e2e-validation.md) | E2E validation | `not_started` | Unblocked — key works, video picked (`in.mp4`, 7:08, 117 shots). Assert tokens against **~40K, not 30K** (D-025). |
| [T010](T010-schema-sync-checkpoint.md) | Schema-sync checkpoint | `done` | Solo repo (D-016) — resolved as a self-lock. D-001/D-002/D-013 all closed. |

## Suggested order

Remaining: **T008 → T009**, then close out T007's last criterion.

**Nothing is blocked.** D-021 (the dead API key) was resolved on 2026-07-26 — the owner supplied a
free-tier key and T004's live run passed. Every earlier note in this file about waiting on a key is
now history.

T008 first because it needs no key and `python -m elvideo index in.mp4` is a Definition-of-Done
criterion in its own right. Once it lands, **one live CLI run closes T007's `<5 min` criterion and
feeds T009 at the same time** — the same ~38K tokens buying two things instead of one.

## Statuses

`not_started` · `in_progress` · `partial` · `blocked` · `done`

`done` means every acceptance criterion in the task file passes — not that the code is written.

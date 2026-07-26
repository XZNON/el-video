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
| [T007](T007-build-orchestrator.md) | `build.py` — orchestrator | `done` | Implemented, 33 tests. Last criterion closed live via the CLI: **234.7s end to end** on `in.mp4`, 117 shots / 1436 words / 1 Gemini call. Caveat in the task file: the clip is 7:08, so a true 10-min video projects to ~300–330s. |
| [T008](T008-cli.md) | `cli.py` — entrypoint | `done` | Thin wrapper, 36 tests, both Typer traps guarded. `--threshold` exposed and `check_api_key()` preflighted (**D-026**). Fixed two output defects the live run exposed: em dashes on cp1252, and lightning logging past root=WARNING. |
| [T009](T009-e2e-validation.md) | E2E validation | `not_started` | **Next.** Most evidence already measured (234.7s, 1 call, 38,956 tokens, 43 candidates, validates clean). Left: the run report in a **tracked** file, the 5-shot hand spot-check, the machine. Assert tokens against **~40K, not 30K** (D-025). |
| [T010](T010-schema-sync-checkpoint.md) | Schema-sync checkpoint | `done` | Solo repo (D-016) — resolved as a self-lock. D-001/D-002/D-013 all closed. |

## Suggested order

Remaining: **T009**, and that is the whole list.

**Nothing is blocked.** D-021 (the dead API key) was resolved on 2026-07-26; T007's `<5 min`
criterion was closed the same day by the first live CLI run. Every earlier note in this file about
waiting on a key is history.

T009 is now mostly **writing down** what has already been measured rather than measuring it: the
live run produced 234.7s, 117 shots, 1436 words, one Gemini call, 38,956 tokens and 43 candidates
against a clean `validate_index()`. What it still owes is a report in a **tracked** file (`work/`
is gitignored), a five-shot hand spot-check that the captions describe what is on screen, and the
machine recorded. A second live run is optional — the numbers above are current.

## Statuses

`not_started` · `in_progress` · `partial` · `blocked` · `done`

`done` means every acceptance criterion in the task file passes — not that the code is written.

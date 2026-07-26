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
| [T009](T009-e2e-validation.md) | E2E validation | `done` | **8 pass, 2 fail, 1 not-verifiable** — [`docs/run-report.md`](../docs/run-report.md). Passes: 1 call, 234.7s, 117 frame-accurate shots, 1436 words, 3 validators clean, 37 distinct scores. Fails: **38,956 tokens** vs the spec's 30K (target was wrong — D-025), and the **hand spot-check, 13 of 17 captions on the wrong shot** (**D-027** → T011). Not verifiable: the Path A A/B (D-016). |
| [T010](T010-schema-sync-checkpoint.md) | Schema-sync checkpoint | `done` | Solo repo (D-016) — resolved as a self-lock. D-001/D-002/D-013 all closed. |
| [T011](T011-caption-shot-alignment.md) | Caption ↔ `shot_index` alignment | `not_started` | **Next, and the repo's top defect.** Gemini's judgments land on the wrong shots — 2 match / 2 partial / 13 mismatch of 17 hand-checked. Boundaries, keyframes and transcripts ruled out; not a constant offset. Measure first, then fix, still **one call** (**D-027**). |

## Suggested order

Remaining: **T011**, and that is the whole list. T001–T010 are all `done`.

**Nothing is blocked.** D-021 (the dead API key) was resolved on 2026-07-26, and the pipeline has
run end to end for real.

**The s1 pipeline is structurally finished and substantively wrong in one place.** T009 proved the
architecture claims — one Gemini call, 38,956 tokens, 234.7s, a schema-valid 117-shot index on a
free-tier key with no 429 — and then its hand spot-check found that **the captions and scores are
attached to the wrong shots** (D-027). Nothing automated caught it, because every gate in the repo
is a shape check and a misfiled caption has the right shape.

T011 is therefore the only thing worth doing next. It starts with a **repeatable measurement**
against the existing index, not a change: 17 hand-checked shots prove the problem is real and are
not enough to attribute a cause. Budget the live runs before starting — each is ~39K tokens and
~4 minutes, and D-024's prompt work took three.

## Statuses

`not_started` · `in_progress` · `partial` · `blocked` · `done`

`done` means every acceptance criterion in the task file passes — not that the code is written.

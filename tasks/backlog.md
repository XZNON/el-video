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
| [T011](T011-caption-shot-alignment.md) | Caption ↔ `shot_index` alignment | `partial` | **Improved, not closed.** `p3` anchors the prompt on timestamps instead of letting the model count shots: **2/17 → 13/17**, then **6/17** on a replicate of the same config. Cause partly attributed (the model was counting, not locating); run-to-run variance exceeds the effect. Criterion 2 (≥12/17) and criterion 3 (`shot_059`) **fail**. Measurement is now repeatable — `elvideo/eval/alignment.py` (**D-028**, **D-029**). Left: **`fps=1.0`, 2–3 runs** — D-027 hypothesis 2 is still untested. |

## Suggested order

Remaining: **T011**, still, and that is the whole list. T001–T010 are all `done`.

**Nothing is blocked.** D-021 (the dead API key) was resolved on 2026-07-26, and the pipeline has
run end to end for real.

**The s1 pipeline is structurally finished and substantively wrong in one place.** T009 proved the
architecture claims — one Gemini call, 38,956 tokens, 234.7s, a schema-valid 117-shot index on a
free-tier key with no 429 — and then its hand spot-check found that **the captions and scores are
attached to the wrong shots** (D-027). Nothing automated caught it, because every gate in the repo
is a shape check and a misfiled caption has the right shape.

**Session 008 measured it and moved it, and did not close it.** The measurement is now repeatable
(`python -m elvideo.eval.alignment work/footage_index.json`, frozen 17-shot sample, Gemini judge
that reproduced the human column 16/17). Prompt `p3` took clean agreement from **2/17 to 13/17** —
and the identical configuration then scored **6/17**, so the honest result is "2/17 → 6–13/17,
n=2". `p3` ships because both runs beat the baseline; ≥12/17 does not hold.

**The next move is one flag.** D-027's hypothesis 2 — frame starvation at `fps=0.5`, ~1.8 sampled
frames per shot — has never been tested. Raise `--fps` to 1.0, ~+14K tokens per run, and because
run-to-run variance is larger than most effects here, **budget 2–3 runs at each setting, not one**.
Grade every run rather than eyeballing captions: the whole point of session 008's harness is that
the number survives the session that produced it.

## Statuses

`not_started` · `in_progress` · `partial` · `blocked` · `done`

`done` means every acceptance criterion in the task file passes — not that the code is written.

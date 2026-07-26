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
| [T011](T011-caption-shot-alignment.md) | Caption ↔ `shot_index` alignment | `partial` | **Improved, ceiling measured, not closed.** `p3` anchors the prompt on timestamps instead of letting the model count shots: **2/17 → mean 10.7/17** over three runs (13/6/13). **`fps` tested and rejected** — `fps=1.0` gives 9/8/9 at +30% tokens, so D-027 hypothesis 2 (frame starvation) is **wrong** and the default stays 0.5 (**D-030**). D-027 is now **`resolved`**, with a documented ~60% ceiling rather than a fix. Criteria 2 and 3 still **fail** (criterion 3 is 1 of 3 — `shot_005` matches on all six runs, `shot_059` on none); criterion 6 **closed as not achievable this way**; criterion 7 **met**. Also found: the free tier's real limit is **20 requests/day**, not the TPM cap (**D-031**). **CLOSED by design 2026-07-27 (D-032)** — `partial` is its final state, and it does **not** enter `completed_tasks`. Every lever inside its scope is measured; the remaining idea changes `shots[]` and is [T012](T012-coarser-intervals.md). Closing produced the consumer-trust split and known-limitations section in the run report, at **zero live requests**. |
| [T012](T012-coarser-intervals.md) | Coarser intervals — ~60 shots, not 117 | `not_started` | **T011's named successor (D-032). Nothing run.** Hypothesis: the model is not bad at watching video, it is bad at telling 117 near-identical sub-3s intervals apart. One flag — `--threshold 40` on `ContentDetector` (D-012, D-026). **Two costs to pay first:** the frozen 17-shot sample stops being directly comparable (remap by *timestamp*, state the changed denominator), and fewer shots is a worse index for some questions. Full pipeline required every run (~235s); **8 of the day's 20 requests** for two thresholds × two runs, graded. |

## Suggested order

Remaining: **T012**, and only if someone chooses to spend requests on it. T001–T010 are `done`;
**T011 is closed at `partial` by design** (D-032) and is not coming back.

**Nothing is blocked.** D-021 (the dead API key) was resolved on 2026-07-26, and the pipeline has
run end to end for real.

**The s1 pipeline is structurally finished and substantively wrong in one place.** T009 proved the
architecture claims — one Gemini call, 38,956 tokens, 234.7s, a schema-valid 117-shot index on a
free-tier key with no 429 — and then its hand spot-check found that **the captions and scores are
attached to the wrong shots** (D-027). Nothing automated caught it, because every gate in the repo
is a shape check and a misfiled caption has the right shape.

**Session 008 measured it and moved it. Session 009 bounded it.** The measurement is repeatable
(`python -m elvideo.eval.alignment work/footage_index.json`, frozen 17-shot sample, Gemini judge
that reproduced the human column 16/17). Prompt `p3` took clean agreement from **2/17 to a mean of
10.7/17** over three runs. Then `fps` — the last untested hypothesis — was measured at three runs
per setting and **rejected**: `fps=1.0` scores 9/8/9 against `fps=0.5`'s 13/6/13, at +30% tokens,
while also flattening the editorial scoring. D-027 is `resolved`; ≥12/17 still does not hold.

**There is no cheap lever left, and that is the finding.** Prompt anchoring is worth ~9 matches of
17; frame budget is worth none; the model's own timestamps detect nothing. `gemini-3.5-flash`
attributing a moment to one of **117 sub-3-second intervals** across 7 minutes is roughly **60%
reliable**, and nothing available inside one call closes the rest.

**Session 010 made that decision: (b).** T011 is closed at `partial` with the ceiling accepted and
stated, at **zero live requests** — `docs/run-report.md` § *T011 closed — partial by design* now
carries a field-by-field **what a consumer may / may not trust** split, a known-limitations list for
whoever writes the downstream agent, and the A/B claim in two halves: **what is in the video holds;
which second does not.** See **D-032**.

**Option (a) survives as [T012](T012-coarser-intervals.md), `not_started`** — merge adjacent sub-2s
shots via `--threshold` so the model picks among ~60 distinguishable intervals. It is a change to
`shots[]`, so it is a product decision, and it must pay for the broken sample comparability before
its first run. **Budget it in requests, not tokens** — 20 `generate_content` calls per day (D-031),
and a graded index run costs two.

**s1 is otherwise finished.** The pipeline works end to end on a free-tier key: one Gemini call,
117 shots, 1,436 words, ~42.5K tokens, 234.7s, three validators clean.

## Statuses

`not_started` · `in_progress` · `partial` · `blocked` · `done`

`done` means every acceptance criterion in the task file passes — not that the code is written.

# Architecture — Path B (Gemini-native)

Orientation doc. Read this before reading code; read `IDEA.md` before arguing with either.

## The pipeline

```
in.mp4 ──▶ probe (ffprobe) ─────────────┐
        ├▶ shots  (PySceneDetect)  ──────┤
        ├▶ words  (WhisperX, word-level) ┤
        └▶ Gemini native pass ───────────┤──▶ build ──▶ footage_index.json  (local disk)
             (whole video, 1 call)        │              + validate against schema
           quality (OpenCV Laplacian) ────┘
```

Four producers feed one assembler. `probe`, `scenes`, `transcribe`, and `gemini` are independent
of each other and could run concurrently; `quality` needs shot boundaries first (it scores a
keyframe sampled from inside each shot). `build` joins all five and validates.

## Module map

Mirrors `IDEA.md` § *Module layout* exactly, so Path A and Path B stay swappable at the seam.

| Module | Signature | Role | Ownership |
|---|---|---|---|
| `elvideo/index/probe.py` | `probe(path) -> VideoMeta` | ffprobe wrapper | shared |
| `elvideo/index/scenes.py` | `detect_shots(path) -> list[Shot]` | shot boundaries | shared, PySceneDetect |
| `elvideo/index/transcribe.py` | `transcribe(path) -> list[Word]` | word-level timing | shared, WhisperX |
| `elvideo/index/gemini.py` | `understand(path, fps, media_resolution) -> list[ShotUnderstanding]` | understanding | **Path B core** |
| `elvideo/index/quality.py` | `score_frame(img) -> float` | deterministic quality | shared, OpenCV |
| `elvideo/index/build.py` | `build_index(...) -> dict` | orchestrate + validate | orchestrator |
| `elvideo/cli.py` | `index` command | entrypoint | — |
| `elvideo/schema/models.py` | pydantic models | **single source of truth for types** | contract |
| `elvideo/schema/footage_index.schema.json` | JSON Schema | contract, language-independent | contract |

`gemini.py` is the analogue of El-Video's pluggable `caption.py` — same role in the graph,
different backend (whole-video Gemini vs per-frame moondream2). That's the swap the A/B measures.

## The one rule

**One Gemini call per video, not per shot.**

A 10-min video is 100–300 shots. Per-shot calls blow the free tier's 10 RPM cap immediately, and
they also throw away the thing that makes this path interesting: Gemini watching the clip as a
continuous piece of time, with audio, and reasoning about what makes a moment good *relative to
the rest of the video*. Frame-by-frame captioning can't do that by construction.

So the call takes the whole file and returns the whole shot list in one structured response.

## Division of labour: what the model decides vs what it doesn't

This is the part that's easy to get wrong. The model is asked for **judgment**, never for
**measurement**.

| Field | Source | Why |
|---|---|---|
| `t_start`, `t_end` | **PySceneDetect** | Frame-accurate. Gemini's timestamps are second-granular — unusable for cuts. |
| `transcript` | **WhisperX** via `words_in_range()` | Word-level timing drives precise cuts and filler removal. |
| `quality` | **OpenCV** Laplacian + exposure | Deterministic and reproducible. An LLM cannot be either. |
| `caption` | Gemini | Description — judgment. |
| `editorial_score` | Gemini | "How good a moment, 0–1" — judgment, and the whole point of the path. |
| `moment_reason` | Gemini | The *why* behind the score. Path B's edge over Path A. |
| `tags` | Gemini | Judgment. |
| `is_candidate` | derived | A view over `editorial_score`, not a separate model output. |
| `embedding` | — | Reserved. Stays `null` in v1. |

Gemini returns a per-shot list; `build.py` aligns it to the PySceneDetect shot list. Alignment is
by index/order and overlap, **not** by trusting the model's timestamps.

## Gemini call settings (locked)

- **Model:** `gemini-3.5-flash` — pinned string, free tier.
- **`media_resolution: low`** — 66 tok/frame instead of 258. SMB b-roll doesn't need fine-text
  reading. 3× cheaper.
- **`fps: 0.5`** default (one frame / 2s). Raise to 1–2 for action-heavy footage (gyms), lower for
  static (talking-head). **Per-video knob, not a global default change.**
- **Structured output** — force strict JSON via response schema, no prose.
- **Backoff** — exponential (`tenacity`) on HTTP 429.

Token math: 10-min @ low-res @ 0.5 fps ≈ **~30K tokens/video**. TPM cap is 250K/min, so iteration
is effectively free all day.

## Storage

Local filesystem. Nothing to database yet.

```
project/
├── in.mp4
├── work/
│   ├── keyframes/shot_###.png      # extracted for quality scoring
│   └── footage_index.json          # THE Part-1 output
```

The video itself lives in the **Gemini File API for 48h (free)** during processing — we don't
store it, Google does, temporarily. GCS/Firestore are Phase 2.

## Speed

Target: 10-min video indexed in **<5 min wall-clock** on a laptop, dominated by transcription +
the single Gemini call — *not* by frame count. That's the whole point of working at shot level.

`build.py` logs **per-stage** timing, not just the total, because the A/B compares speed as well
as quality and "5 minutes" tells you nothing about which path is slow where.

## Out of scope (s1)

Render / ffmpeg edit · EDL execution · Director / Critic / Delivery agents · embeddings · vector
DB · GCP (GCS / Firestore / Cloud Run) · app / UI / upload · concurrent jobs.

See `IDEA.md` § *Non-goals / deferred*. These are all real and all later — write them down so they
don't creep in.

## Lineage

The **LAVE language-index** pattern ([arXiv:2402.10294](https://arxiv.org/abs/2402.10294)),
upgraded from frame-captioning to native long-context video. UniVA
([2511.08521](https://arxiv.org/abs/2511.08521)) is the whole-pipeline map; s1 builds one stage of
it.

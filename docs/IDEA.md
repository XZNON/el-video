# Idea.md — v1 / Stage 1 (Understanding & Index)

**One line:** Turn one ≤10-min video into a shot-level text index (`footage_index.json`) that an agent can later reason over — Gemini-native path, running locally on the free tier, zero cloud, zero credits.

This is **only Part 1** of the pipeline (video → structured index → local store). Render, Director, Critic, and Delivery are _out of scope for s1_.

---

## Why this slice, this way

We're running a real **A/B on the Understanding stage**, because that is the one decision that defines the product ("does Gemini-native understanding beat a local frames-to-text index?"). Two implementations, **one shared output contract**:

|               | Path A — co-founder (El-Video)          | Path B — this doc (Shivalik)                 |
| ------------- | --------------------------------------- | -------------------------------------------- |
| Shot cuts     | PySceneDetect                           | PySceneDetect _(shared — keep classical)_    |
| Transcript    | faster-whisper / WhisperX               | WhisperX _(shared — need word-level timing)_ |
| Understanding | moondream2, 1 keyframe/shot (local VLM) | **Gemini 3.5 Flash, one native-video pass**  |
| Quality flags | OpenCV Laplacian                        | OpenCV Laplacian _(shared)_                  |
| Cost          | local compute                           | ~30K tokens/video, free tier                 |
| Output        | `footage_index.json`                    | **same `footage_index.json`**                |

Because both emit the identical schema, "then we discuss what's next" is a 20-minute glue conversation, not a merge. The diff between the two indexes on the _same_ footage **is** the architecture decision — and later, the hackathon evidence.

Lineage: this stage is the **LAVE language-index** pattern (arXiv:2402.10294), upgraded from frame-captioning to native long-context video. UniVA (2511.08521) is the whole-pipeline map; we build one stage of it here.

---

## Scope

**s1 does:**

1. Ingest a local `in.mp4` (≤10 min), probe it.
2. Detect shot boundaries (frame-accurate).
3. Transcribe audio with word-level timestamps.
4. **One Gemini pass over the whole video** → per-shot understanding: caption, editorial score + reason, tags, moment-candidate flag.
5. Per-shot quality score (OpenCV, deterministic).
6. Assemble + validate `footage_index.json`, write to local disk.

**s1 explicitly does NOT:**

- No render / ffmpeg edit. No EDL execution.
- No Director, Critic, or Delivery agents.
- No embeddings (schema _reserves_ the field; we do not build the step).
- No GCP — no GCS, no Firestore, no Cloud Run. Local filesystem only.
- No app, no UI, no upload form. CLI on one file.

---

## Architecture (Path B)

```
in.mp4 ──▶ probe (ffprobe) ─────────────┐
        ├▶ shots  (PySceneDetect)  ──────┤
        ├▶ words  (WhisperX, word-level) ┤
        └▶ Gemini native pass ───────────┤──▶ build ──▶ footage_index.json  (local disk)
             (whole video, 1 call)        │              + validate against schema
           quality (OpenCV Laplacian) ────┘
```

**The one rule that makes free-tier work: one Gemini call per video, not per shot.** A 10-min video is 100–300 shots; per-shot calls would blow 10 RPM instantly. Gemini watches the whole clip once and returns the full shot list in a single structured response. This is also the differentiator — native long-context temporal + audio-visual understanding, not frame-by-frame captioning.

### Gemini call settings (locked)

- **Model:** `gemini-3.5-flash` (pinned string; free tier).
- **`media_resolution: low`** — 66 tok/frame not 258. SMB b-roll doesn't need fine-text reading. 3× cheaper.
- **`fps: 0.5`** default (one frame / 2s) — raise to 1–2 for action-heavy footage (gyms), lower for static (talking-head). Per-video knob, not global.
- **Structured output** — force strict JSON (response schema / "return only JSON, no prose").
- **Backoff** — wrap in exponential backoff on HTTP 429.
- Token math: 10-min @ low-res @ 0.5fps ≈ **~30K tokens/video**. TPM cap is 250K/min → iterate freely all day.

### Module layout (drop-in with El-Video's seam)

Path B slots into the _same_ interfaces so either path is swappable:

```
elvideo/index/
  scenes.py       detect_shots(path) -> [Shot]              # shared, PySceneDetect
  transcribe.py   transcribe(path)   -> [Word]              # shared, WhisperX
  gemini.py       understand(path, fps, res) -> [ShotUnderstanding]   # Path B core
  quality.py      score_frame(img)   -> float               # shared, OpenCV
  build.py        build_index(...)   -> dict (validated)    # orchestrator
```

`gemini.py` is the analogue of El-Video's pluggable `caption.py` — same role (understanding), different backend (whole-video Gemini vs per-frame moondream2).

---

## Shared contract — `footage_index.json` (extended)

Base = El-Video's fields. Extensions = `editorial_score`, `moment_reason`, `is_candidate`, reserved `embedding`. **Both paths must emit this. Lock it before either of us codes further.**

```json
{
  "video": {
    "path": "in.mp4",
    "duration_s": 600.0,
    "fps": 30.0,
    "w": 1080,
    "h": 1920
  },
  "index_meta": {
    "path_variant": "gemini", // "gemini" | "local"
    "model": "gemini-3.5-flash",
    "media_resolution": "low",
    "sample_fps": 0.5
  },
  "shots": [
    {
      "id": "shot_007",
      "t_start": 42.1, // frame-accurate, from PySceneDetect
      "t_end": 48.33,
      "transcript": "so this is our weekend brunch special", // words_in_range()
      "caption": "chef plating a dosa, steam rising, centered subject, warm light",
      "editorial_score": 0.86, // Gemini: how good a moment, 0-1
      "moment_reason": "hero food shot, clean framing, natural sound bite",
      "is_candidate": true, // flagged good-moment (derived view over full index)
      "tags": ["food", "indoor", "hero"],
      "quality": 0.79, // OpenCV Laplacian + exposure, deterministic
      "embedding": null // RESERVED — not populated in v1
    }
  ],
  "words": [{ "t": 42.1, "d": 0.22, "w": "so" }] // flat word-level, drives precise cuts + filler removal
}
```

Notes:

- **Full index, not top-N.** Every shot is emitted; "best moments" = filter `is_candidate` / sort by `editorial_score`. Keeps both paths schema-identical. _(This is the one open call — confirm.)_
- `editorial_score` + `moment_reason` are Path B's edge; Path A may leave them null or approximate. That gap is the A/B signal.
- `embedding` stays `null` in v1. If we ever add cross-video search (Phase 2), it's a per-shot vector + a local SQLite/FAISS store — still no GCP.

---

## Storage & speed (the "storage and speed" ask)

**Storage:** local filesystem. There is nothing to database yet.

```
project/
├── in.mp4
├── work/
│   ├── keyframes/shot_###.png      # extracted for quality scoring
│   └── footage_index.json          # THE Part-1 output
```

The 10-min video itself lives in the **Gemini File API for 48h (free)** during processing — we don't store it, Google does, temporarily. Firestore/GCS are Phase-2 (both have free tiers when we get there; not needed now).

**Speed target (s1, laptop):** end-to-end index of a 10-min video in **< 5 min wall-clock**, dominated by transcription + the single Gemini call — _not_ by frame count (that's the whole point of shot-level). Log per-stage timing so the A/B compares speed, not just quality.

---

## Definition of done (s1)

- [ ] `python -m elvideo index in.mp4` produces a `footage_index.json` that **validates against the shared schema**.
- [ ] One Gemini call per video (assert call count == 1 in logs).
- [ ] Full shot list with `t_start`/`t_end` frame-accurate (from PySceneDetect, not Gemini timestamps).
- [ ] `words[]` present with word-level timing (WhisperX).
- [ ] Runs on a **free-tier** key, ≤ ~30K tokens, no 429 on a single video.
- [ ] Per-stage timing logged.
- [ ] Same command, same schema output as co-founder's local path → A/B-ready on one shared test video.

---

## Open decisions to confirm

1. **Output shape** — full index + `is_candidate` flag (assumed), vs. separate top-N moments list. _Doc assumes full index._
2. **Whose PySceneDetect + WhisperX** — shared module, or each path vendors its own? (Recommend shared, to isolate the variable to Understanding only.)
3. **The A/B test video** — one agreed 10-min clip both paths run on, checked into the repo (or a shared drive link). Pick it before coding so "done" is comparable.

---

## Non-goals / deferred (write these down so they don't creep in)

Embeddings · vector DB · GCP (GCS/Firestore/Cloud Run) · render/ffmpeg · EDL execution · Director/Critic/Delivery agents · vernacular caption styling · reframe/music/brand-kit · multi-vertical rubrics · upload UI · concurrent jobs.

All real. All later. **s1 is: one video in, one validated `footage_index.json` out, on a laptop, for free.**

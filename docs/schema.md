# `footage_index.json` — the shared contract

**This schema is shared with a separate repo.** Path A (co-founder's El-Video, local VLM) and
Path B (this repo, Gemini-native) both emit it. Identical output shape is what makes the A/B a
20-minute glue conversation instead of a merge.

> **Changing this shape is a two-repo change.** This repo has no automated way to detect that the
> other side changed too. Any edit must be logged in `state/decisions-log.md` **and** manually
> synced with the co-founder. Treat it as an interface, not as your data model.

Two artifacts define it, and they must stay in lockstep:

| Artifact | For |
|---|---|
| `elvideo/schema/models.py` | Python — pydantic, the single source of truth every module imports |
| `elvideo/schema/footage_index.schema.json` | Cross-repo — language-independent, diffable against whatever Path A emits |

Change one, change the other. `tests/test_schema.py` guards them.

---

## Shape

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
    "path_variant": "gemini",
    "model": "gemini-3.5-flash",
    "media_resolution": "low",
    "sample_fps": 0.5
  },
  "shots": [
    {
      "id": "shot_007",
      "t_start": 42.1,
      "t_end": 48.33,
      "transcript": "so this is our weekend brunch special",
      "caption": "chef plating a dosa, steam rising, centered subject, warm light",
      "editorial_score": 0.86,
      "moment_reason": "hero food shot, clean framing, natural sound bite",
      "is_candidate": true,
      "tags": ["food", "indoor", "hero"],
      "quality": 0.79,
      "embedding": null
    }
  ],
  "words": [{ "t": 42.1, "d": 0.22, "w": "so" }]
}
```

## `video` — probe output

Straight from `ffprobe`, no interpretation. Produced by `probe.py` (T001).

| Field | Type | Notes |
|---|---|---|
| `path` | `str` | Path as given on the CLI. |
| `duration_s` | `float` | Seconds. |
| `fps` | `float` | Container frame rate — **not** the Gemini sampling rate. See `index_meta.sample_fps` for that. |
| `w`, `h` | `int` | Pixels. Vertical (1080×1920) is the common case for this footage. |

## `index_meta` — provenance

How this index was produced. This is what makes two indexes of the same footage comparable, so
it must reflect what actually ran, not what the defaults say.

| Field | Type | Notes |
|---|---|---|
| `path_variant` | `"gemini" \| "local"` | **The A/B discriminator.** This repo always emits `"gemini"`. |
| `model` | `str` | `"gemini-3.5-flash"` — pinned. Path A puts its local model name here. |
| `media_resolution` | `"low" \| "medium" \| "high"` | We use `low`: 66 tok/frame not 258, 3× cheaper. |
| `sample_fps` | `float` | Frames/sec fed to Gemini. Default `0.5`. Per-video knob — record the value actually used. |

## `shots[]` — the payload

One entry per PySceneDetect boundary. **Every shot is emitted — full index, not top-N** (see
*Open decisions* below).

| Field | Type | Source | Notes |
|---|---|---|---|
| `id` | `str` | derived | `shot_007` — zero-padded to 3, ordered by `t_start`. |
| `t_start` | `float` | **PySceneDetect** | Frame-accurate. **Never from Gemini** — its timestamps are second-granular. |
| `t_end` | `float` | **PySceneDetect** | Same. |
| `transcript` | `str` | **WhisperX** | Joined `words_in_range(t_start, t_end)`. Empty string if silent, not `null`. |
| `caption` | `str` | Gemini | What's visually happening. |
| `editorial_score` | `float` 0–1 | Gemini | How good a moment. **Path B's edge.** |
| `moment_reason` | `str` | Gemini | Why that score. **Path B's edge.** |
| `is_candidate` | `bool` | derived | Flagged good-moment. A view over the full index, not a model output. |
| `tags` | `list[str]` | Gemini | Free-form, lowercase. |
| `quality` | `float` 0–1 | **OpenCV** | Laplacian + exposure. Deterministic, no LLM. |
| `embedding` | `null` | — | **RESERVED. Stays `null` in v1.** |

## `words[]` — flat word-level timing

Not nested under shots — a flat list for the whole video. Drives precise cuts and filler removal
downstream, and is the substrate `words_in_range()` slices per shot.

| Field | Type | Notes |
|---|---|---|
| `t` | `float` | Start time, seconds. |
| `d` | `float` | Duration, seconds. |
| `w` | `str` | The word. |

Short keys are deliberate — there are thousands of these per video.

---

## Path A's edge vs Path B's edge

| Field | Path A (local VLM) | Path B (Gemini) |
|---|---|---|
| `t_start`, `t_end`, `transcript`, `quality` | identical | identical | 
| `caption` | per-keyframe moondream2 | whole-video native pass |
| `editorial_score` | may be `null` or approximate | populated, cross-shot aware |
| `moment_reason` | may be `null` | populated |
| `tags` | per-keyframe | whole-video context |

**The gap in `editorial_score` / `moment_reason` is the A/B signal.** Path A is allowed to leave
them null — the schema permits it — and that permission is the measurement, not a loophole.

The shared fields being byte-comparable is what makes the rest of the diff meaningful.

## Reserved: `embedding`

The field exists so adding cross-video search in Phase 2 isn't a schema break. It is `null` in
v1 and **no code computes it** — see `IDEA.md` § *Non-goals*. If it ever lands, it's a per-shot
vector plus a local SQLite/FAISS store. Still no GCP.

## Open decisions affecting this contract

Tracked in `state/decisions-log.md`; resolved in **T010**.

- **D-001 — full index vs top-N.** This doc assumes **full index + `is_candidate` flag**. "Best
  moments" = filter `is_candidate` / sort by `editorial_score`. Keeps both paths
  schema-identical. Needs confirming with the co-founder.
- **D-002 — shared vs vendored PySceneDetect/WhisperX.** Recommend shared, to isolate the A/B
  variable to Understanding only. If vendored, shot boundaries may differ between paths and the
  diff stops being clean.

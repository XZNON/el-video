"""Gemini-native understanding pass — **the Path B core**.

This is the analogue of El-Video's pluggable ``caption.py``: same role in the graph, different
backend (whole-video Gemini vs per-frame moondream2). Swapping this module out is exactly what
the A/B measures.

**The one rule that makes free-tier work: one Gemini call per video, never per shot.** A 10-min
video is 100–300 shots; per-shot calls blow the 10 RPM cap instantly, and they throw away the
thing that makes this path interesting — the model seeing the clip as continuous time, with
audio, and judging each moment *relative to the rest of the video*.

Settings are locked in ``docs/IDEA.md`` § *Gemini call settings*. Don't loosen them casually:
the whole point is that a 10-min video costs ~30K tokens against a 250K TPM cap, so iteration is
free all day.

The video is uploaded to the **Gemini File API**, which holds it for 48h at no cost. We don't
store it; Google does, temporarily — and this module deletes the handle when the call is done, so
a debugging loop doesn't leak an upload per run.

**Shot boundaries go into the prompt text** (``state/decisions-log.md`` D-010): the model is told
our PySceneDetect cuts as a numbered list and answers with ``shot_index`` against it, so T007's
alignment is an index lookup rather than a fuzzy overlap match against timestamps the constraints
already declare untrustworthy. Passing ``shots=None`` keeps the free-segmentation path alive —
the model then segments the video itself and returns ``t_start_hint`` / ``t_end_hint``.

The prompt lives here as a module constant with a :data:`PROMPT_VERSION`, not inline in the call:
it is the part of this module that gets iterated on, and the A/B writeup has to quote the version
that produced the numbers.
"""

from __future__ import annotations

import json
import logging
import os
import statistics
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TypeVar

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from elvideo.schema.models import MediaResolution, Shot, ShotUnderstanding

__all__ = [
    "DEFAULT_MEDIA_RESOLUTION",
    "DEFAULT_SAMPLE_FPS",
    "HINT_DRIFT_WARN_FRACTION",
    "HINT_TOLERANCE_S",
    "MODEL",
    "PROMPT_VERSION",
    "RETRY_MAX_ATTEMPTS",
    "RETRY_WAIT_MAX_S",
    "RETRY_WAIT_MULTIPLIER_S",
    "SEED",
    "SYSTEM_INSTRUCTION",
    "TEMPERATURE",
    "THINKING_LEVEL",
    "UPLOAD_POLL_INTERVAL_S",
    "UPLOAD_TIMEOUT_S",
    "check_api_key",
    "generate_attempt_count",
    "generate_call_count",
    "hint_drift",
    "is_rate_limited",
    "reset_call_count",
    "understand",
]

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

MODEL = "gemini-3.5-flash"
"""Pinned model string, free tier. Do not swap this for another model name."""

DEFAULT_SAMPLE_FPS = 0.5
"""One frame every 2s. A **per-video** knob: raise to 1–2 for action-heavy footage (gyms), lower
for static talking-head. Never change this default globally to fix one clip."""

DEFAULT_MEDIA_RESOLUTION: MediaResolution = "low"
"""66 tok/frame instead of 258 — 3× cheaper. SMB b-roll doesn't need fine-text reading."""

TEMPERATURE = 0.4
"""Pinned so two runs of the same clip are comparable.

Not 0.0: the scoring rubric asks for a *spread* across shots, and near-greedy decoding pulls the
model toward a handful of round numbers (the "everything is 0.8" failure the task calls a prompt
bug). Not 1.0 either — the A/B needs the understanding stage to be re-runnable."""

SEED = 7
"""Fixed sampling seed. Best-effort reproducibility only — the API does not guarantee identical
output across model revisions, but it removes run-to-run jitter as a variable in the A/B."""

THINKING_LEVEL = types.ThinkingLevel.LOW
"""Thinking budget for the one call. This is a judgment-per-shot task with an explicit rubric, not
a reasoning puzzle; high thinking would spend the free-tier budget on tokens that never reach the
index and add minutes to the <5 min wall-clock target."""

UPLOAD_TIMEOUT_S = 300.0
"""How long to wait for the File API to finish processing the upload before giving up. Server-side
video processing, not the transfer; a 10-min clip is typically ready in seconds."""

UPLOAD_POLL_INTERVAL_S = 2.0
"""Gap between File API state polls while the upload is ``PROCESSING``."""

RETRY_MAX_ATTEMPTS = 5
"""Bounded retries on HTTP 429. Free tier is 10 RPM, so a single video that trips the cap is
almost always a shared-key or debug-loop problem — retrying forever would hide it."""

RETRY_WAIT_MULTIPLIER_S = 4.0
"""Exponential backoff base: 4s, 8s, 16s, 32s between attempts."""

RETRY_WAIT_MAX_S = 60.0
"""Backoff ceiling. Beyond a minute the free-tier per-minute window has reset anyway."""

HINT_TOLERANCE_S = 1.0
"""Slack allowed between a reported hint and the shot it was filed against, per end.

Gemini's timestamps are second-granular (hard constraint 4), so anything tighter would count
rounding as drift. Anything looser would start absorbing the real thing: D-027's displacements are
whole shots — ``shot_022``'s content filed 3 shots away, ``shot_048``'s 15 — which is far outside
1s on a clip whose median shot is 2.68s."""

HINT_DRIFT_WARN_FRACTION = 0.25
"""Warn when more than this share of judgments describe a moment outside their own shot. Not zero:
a handful of coarse hints on sub-second shots is expected and is not the failure D-027 names."""

PROMPT_VERSION = "p3"
"""Bump on every prompt edit. The A/B writeup quotes the version that produced its numbers, and
``index_meta`` has no field for it — so this constant plus the log line is the record."""

_MEDIA_RESOLUTION_ENUM: dict[MediaResolution, types.MediaResolution] = {
    "low": types.MediaResolution.MEDIA_RESOLUTION_LOW,
    "medium": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
    "high": types.MediaResolution.MEDIA_RESOLUTION_HIGH,
}

SYSTEM_INSTRUCTION = """\
You are the assistant to a video editor cutting a short from raw footage. You watch the whole \
video once, with its audio, and judge every shot for whether it is worth cutting to.

You return JSON only. No prose, no markdown, no commentary outside the schema.

For each shot:

caption — what is visibly happening: subject, action, framing, light. One sentence. Describe what \
is on screen, not what you infer about intent or brand.

editorial_score — how good a moment this is, 0.0-1.0, judged against the OTHER shots in THIS \
video, not against video in general:
  0.85-1.00  hero moment. A peak of action or emotion, clean framing, the shot you would open or \
close on. Rare - expect a handful in a video, sometimes none.
  0.65-0.84  strong. Clear subject, purposeful motion, or a sound bite that stands on its own.
  0.40-0.64  useful connective tissue. Ordinary b-roll: real but replaceable. Most shots land here.
  0.15-0.39  weak. Cluttered, redundant with a better shot of the same thing, mid-action nothing, \
or a talking head saying nothing quotable.
  0.00-0.14  unusable. Transition frames, whip pans, severe blur, subject cut off, dead air.

Rank before you score. Watch the whole video, pick out the few shots you would actually build \
the edit around and the few you would never use, and let those anchor the top and bottom of your \
range. Then place everything else between them. Scoring shot by shot in isolation is what \
produces a video where every shot is a 0.6, and a video where every shot is a 0.6 is a video you \
have not judged.

Concretely, and these are requirements, not style notes:
  - The best shots in this video belong in the 0.85-1.00 band. Whatever the strongest moment \
here is, it IS the strongest moment here - do not withhold the top band because the footage is \
ordinary. The same goes downward: dead frames, black screens and whip pans belong below 0.15.
  - Use two decimals, and use the digits. 0.58 and 0.63 are different judgments; 0.60 for both is \
a refusal to choose. Do not round everything to multiples of 0.05.
  - No score should be shared by more than about ten shots. If a third of your scores land within \
0.1 of each other you have stopped judging and started labelling - go back and separate them.
  - Redundancy is a legitimate reason to score one of two similar shots lower. Say which one it \
is redundant with.

moment_reason — the EVIDENCE for that score, not a restatement of the caption. Name the specific \
thing that earned or lost the points: the framing, the action peak, the line that is said, the \
shot it repeats, the technical fault. At most 15 words.

A category label is not evidence. "Standard b-roll", "connective tissue", "establishing shot" say \
nothing a reader could disagree with - if you use words like those, say what makes this one so. \
"Third exterior pan of the same car" is evidence. "Standard exterior b-roll" is not.

tags — 2 to 5 lowercase tags, single words or hyphenated: subject, setting, shot type. \
e.g. "food", "indoor", "close-up", "hands", "wide".

Use the audio. A shot whose dialogue carries a usable line is worth more than the same picture in \
silence, and you are the only stage in this pipeline that hears both at once.\
"""
"""System instruction — the rubric half of the prompt. See :data:`PROMPT_VERSION`."""

_SHOT_LIST_PROMPT = """\
This video has already been cut into {count} shots by a frame-accurate shot detector. The \
boundaries are authoritative; they are what the final index is built on.

Judge EXACTLY these shots. Do not merge them, do not split them, do not invent shots, do not skip \
shots you find dull - a dull shot gets a low score, not an omission. Return exactly one object per \
shot, {count} in total, in this order, with shot_index set to the index below.

FIND EACH SHOT BY ITS TIMESTAMP, NOT BY COUNTING. Do not assume the k-th cut you notice is index \
k. This detector cuts far more finely than a person would: several listed shots can be one \
continuous-looking action, a slow pan can be split in two, and a shot can be under a second long. \
If you count cuts as you watch, you will drift out of step with the list and describe the right \
moments under the wrong indices. For every index, go to the start time listed for THAT index and \
describe what is on screen between that time and its end time. Nothing else.

Report where you actually looked. t_start_hint and t_end_hint are the timestamps of the moment \
you just described, read off the video - not copied back from the list. Then check yourself: for \
index k, the moment you describe must lie inside the k-th interval below. If it does not, you have \
described the wrong moment. Return to the listed times for index k and describe what is there \
instead. The list is authoritative; your reading of the clock is what bends.

If a listed shot is too short or too dark to see properly, say so in the caption, score it low, \
and still report its listed timestamps. A guess that borrows a neighbouring shot's content is \
worse than an honest "brief, indistinct frame".

index  start-end (seconds)
{shot_lines}\
"""

_FREE_SEGMENTATION_PROMPT = """\
Segment this video into shots yourself, in chronological order, and judge each one.

shot_index is the 0-based position in your own list. Also give t_start_hint and t_end_hint in \
seconds; second granularity is fine, they are used only to line your shots up against a \
frame-accurate detector's boundaries and never become the cut points themselves.\
"""

_calls = 0
"""Count of understanding *requests* — one per :func:`understand` call, retries excluded. See
:func:`generate_call_count` and ``tasks/T013-retry-vs-one-call-counter.md``."""

_attempts = 0
"""Count of ``generate_content`` transport *attempts*, retries included. See
:func:`generate_attempt_count`."""


class _Judgment(BaseModel):
    """Response schema when the model is given our shot boundaries (D-010).

    Deliberately *not* :class:`~elvideo.schema.models.ShotUnderstanding`: that model has optional
    hint fields, which turn into nullable branches in the generated response schema, and it forbids
    extras — both are constraints on our side of the wire, not the model's. This is the wire shape;
    it is converted to ``ShotUnderstanding`` after validation.
    """

    shot_index: int = Field(description="0-based index of the shot being judged, from the list.")
    caption: str = Field(description="What is visibly happening: subject, action, framing, light.")
    editorial_score: float = Field(description="How good a moment, 0.0-1.0.")
    moment_reason: str = Field(description="Evidence for the score. Not a restatement of caption.")
    tags: list[str] = Field(description="2-5 lowercase tags: subject, setting, shot type.")


class _JudgmentWithHints(_Judgment):
    """Response schema for the free-segmentation path (``shots=None``).

    Hints are required here because they are the *only* way to line the model's own segmentation up
    with PySceneDetect's. They are alignment aids and never become ``t_start`` / ``t_end``.
    """

    t_start_hint: float = Field(description="Approximate shot start, seconds. Alignment only.")
    t_end_hint: float = Field(description="Approximate shot end, seconds. Alignment only.")


def generate_call_count() -> int:
    """Number of understanding **requests** issued since import or the last reset.

    The instrumentation behind the *one call per video* rule: T009 asserts this is ``1`` after a
    full index run rather than trusting that the code path is what it looks like.

    **One per :func:`understand` invocation, whatever the transport did.** A 429 retry of the same
    request does not increment this — see :func:`generate_attempt_count` for that, and
    ``tasks/T013-retry-vs-one-call-counter.md`` for why the two were split. Hard constraint 1
    forbids *asking the model twice about one video*, which is what this counts; it does not forbid
    TCP from needing two goes at asking once. Counting attempts here meant a single 429 aborted a
    run that had already succeeded and threw ~235s of work away.
    """
    return _calls


def generate_attempt_count() -> int:
    """Number of ``generate_content`` transport attempts, retries included.

    Strictly ``>= generate_call_count()``. A gap between the two is a 429 that the D-020 backoff
    absorbed: harmless for correctness, expensive against the 20-requests/day free-tier quota
    (D-031), and therefore worth reporting rather than hiding.
    """
    return _attempts


def reset_call_count() -> None:
    """Zero both counters. For tests and for T009's per-run assertion."""
    global _calls, _attempts
    _calls = 0
    _attempts = 0


def understand(
    path: str,
    fps: float = DEFAULT_SAMPLE_FPS,
    media_resolution: MediaResolution = DEFAULT_MEDIA_RESOLUTION,
    *,
    shots: Sequence[Shot] | None = None,
) -> list[ShotUnderstanding]:
    """Watch the whole video in **one** Gemini call and return per-shot judgment.

    Exactly one request to the model per invocation, independent of shot count — instrumented via
    :func:`generate_call_count`, not merely intended. The response is forced to strict JSON via a
    response schema (no prose, no fences to strip), and the request is wrapped in exponential
    backoff on HTTP 429.

    What comes back is *judgment only*: caption, editorial score, reason, tags. Timings in the
    response are second-granular hints used for alignment and nothing else — ``t_start`` and
    ``t_end`` in the index always come from PySceneDetect.

    Args:
        path: Path to the source video. Uploaded to the Gemini File API for the call, and the
            handle is deleted afterwards.
        fps: Frames per second sampled from the video. Per-video knob; see
            :data:`DEFAULT_SAMPLE_FPS`.
        media_resolution: Token cost per frame. See :data:`DEFAULT_MEDIA_RESOLUTION`.
        shots: PySceneDetect boundaries, rendered into the prompt as a numbered list so the model
            answers with ``shot_index`` against it (D-010). Keyword-only with a ``None`` default so
            ``understand(path, fps, media_resolution)`` stays literally callable as
            ``docs/IDEA.md`` § *Module layout* writes it. With ``None`` the model segments the
            video itself and returns ``t_start_hint`` / ``t_end_hint`` instead.

    Returns:
        One :class:`~elvideo.schema.models.ShotUnderstanding` per shot, in chronological order.
        When ``shots`` is given, every ``shot_index`` is validated against ``len(shots)`` and the
        list is sorted by it; when it is ``None``, the count need not match PySceneDetect's and
        :func:`elvideo.index.build.build_index` owns alignment.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If ``fps`` is not positive or ``media_resolution`` is not a known value.
        RuntimeError: If ``GEMINI_API_KEY`` is unset, if the upload never becomes usable, if the
            rate limit survives :data:`RETRY_MAX_ATTEMPTS` attempts, or if the response cannot be
            parsed as the expected schema — including a ``shot_index`` outside the real shot range,
            which would otherwise attach captions to the wrong shots with nothing erroring.
    """
    global _calls

    if not Path(path).is_file():
        raise FileNotFoundError(f"video not found: {path}")
    if fps <= 0:
        raise ValueError(f"fps must be > 0, got {fps}")
    if media_resolution not in _MEDIA_RESOLUTION_ENUM:
        raise ValueError(
            f"unknown media_resolution {media_resolution!r}; "
            f"expected one of {sorted(_MEDIA_RESOLUTION_ENUM)}"
        )

    client = genai.Client(api_key=_api_key())
    # Hints on BOTH paths since p3. They are the only evidence of where the model actually looked,
    # and D-027 is the case where it looked in the wrong place with nothing erroring.
    schema: type[_Judgment] = _JudgmentWithHints
    prompt = _build_prompt(shots)

    started = time.perf_counter()
    uploaded = _upload(client, path)
    upload_s = time.perf_counter() - started

    try:
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            media_resolution=_MEDIA_RESOLUTION_ENUM[media_resolution],
            response_mime_type="application/json",
            response_schema=list[schema],  # type: ignore[valid-type]
            temperature=TEMPERATURE,
            seed=SEED,
            thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
        )
        contents = types.Content(
            role="user",
            parts=[
                types.Part(
                    file_data=types.FileData(
                        file_uri=uploaded.uri,
                        mime_type=uploaded.mime_type,
                    ),
                    # The sampling rate reaches the model here, per-part, not as a global setting.
                    video_metadata=types.VideoMetadata(fps=fps),
                ),
                types.Part(text=prompt),
            ],
        )

        call_started = time.perf_counter()
        response = _generate_with_backoff(client, contents, config, fps, media_resolution)
        call_s = time.perf_counter() - call_started
    finally:
        _delete_upload(client, uploaded)

    understandings = _parse(response, shots, with_hints=True)
    _log_usage(response, understandings, upload_s, call_s, time.perf_counter() - started)
    return understandings


def check_api_key() -> None:
    """Fail now if ``GEMINI_API_KEY`` is missing, instead of after the transcription stage.

    The understanding stage is fourth in ``build_index``: probe, shots and WhisperX run first and
    cost ~2.5 minutes on the test clip. Without this the CLI would spend all of it before
    discovering there is no key to call with — the same exit code, two and a half minutes later.
    Public only so ``elvideo.cli`` can preflight it; the real read still happens in
    :func:`understand`.

    Raises:
        RuntimeError: If it is unset or empty. The message names the fix.
    """
    _api_key()


def _api_key() -> str:
    """Read ``GEMINI_API_KEY`` from the environment or ``.env``.

    Raises:
        RuntimeError: If it is unset or empty.
    """
    load_dotenv()
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and paste a free-tier key from "
            "https://aistudio.google.com/apikey (or export GEMINI_API_KEY in this shell)."
        )
    return key


def _build_prompt(shots: Sequence[Shot] | None) -> str:
    """Render the user half of the prompt — the shot list, or the free-segmentation instruction.

    The boundary list is ~117 lines of ``idx start-end`` on the test clip, well under 2K tokens
    against a ~14K-token visual budget (D-003, D-010).
    """
    if shots is None:
        return _FREE_SEGMENTATION_PROMPT
    if not shots:
        raise ValueError("shots is empty; pass None to let the model segment the video itself")

    lines = "\n".join(f"{i} {s.t_start:.2f}-{s.t_end:.2f}" for i, s in enumerate(shots))
    return _SHOT_LIST_PROMPT.format(count=len(shots), shot_lines=lines)


def _upload(client: genai.Client, path: str) -> types.File:
    """Upload the video to the File API and wait until it is usable.

    The File API holds the video for 48h at no cost (``docs/IDEA.md`` § *Storage & speed*), but a
    freshly uploaded video is ``PROCESSING`` for a few seconds and referencing it too early fails
    the call.

    Raises:
        RuntimeError: If processing fails or does not finish inside :data:`UPLOAD_TIMEOUT_S`.
    """
    uploaded = _with_backoff("the File API upload", lambda: client.files.upload(file=path))
    deadline = time.monotonic() + UPLOAD_TIMEOUT_S

    while _state_name(uploaded) == "PROCESSING":
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"Gemini File API still PROCESSING {path} after {UPLOAD_TIMEOUT_S:.0f}s "
                f"(file {uploaded.name}). Retry, or check the clip is a supported format."
            )
        time.sleep(UPLOAD_POLL_INTERVAL_S)
        uploaded = client.files.get(name=str(uploaded.name))

    if _state_name(uploaded) != "ACTIVE":
        raise RuntimeError(
            f"Gemini File API upload of {path} is {_state_name(uploaded)}, not ACTIVE "
            f"(file {uploaded.name}). The video cannot be used for this call."
        )
    logger.info("gemini upload ready: %s (%s)", uploaded.name, uploaded.mime_type)
    return uploaded


def _state_name(file: types.File) -> str:
    """File state as a plain string — the SDK returns an enum, mocks and JSON return strings."""
    state = file.state
    if state is None:
        return "UNKNOWN"
    return str(getattr(state, "name", state))


def _delete_upload(client: genai.Client, uploaded: types.File) -> None:
    """Delete the File API handle.

    Deliberate cleanup rather than letting the 48h expiry mop up: a debugging loop over one clip
    would otherwise leave an upload behind on every run.
    """
    try:
        client.files.delete(name=str(uploaded.name))
        logger.info("gemini upload deleted: %s", uploaded.name)
    except Exception as exc:  # noqa: BLE001 - cleanup must never mask the real result
        logger.warning(
            "could not delete gemini upload %s (%s); it expires in 48h", uploaded.name, exc
        )


def is_rate_limited(exc: BaseException) -> bool:
    """True for HTTP 429 — the only status worth retrying on the free tier.

    Public so ``elvideo.eval.alignment`` can build its own retryer over the same predicate and the
    same backoff constants without importing a private helper. The grading call is a separate
    consumer of the same key and must not go through :func:`_generate_with_backoff`, which
    increments the one-call-per-video counter.
    """
    return isinstance(exc, genai_errors.APIError) and exc.code == 429


def _with_backoff(label: str, operation: Callable[[], _T]) -> _T:
    """Run ``operation``, retrying only on HTTP 429 with exponential backoff.

    Built per call from the module constants rather than as a decorator, so the backoff can be
    turned down in tests without patching a captured closure.

    Both API-touching steps go through this, not just the generate call: **a depleted or
    rate-limited key trips at the File API upload first**, and without this an SDK ``ClientError``
    traceback would surface instead of the actionable message.

    Raises:
        RuntimeError: If the rate limit survives :data:`RETRY_MAX_ATTEMPTS` attempts.
    """
    retryer = Retrying(
        retry=retry_if_exception(is_rate_limited),
        wait=wait_exponential(multiplier=RETRY_WAIT_MULTIPLIER_S, max=RETRY_WAIT_MAX_S),
        stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
        reraise=False,
    )
    try:
        return retryer(operation)
    except RetryError as exc:
        detail = exc.last_attempt.exception()
        raise RuntimeError(
            f"Gemini returned HTTP 429 on all {RETRY_MAX_ATTEMPTS} attempts of {label}. The free "
            f"tier is 10 RPM / 250K TPM - wait a minute and rerun, or check nothing else is using "
            f"this key. If the message below mentions depleted credits, the key's project is not "
            f"on the free tier and no amount of waiting will help: {detail}"
        ) from exc


def _generate_with_backoff(
    client: genai.Client,
    contents: types.Content,
    config: types.GenerateContentConfig,
    fps: float,
    media_resolution: MediaResolution,
) -> types.GenerateContentResponse:
    """Issue the one ``generate_content`` request, retrying only on 429.

    The **request** counter increments once, here, before any attempt; the **attempt** counter
    increments inside the retried closure. Keeping them apart is what stops a 429 the backoff
    successfully absorbed from tripping ``build.py``'s one-call assertion and discarding a run that
    already worked — see ``tasks/T013-retry-vs-one-call-counter.md``.

    Raises:
        RuntimeError: If the rate limit survives :data:`RETRY_MAX_ATTEMPTS` attempts.
    """
    global _calls

    _calls += 1
    request_no = _calls
    logger.info(
        "gemini generate_content request #%d model=%s fps=%s media_resolution=%s prompt=%s",
        request_no,
        MODEL,
        fps,
        media_resolution,
        PROMPT_VERSION,
    )

    attempts_here = 0

    def _once() -> types.GenerateContentResponse:
        global _attempts
        nonlocal attempts_here

        _attempts += 1
        attempts_here += 1
        if attempts_here > 1:
            # Louder than the request line above: a retry is invisible in the artifact but costs
            # a second unit of the resource that actually binds (D-031).
            logger.warning(
                "gemini generate_content request #%d: transport attempt %d (429 retry, "
                "D-020 backoff) - this consumes another of the 20 daily free-tier requests",
                request_no,
                attempts_here,
            )
        return client.models.generate_content(model=MODEL, contents=contents, config=config)

    return _with_backoff("generate_content", _once)


def _parse(
    response: types.GenerateContentResponse,
    shots: Sequence[Shot] | None,
    *,
    with_hints: bool,
) -> list[ShotUnderstanding]:
    """Validate the JSON body into ``ShotUnderstanding`` and check it against the real shot list.

    Raises:
        RuntimeError: If the body is missing, is not the expected JSON shape, is empty, or carries
            a ``shot_index`` that is out of range or duplicated. All of those are loud on purpose:
            a silently dropped or misnumbered entry produces an index with captions on the wrong
            shots and no error anywhere (D-010).
    """
    text = response.text
    if not text or not text.strip():
        raise RuntimeError(
            f"Gemini returned no text for the understanding call "
            f"(finish reason: {_finish_reason(response)}). Nothing to parse."
        )

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Gemini response is not valid JSON despite response_mime_type=application/json: "
            f"{exc}. First 200 chars: {text[:200]!r}"
        ) from exc

    if not isinstance(payload, list):
        raise RuntimeError(
            f"Gemini response is {type(payload).__name__}, expected a JSON array of shot "
            f"judgments. First 200 chars: {text[:200]!r}"
        )
    if not payload:
        raise RuntimeError("Gemini returned an empty shot list - no judgment to merge into shots.")

    understandings: list[ShotUnderstanding] = []
    for i, raw in enumerate(payload):
        if not isinstance(raw, dict):
            raise RuntimeError(
                f"entry {i} of the Gemini response is {type(raw).__name__}, not an object"
            )
        try:
            understandings.append(_to_understanding(raw, with_hints=with_hints))
        except ValidationError as exc:
            raise RuntimeError(
                f"entry {i} of the Gemini response does not match ShotUnderstanding: {exc}"
            ) from exc

    _check_indices(understandings, shots)
    understandings.sort(key=lambda u: u.shot_index)
    _check_hints(understandings, shots)
    return understandings


def _to_understanding(raw: dict[str, Any], *, with_hints: bool) -> ShotUnderstanding:
    """Convert one wire object to a :class:`ShotUnderstanding`, dropping unknown keys.

    ``ShotUnderstanding`` forbids extras, which is right for our own code but wrong to enforce
    against a model that may add a field; the fields we asked for are the fields we keep.
    """
    fields = {
        "shot_index": raw.get("shot_index"),
        "caption": raw.get("caption"),
        "editorial_score": raw.get("editorial_score"),
        "moment_reason": raw.get("moment_reason"),
        "tags": raw.get("tags") or [],
    }
    if with_hints:
        fields["t_start_hint"] = raw.get("t_start_hint")
        fields["t_end_hint"] = raw.get("t_end_hint")
    return ShotUnderstanding.model_validate(fields)


def _check_indices(
    understandings: Sequence[ShotUnderstanding], shots: Sequence[Shot] | None
) -> None:
    """Fail loudly on a duplicated or out-of-range ``shot_index``.

    Missing shots are a warning, not an error — T007 leaves those shots with an empty caption,
    which is recoverable and visible. A wrong index is not: it silently attributes a caption to
    footage it does not describe.
    """
    seen: set[int] = set()
    duplicates: set[int] = set()
    for u in understandings:
        if u.shot_index in seen:
            duplicates.add(u.shot_index)
        seen.add(u.shot_index)
    if duplicates:
        raise RuntimeError(
            f"Gemini returned duplicate shot_index values {sorted(duplicates)}; alignment in T007 "
            f"would be ambiguous."
        )

    if shots is None:
        return

    out_of_range = sorted(u.shot_index for u in understandings if u.shot_index >= len(shots))
    if out_of_range:
        raise RuntimeError(
            f"Gemini returned shot_index {out_of_range} but only {len(shots)} shots were given "
            f"(valid range 0-{len(shots) - 1}). Captions would land on the wrong shots."
        )

    missing = len(shots) - len(understandings)
    if missing > 0:
        logger.warning(
            "gemini judged %d of %d shots - %d shot(s) will have no caption",
            len(understandings),
            len(shots),
            missing,
        )


def hint_drift(
    understandings: Sequence[ShotUnderstanding], shots: Sequence[Shot]
) -> list[int]:
    """Shot indices whose reported hint falls outside the boundary they were filed against.

    The one signal that distinguishes *the model looked in the wrong place* from *the model looked
    in the right place and described it badly* — the two are indistinguishable in a caption, which
    is why D-027 survived every gate in the repo. Since ``p3`` the model reports, per shot, the
    timestamps of the moment it just described; if that moment is not inside the interval the shot
    was listed under, the judgment is filed against footage it did not watch.

    Tolerant by design: Gemini's timestamps are second-granular (hard constraint 4) and the median
    shot on the test clip is 2.68s, so a hint is counted as drifted only when its midpoint lands
    outside the shot's interval widened by :data:`HINT_TOLERANCE_S` at each end. That keeps
    rounding out of the number and leaves the +3 / -15 shot displacements D-027 measured firmly in.

    Args:
        understandings: Parsed judgments, hints populated (``p3`` and later).
        shots: The boundaries those judgments were filed against.

    Returns:
        The drifted ``shot_index`` values, ascending. Empty when every judgment lands inside the
        shot it claims — or when no hints were returned at all, which is why the caller logs the
        denominator too.
    """
    drifted: list[int] = []
    for u in understandings:
        if u.t_start_hint is None or u.t_end_hint is None:
            continue
        if not 0 <= u.shot_index < len(shots):
            continue
        shot = shots[u.shot_index]
        midpoint = (u.t_start_hint + u.t_end_hint) / 2
        if not (
            shot.t_start - HINT_TOLERANCE_S <= midpoint <= shot.t_end + HINT_TOLERANCE_S
        ):
            drifted.append(u.shot_index)
    return sorted(drifted)


def _check_hints(understandings: Sequence[ShotUnderstanding], shots: Sequence[Shot] | None) -> None:
    """Log how far the model's own account of where it looked diverges from where we filed it.

    A warning, not an exception. A drifted hint means the caption is untrustworthy, but the run
    still produced a schema-valid index and the operator is better served by a number and a
    recoverable artifact than by a crash — the alternative is a pipeline that fails a 4-minute run
    on the last stage. :func:`hint_drift` is public so a caller that wants to be stricter can be.
    """
    if shots is None:
        return
    hinted = [u for u in understandings if u.t_start_hint is not None]
    if not hinted:
        logger.warning(
            "gemini returned no timestamp hints - alignment cannot be checked (prompt %s)",
            PROMPT_VERSION,
        )
        return

    drifted = hint_drift(understandings, shots)
    logger.info(
        "gemini hint alignment: %d of %d judgments land inside the shot they were filed against "
        "(tolerance +/-%.1fs)",
        len(hinted) - len(drifted),
        len(hinted),
        HINT_TOLERANCE_S,
    )
    if drifted and len(drifted) > HINT_DRIFT_WARN_FRACTION * len(hinted):
        logger.warning(
            "%d of %d judgments describe a moment outside their own shot - captions are attached "
            "to footage the model did not watch there (D-027). First few: %s",
            len(drifted),
            len(hinted),
            drifted[:10],
        )


def _finish_reason(response: types.GenerateContentResponse) -> str:
    """Best-effort finish reason for error messages (``MAX_TOKENS``, ``SAFETY``, …)."""
    candidates = response.candidates or []
    if not candidates or candidates[0].finish_reason is None:
        return "unknown"
    return str(getattr(candidates[0].finish_reason, "name", candidates[0].finish_reason))


def _log_usage(
    response: types.GenerateContentResponse,
    understandings: Sequence[ShotUnderstanding],
    upload_s: float,
    call_s: float,
    total_s: float,
) -> None:
    """Log token usage, timing, and the score distribution.

    Three things T009 needs and cannot reconstruct afterwards: the real token count against the
    ~30K target, the per-stage timing the <5 min budget is measured in, and whether
    ``editorial_score`` actually spread. A model that scores everything 0.8 is a prompt bug, so the
    spread is logged every run rather than eyeballed once.
    """
    usage = response.usage_metadata
    prompt_tokens = getattr(usage, "prompt_token_count", None) if usage else None
    output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
    thoughts_tokens = getattr(usage, "thoughts_token_count", None) if usage else None
    total_tokens = getattr(usage, "total_token_count", None) if usage else None

    logger.info(
        "gemini tokens: prompt=%s output=%s thoughts=%s total=%s (target ~30K/10min)",
        prompt_tokens,
        output_tokens,
        thoughts_tokens,
        total_tokens,
    )

    scores = [u.editorial_score for u in understandings]
    distinct = len({round(s, 2) for s in scores})
    stdev = statistics.pstdev(scores) if len(scores) > 1 else 0.0
    logger.info(
        # ASCII only: these messages reach a cp1252 console through the CLI's rich handler,
        # where an em dash renders as a replacement glyph. Same trap as the help strings.
        "gemini understanding: %d shots in %.1fs (upload %.1fs, call %.1fs) | "
        "editorial_score min=%.2f median=%.2f max=%.2f stdev=%.3f distinct@2dp=%d/%d",
        len(understandings),
        total_s,
        upload_s,
        call_s,
        min(scores),
        statistics.median(scores),
        max(scores),
        stdev,
        distinct,
        len(scores),
    )
    if stdev < 0.05:
        logger.warning(
            "editorial_score barely varies (stdev %.3f, %d distinct values) - that is a prompt "
            "bug, not a verdict on the footage. See PROMPT_VERSION %s.",
            stdev,
            distinct,
            PROMPT_VERSION,
        )

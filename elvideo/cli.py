"""CLI entrypoint — ``python -m elvideo index in.mp4``.

One command, one file, no UI. See ``docs/IDEA.md`` § *Scope* ("CLI on one file") and
§ *Definition of done*, whose first line is this exact invocation.

**Deliberately thin.** Argument parsing, ``.env`` loading, output formatting and exit codes live
here; everything real lives in :func:`elvideo.index.build.build_index`, which has to stay callable
without inheriting our argument parsing. If logic starts accumulating in this module it is in the
wrong file.

Two traps this module was already bitten by — do not reintroduce either:

* Typer collapses a **single-command** app and drops the subcommand name, which turns
  ``python -m elvideo index in.mp4`` into a parse error. The empty :func:`_root` callback forces
  multi-command mode.
* **Anything Typer or rich prints must be ASCII.** The Windows console is cp1252 and a single
  ``<=`` glyph crashed ``--help`` with ``UnicodeEncodeError``. Docstrings that Typer does *not*
  print (this one, ``_fail``) may use whatever they like; ``help=`` strings may not.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import NoReturn

import typer
from dotenv import load_dotenv
from jsonschema.exceptions import ValidationError
from rich.console import Console
from rich.logging import RichHandler

from elvideo.index import gemini, scenes
from elvideo.index.build import OUTPUT_FILENAME, build_index
from elvideo.index.gemini import DEFAULT_MEDIA_RESOLUTION, DEFAULT_SAMPLE_FPS

__all__ = ["EXIT_FAILURE", "MediaResolutionChoice", "app", "index", "main"]

EXIT_FAILURE = 1
"""Exit code for every run that did not write a valid index.

One code for all of them, deliberately: the criterion is *non-zero*, and the message on stderr —
not an exit code the caller has to look up — is what tells you which failure it was. Typer's own
usage errors (an unknown ``--media-resolution``, a missing argument) exit 2 on their own.
"""

# Not printed by Typer, so highlighting and markup would only mangle Windows paths and messages
# that happen to contain square brackets.
_out = Console(markup=False, highlight=False)
_err = Console(stderr=True, markup=False, highlight=False)


class MediaResolutionChoice(StrEnum):
    """The three values the API accepts, as a Typer choice.

    An enum rather than a validated string so a bad value dies **in the parser**, with the three
    valid ones listed, instead of travelling to the API as an invalid enum name. Mirrors
    ``MediaResolution`` in ``elvideo/schema/models.py``, which is the source of truth.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    # Keep help strings ASCII-only: the Windows console is cp1252 and a stray "<=" glyph
    # crashes --help with UnicodeEncodeError.
    help="Turn one 10-min-or-shorter video into a shot-level text index (footage_index.json).",
)


@app.callback()
def _root() -> None:
    """Keep Typer in multi-command mode.

    With a single registered command Typer collapses the group and the subcommand name
    disappears — which would make the DoD's ``python -m elvideo index in.mp4`` invalid. This
    callback prevents that.
    """


@app.command(
    help=(
        "Build footage_index.json for one video.\n\n"
        "Runs probe, shot detection, transcription, ONE Gemini understanding call, and per-shot "
        "quality scoring; validates the result against the shared schema and writes it to "
        "WORK_DIR/footage_index.json. Per-stage timing is printed as it goes.\n\n"
        "Needs GEMINI_API_KEY, read from the environment or a .env file in the working directory."
    )
)
def index(
    video: str = typer.Argument(..., help="Path to the source video (10 min or shorter)."),
    work_dir: str = typer.Option("work", "--work-dir", help="Where keyframes and output go."),
    fps: float = typer.Option(
        DEFAULT_SAMPLE_FPS,
        "--fps",
        help=(
            "Frames per second sampled for the Gemini call, and the main cost/detail knob. "
            "0.5 (one frame every 2s) suits most footage. Talking-head or a locked-off camera: "
            "0.2-0.5, since little changes between frames. Action, sport, fast cuts or handheld: "
            "1-2, or brief moments fall between samples. Cost scales with it - doubling fps "
            "roughly doubles the frame tokens. Per-video: pass it per run, do not change the "
            "default to fix one clip."
        ),
    ),
    media_resolution: MediaResolutionChoice = typer.Option(
        # The pinned constant itself, not a retyped "low": the CLI default cannot drift from
        # gemini.DEFAULT_MEDIA_RESOLUTION (D-019). Click casts it to the enum member.
        DEFAULT_MEDIA_RESOLUTION,
        "--media-resolution",
        help=(
            "Token cost per sampled frame: low=66, medium/high=258. Keep 'low' unless the shots "
            "turn on small on-screen text; it is ~3x cheaper and free-tier friendly."
        ),
    ),
    threshold: float = typer.Option(
        scenes.DEFAULT_THRESHOLD,
        "--threshold",
        help=(
            "PySceneDetect ContentDetector threshold. Lower cuts more often, higher cuts less. "
            "Per-video, like --fps; the value used is recorded in index_meta.scene_threshold."
        ),
    ),
) -> None:
    """Build ``footage_index.json`` for one video.

    A wrapper over :func:`elvideo.index.build.build_index` and nothing more. The two things it
    does before handing over are both about failing early rather than late: ``.env`` is loaded and
    the API key is checked *before* the ~2.5-minute transcription stage, and ``work_dir`` is
    created so an unwritable path is caught at second zero rather than at the write.

    ``--threshold`` is exposed even though ``tasks/T008-cli.md`` does not list it: D-012 calls the
    detector threshold a per-video knob, and a knob no user can reach is not a knob. See
    ``state/decisions-log.md`` D-026.

    Raises:
        typer.Exit: :data:`EXIT_FAILURE` on a missing video, a missing ``GEMINI_API_KEY``, a
            pipeline error, or a schema validation failure. Never exits 0 without a written index.
    """
    _configure_logging()
    load_dotenv()

    if not Path(video).is_file():
        _fail(
            f"video not found: {video}",
            "Pass a path to an existing file, e.g. python -m elvideo index in.mp4",
        )

    try:
        gemini.check_api_key()
    except RuntimeError as exc:
        _fail(str(exc))

    out_dir = Path(work_dir)
    try:
        # build_index creates work_dir at write time and quality.score_shot creates keyframes/,
        # but both happen minutes in. Making them now turns "unwritable --work-dir" into an
        # immediate error instead of one that lands after the whole pipeline has run.
        (out_dir / "keyframes").mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _fail(f"cannot create work dir {work_dir}: {exc}", "Pick a writable path for --work-dir.")

    try:
        doc = build_index(
            video,
            work_dir,
            fps,
            # .value, not the member: pydantic would otherwise carry a MediaResolutionChoice into
            # index_meta and serialize the enum's repr instead of "low". mypy narrows this to the
            # MediaResolution literal on its own - the enum's values are exactly those three.
            media_resolution.value,
            threshold=threshold,
        )
    except FileNotFoundError as exc:
        # Reachable despite the check above if the file disappears mid-run.
        _fail(str(exc), "Pass a path to an existing file.")
    except ValidationError as exc:
        _fail(
            f"the assembled index violates the shared schema: {exc.message}",
            "Nothing was written. This is a bug in the pipeline, not in your input - report the "
            "field above with the video that produced it.",
        )
    except RuntimeError as exc:
        _fail(str(exc))
    except ValueError as exc:
        _fail(
            str(exc),
            "The model did not answer against the shot list it was given. Re-run; if it repeats, "
            "try a different --fps.",
        )

    _out.print(
        f"wrote {out_dir / OUTPUT_FILENAME}  "
        f"{len(doc['shots'])} shots  "
        f"{len(doc['words'])} words  "
        f"{sum(1 for shot in doc['shots'] if shot['is_candidate'])} candidates"
    )


def _configure_logging() -> None:
    """Route the pipeline's per-stage log lines through ``rich``.

    ``build_index`` already emits one line per stage plus a total via ``logging`` (the <5 min
    budget is a per-stage claim — see ``docs/IDEA.md`` § *Definition of done*), so the CLI's job is
    to render them, not to re-time anything.

    Root stays at WARNING and only ``elvideo`` is raised to INFO: torch, whisperx and
    google-genai are all chatty at INFO and would bury the eight lines that matter. The handler
    filter is the second half of that — a library that sets a level on **its own** logger
    (lightning does, on import) bypasses the root level and prints anyway. Third-party WARNING and
    above still gets through; the goal is a readable run, not a silent one.

    Nothing here can filter the ffmpeg/h264 chatter: native code writes it straight to the
    process's stderr, below Python's logging altogether.
    """
    handler = RichHandler(console=_out, show_path=False, markup=False, rich_tracebacks=False)
    handler.addFilter(
        lambda record: record.levelno >= logging.WARNING or record.name.startswith("elvideo")
    )
    logging.basicConfig(
        level=logging.WARNING,
        format="%(message)s",
        datefmt="%H:%M:%S",
        handlers=[handler],
        force=True,
    )
    logging.getLogger("elvideo").setLevel(logging.INFO)


def _fail(problem: str, fix: str | None = None) -> NoReturn:
    """Print a one-line error naming the fix, then exit non-zero.

    Two lines, not a traceback: a stack trace tells a user what broke inside us, ``fix`` tells
    them what to do about it. See ``tasks/T008-cli.md`` — "error messages name the fix, not just
    the fault".
    """
    _err.print(f"error: {problem}", style="bold red")
    if fix is not None:
        _err.print(f"  fix: {fix}", style="yellow")
    raise typer.Exit(EXIT_FAILURE)


def main() -> None:
    """Module entrypoint. Invoked by ``elvideo/__main__.py``."""
    app()

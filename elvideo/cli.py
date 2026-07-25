"""CLI entrypoint — ``python -m elvideo index in.mp4``.

One command, one file, no UI. See ``docs/IDEA.md`` § *Scope* ("CLI on one file") and
§ *Definition of done*.
"""

from __future__ import annotations

import typer

from elvideo.index.gemini import DEFAULT_MEDIA_RESOLUTION, DEFAULT_SAMPLE_FPS

__all__ = ["app", "index", "main"]

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


@app.command()
def index(
    video: str = typer.Argument(..., help="Path to the source video (10 min or shorter)."),
    work_dir: str = typer.Option("work", "--work-dir", help="Where keyframes and output go."),
    fps: float = typer.Option(
        DEFAULT_SAMPLE_FPS,
        "--fps",
        help=(
            "Frames/sec sampled for the Gemini call. Per-video knob: raise to 1-2 for "
            "action-heavy footage, lower for talking-head."
        ),
    ),
    media_resolution: str = typer.Option(
        DEFAULT_MEDIA_RESOLUTION,
        "--media-resolution",
        help="Token cost per frame. 'low' is 66 tok/frame vs 258 - keep it unless you must.",
    ),
) -> None:
    """Build ``footage_index.json`` for one video.

    Runs probe, shot detection, transcription, a single Gemini understanding call, and
    per-shot quality scoring; then validates the result against the shared schema and writes it
    to ``{work_dir}/footage_index.json``. Per-stage timing is printed.

    Raises:
        typer.Exit: Non-zero on a missing file, a missing ``GEMINI_API_KEY``, or a schema
            validation failure.
    """
    raise NotImplementedError("see tasks/T008-cli.md")


def main() -> None:
    """Module entrypoint. Invoked by ``elvideo/__main__.py``."""
    app()

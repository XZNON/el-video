"""CLI tests — the argument surface and the exit-code map.

``build_index`` is mocked in every test here. That is the point of the split: the pipeline is
tested in ``tests/test_build.py``, and this module tests only what ``cli.py`` owns — which options
exist, what they forward, what gets created before the pipeline runs, and which exception becomes
which exit code. A CLI test that ran the real pipeline would take three minutes and tell us
nothing about the CLI.

Three things here are regression guards rather than feature tests, and they are marked as such:
the Typer single-command collapse, the cp1252 help-string trap, and "no exit 0 without a written
index".

See ``tasks/T008-cli.md``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import click
import pytest
import typer.main
from jsonschema.exceptions import ValidationError
from typer.testing import CliRunner

from elvideo import cli
from elvideo.cli import EXIT_FAILURE, app
from elvideo.index import gemini, scenes
from elvideo.index.gemini import DEFAULT_MEDIA_RESOLUTION, DEFAULT_SAMPLE_FPS

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plant a key and stop ``.env`` from being read.

    The repo has a real ``.env`` with a working key (D-021). Without this the "missing key" test
    would pass or fail depending on the developer's filesystem.
    """
    monkeypatch.setattr(cli, "load_dotenv", lambda *a, **k: False)
    # gemini._api_key() calls load_dotenv() a second time, inside its own module.
    monkeypatch.setattr(gemini, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")


@pytest.fixture
def video(tmp_path: Path) -> Path:
    """An existing file. Nothing reads its bytes — ``build_index`` is mocked."""
    path = tmp_path / "in.mp4"
    path.write_bytes(b"not really an mp4")
    return path


class _Spy:
    """Stand-in for ``build_index`` that records its call and returns a minimal valid-shaped doc."""

    def __init__(self, shots: int = 2, words: int = 3) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.doc: dict[str, Any] = {
            "shots": [
                {"id": f"shot_{i:03d}", "is_candidate": i == 0, "editorial_score": 0.9 - 0.5 * i}
                for i in range(shots)
            ],
            "words": [{"w": "hello"} for _ in range(words)],
        }

    def __call__(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((args, kwargs))
        return self.doc


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> _Spy:
    """Replace ``build_index`` where ``cli`` looked it up."""
    spy = _Spy()
    monkeypatch.setattr(cli, "build_index", spy)
    return spy


def _raiser(exc: BaseException) -> Any:
    def _raise(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise exc

    return _raise


# --------------------------------------------------------------------------------------------
# The invocation itself — the two bootstrap traps
# --------------------------------------------------------------------------------------------


def test_index_is_a_named_subcommand(video: Path, spy: _Spy) -> None:
    """``python -m elvideo index in.mp4`` — the exact DoD invocation, not a collapsed one.

    Regression guard for the Typer single-command collapse: without the ``@app.callback()``,
    Typer drops the group and ``index`` parses as an unexpected extra argument.
    """
    result = runner.invoke(app, ["index", str(video)])

    assert result.exit_code == 0, result.output
    assert len(spy.calls) == 1


def test_video_without_the_subcommand_is_rejected(video: Path, spy: _Spy) -> None:
    """The other half of the same guard: the subcommand is required, not optional."""
    result = runner.invoke(app, [str(video)])

    assert result.exit_code != 0
    assert spy.calls == []


def _authored_help_texts() -> dict[str, str]:
    """Every help string this repo wrote, keyed by where it lives.

    Rich's own panel borders are excluded on purpose: rich downgrades them to ``+-`` when the
    stream is cp1252, so they are not what broke ``--help``. A ``<=`` we typed is.
    """
    group = cast(click.Group, typer.main.get_command(app))
    texts = {"app": group.help or ""}
    for name, command in group.commands.items():
        texts[name] = command.help or ""
        for param in command.params:
            texts[f"{name} {param.name}"] = getattr(param, "help", None) or ""
    return texts


@pytest.mark.parametrize("where", sorted(_authored_help_texts()))
def test_help_strings_are_ascii_only(where: str) -> None:
    """Regression guard for the cp1252 crash.

    A non-ASCII glyph in anything Typer prints raises ``UnicodeEncodeError`` when stdout is
    cp1252 — which is the Windows console, and any redirect to a file or pipe.
    """
    text = _authored_help_texts()[where]

    assert text.isascii(), f"non-ASCII in the help for {where}: {text!r}"


@pytest.mark.parametrize("argv", [["--help"], ["index", "--help"]])
def test_help_renders(argv: list[str]) -> None:
    result = runner.invoke(app, argv)

    assert result.exit_code == 0
    assert "index" in result.output


def test_help_explains_how_to_pick_fps() -> None:
    """``--fps`` help has to be enough on its own to choose a value.

    The criterion is that someone picks the right number for talking-head vs action footage
    without opening the spec, so both cases have to be named with numbers attached.
    """
    output = runner.invoke(app, ["index", "--help"]).output.lower()

    assert "--fps" in output
    assert "talking-head" in output
    assert "action" in output
    assert "1-2" in output


# --------------------------------------------------------------------------------------------
# What the options forward
# --------------------------------------------------------------------------------------------


def test_defaults_match_the_pinned_settings(video: Path, spy: _Spy) -> None:
    """No flags means the free-tier defaults: fps 0.5, media_resolution low, threshold 27."""
    result = runner.invoke(app, ["index", str(video)])

    assert result.exit_code == 0, result.output
    args, kwargs = spy.calls[0]
    assert args == (str(video), "work", DEFAULT_SAMPLE_FPS, DEFAULT_MEDIA_RESOLUTION)
    assert kwargs == {"threshold": scenes.DEFAULT_THRESHOLD}


def test_every_knob_is_forwarded(video: Path, spy: _Spy, tmp_path: Path) -> None:
    """The per-video knobs reach ``build_index`` unchanged — for this run only."""
    out = tmp_path / "elsewhere"
    result = runner.invoke(
        app,
        [
            "index",
            str(video),
            "--work-dir",
            str(out),
            "--fps",
            "2",
            "--media-resolution",
            "high",
            "--threshold",
            "20.5",
        ],
    )

    assert result.exit_code == 0, result.output
    args, kwargs = spy.calls[0]
    assert args == (str(video), str(out), 2.0, "high")
    assert kwargs == {"threshold": 20.5}


def test_fps_override_does_not_touch_the_default(video: Path, spy: _Spy) -> None:
    """"For that run only": the module constant is not rewritten by a flag."""
    runner.invoke(app, ["index", str(video), "--fps", "2"])

    assert DEFAULT_SAMPLE_FPS == 0.5
    runner.invoke(app, ["index", str(video)])
    assert spy.calls[1][0][2] == 0.5


def test_media_resolution_arrives_as_a_plain_string(video: Path, spy: _Spy) -> None:
    """Not the enum member.

    ``MediaResolutionChoice`` is a ``str`` subclass, so a leaked member would compare equal to
    "low" and pass every other assertion here — while serializing into ``index_meta`` as the
    enum's repr.
    """
    runner.invoke(app, ["index", str(video), "--media-resolution", "medium"])

    forwarded = spy.calls[0][0][3]
    assert type(forwarded) is str
    assert forwarded == "medium"


@pytest.mark.parametrize("value", ["low", "medium", "high"])
def test_media_resolution_accepts_the_three_api_values(
    value: str, video: Path, spy: _Spy
) -> None:
    result = runner.invoke(app, ["index", str(video), "--media-resolution", value])

    assert result.exit_code == 0, result.output
    assert spy.calls[0][0][3] == value


def test_bad_media_resolution_dies_in_the_parser(video: Path, spy: _Spy) -> None:
    """Rejected here, with the valid values named — never passed through to the API."""
    result = runner.invoke(app, ["index", str(video), "--media-resolution", "ultra"])

    assert result.exit_code != 0
    assert spy.calls == []
    message = result.output + (result.stderr or "")
    assert "ultra" in message
    for valid in ("low", "medium", "high"):
        assert valid in message


# --------------------------------------------------------------------------------------------
# work_dir
# --------------------------------------------------------------------------------------------


def test_work_dir_and_keyframes_are_created(video: Path, spy: _Spy, tmp_path: Path) -> None:
    """Both directories exist before the pipeline starts, not after the first write."""
    out = tmp_path / "nested" / "work"
    result = runner.invoke(app, ["index", str(video), "--work-dir", str(out)])

    assert result.exit_code == 0, result.output
    assert (out / "keyframes").is_dir()


def test_existing_work_dir_is_reused(video: Path, spy: _Spy, tmp_path: Path) -> None:
    """A second run does not blow away the first one's keyframes."""
    out = tmp_path / "work"
    (out / "keyframes").mkdir(parents=True)
    (out / "keyframes" / "shot_000.png").write_bytes(b"kept")

    result = runner.invoke(app, ["index", str(video), "--work-dir", str(out)])

    assert result.exit_code == 0, result.output
    assert (out / "keyframes" / "shot_000.png").read_bytes() == b"kept"


def test_unwritable_work_dir_fails_before_the_pipeline(
    video: Path, spy: _Spy, tmp_path: Path
) -> None:
    """An OS error on mkdir is a named failure, not a traceback three minutes in."""
    blocker = tmp_path / "work"
    blocker.write_text("this is a file, not a directory")

    result = runner.invoke(app, ["index", str(video), "--work-dir", str(blocker)])

    assert result.exit_code == EXIT_FAILURE
    assert spy.calls == []
    assert "--work-dir" in result.stderr


# --------------------------------------------------------------------------------------------
# Exit codes — the map from build_index's Raises: block
# --------------------------------------------------------------------------------------------


def test_missing_video_exits_non_zero_and_names_the_fix(tmp_path: Path, spy: _Spy) -> None:
    result = runner.invoke(app, ["index", str(tmp_path / "nope.mp4")])

    assert result.exit_code == EXIT_FAILURE
    assert spy.calls == []
    assert "nope.mp4" in result.stderr
    assert "fix:" in result.stderr


def test_missing_api_key_exits_before_transcription(
    video: Path, spy: _Spy, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The expensive stages never run, and the message says where to put the key.

    ``build_index`` would raise the same ``RuntimeError`` from inside the understanding stage —
    but only after probe, shots and WhisperX have burned ~2.5 minutes.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = runner.invoke(app, ["index", str(video)])

    assert result.exit_code == EXIT_FAILURE
    assert spy.calls == []
    assert "GEMINI_API_KEY" in result.stderr
    assert ".env" in result.stderr


def test_blank_api_key_counts_as_missing(
    video: Path, spy: _Spy, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "   ")

    result = runner.invoke(app, ["index", str(video)])

    assert result.exit_code == EXIT_FAILURE
    assert spy.calls == []


def test_schema_validation_failure_exits_non_zero(
    video: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The worst outcome is a silent 0 on a broken index, so this one is load-bearing."""
    monkeypatch.setattr(
        cli, "build_index", _raiser(ValidationError("'t_end' is a required property"))
    )

    result = runner.invoke(app, ["index", str(video)])

    assert result.exit_code == EXIT_FAILURE
    assert "t_end" in result.stderr
    assert "Nothing was written" in result.stderr


@pytest.mark.parametrize(
    ("exc", "needle"),
    [
        (FileNotFoundError("video not found: gone.mp4"), "gone.mp4"),
        (RuntimeError("expected exactly 1 Gemini generate_content call, counted 3"), "counted 3"),
        (RuntimeError("GEMINI_API_KEY is not set. Copy .env.example"), ".env.example"),
        (ValueError("shot_index 400 is outside the detected range 0-116"), "shot_index 400"),
    ],
)
def test_pipeline_errors_map_to_a_named_non_zero_exit(
    exc: BaseException, needle: str, video: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every exception ``build_index`` documents becomes exit 1 plus its own message."""
    monkeypatch.setattr(cli, "build_index", _raiser(exc))

    result = runner.invoke(app, ["index", str(video)])

    assert result.exit_code == EXIT_FAILURE
    assert needle in result.stderr
    assert not result.stderr.startswith("Traceback")


def test_errors_go_to_stderr_not_stdout(video: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """So `python -m elvideo index x.mp4 > out.txt` still shows the failure on the terminal."""
    monkeypatch.setattr(cli, "build_index", _raiser(RuntimeError("boom")))

    result = runner.invoke(app, ["index", str(video)])

    assert "boom" in result.stderr
    # result.output mixes both streams (click 8.2+); result.stdout is the redirected one.
    assert "boom" not in result.stdout


# --------------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------------


def test_per_stage_timing_is_printed(
    video: Path, spy: _Spy, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The <5 min budget is a per-stage claim, so the stage lines have to reach the terminal.

    ``build_index`` logs them through ``logging``; the CLI's job is to have a handler attached and
    ``elvideo`` at INFO. Emitting from the real logger name is what proves the wiring.
    """

    def _logging_build(*args: Any, **kwargs: Any) -> dict[str, Any]:
        logging.getLogger("elvideo.index.build").info("stage %-10s %7.2fs", "transcript", 102.75)
        return spy(*args, **kwargs)

    monkeypatch.setattr(cli, "build_index", _logging_build)

    result = runner.invoke(app, ["index", str(video)])

    assert result.exit_code == 0
    assert "transcript" in result.output
    assert "102.75" in result.output


def test_noisy_third_party_logs_are_not_printed(
    video: Path, spy: _Spy, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Third-party INFO is dropped even when the library sets its own level.

    Both halves matter, and the second is the one the first live run caught: root at WARNING is
    not enough, because ``lightning`` raises the level on its own logger at import time and its
    records then reach the root handler regardless.
    """

    def _noisy_build(*args: Any, **kwargs: Any) -> dict[str, Any]:
        logging.getLogger("torch.some.module").info("inherits root, should be dropped")
        opinionated = logging.getLogger("lightning.pytorch.utilities")
        opinionated.setLevel(logging.INFO)
        opinionated.info("sets its own level, should still be dropped")
        return spy(*args, **kwargs)

    monkeypatch.setattr(cli, "build_index", _noisy_build)

    result = runner.invoke(app, ["index", str(video)])

    assert "should be dropped" not in result.output


def test_third_party_warnings_still_reach_the_user(
    video: Path, spy: _Spy, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The filter quiets INFO, not everything. A library warning is worth seeing."""

    def _warning_build(*args: Any, **kwargs: Any) -> dict[str, Any]:
        logging.getLogger("whisperx.asr").warning("model fell back to cpu")
        return spy(*args, **kwargs)

    monkeypatch.setattr(cli, "build_index", _warning_build)

    result = runner.invoke(app, ["index", str(video)])

    assert "model fell back to cpu" in result.output


def test_success_reports_what_was_written(video: Path, spy: _Spy, tmp_path: Path) -> None:
    out = tmp_path / "work"
    result = runner.invoke(app, ["index", str(video), "--work-dir", str(out)])

    assert result.exit_code == 0
    assert "footage_index.json" in result.output
    assert "2 shots" in result.output
    assert "3 words" in result.output
    assert "1 candidates" in result.output

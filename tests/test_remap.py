"""Tests for T012 — ``elvideo.eval.remap``.

No Gemini call is involved: the remap is pure arithmetic over two shot lists. What is worth
asserting is that it cannot quietly produce a number on a denominator nobody stated — merges are
collapsed rather than double-counted, the changed denominator is written into the sample it emits,
and a sampled id that is not in the old index is an error rather than a silently dropped row.

See ``tasks/T012-coarser-intervals.md`` and ``state/decisions-log.md`` D-033.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from elvideo.eval.alignment import AlignmentSample, SampleShot
from elvideo.eval.remap import load_shots, remap_sample, shot_at
from elvideo.schema.models import FootageIndex, IndexMeta, Shot, VideoMeta


def _index(shots: list[Shot], *, threshold: float = 27.0) -> FootageIndex:
    return FootageIndex(
        video=VideoMeta(path="in.mp4", duration_s=20.0, fps=25.0, w=1280, h=720),
        index_meta=IndexMeta(
            path_variant="gemini",
            model="gemini-3.5-flash",
            media_resolution="low",
            sample_fps=0.5,
            scene_detector="ContentDetector",
            scene_threshold=threshold,
        ),
        shots=shots,
        words=[],
    )


def _fine() -> list[Shot]:
    """Ten 2s shots, ``shot_000`` … ``shot_009``. The 'threshold 27' side."""
    return [Shot(id=f"shot_{n:03d}", t_start=n * 2.0, t_end=n * 2.0 + 2.0) for n in range(10)]


def _coarse() -> list[Shot]:
    """Five 4s shots — every adjacent pair of :func:`_fine` merged."""
    return [Shot(id=f"shot_{n:03d}", t_start=n * 4.0, t_end=n * 4.0 + 4.0) for n in range(5)]


def _sample(ids: list[str]) -> AlignmentSample:
    return AlignmentSample(
        video="in.mp4",
        n=len(ids),
        rule="test",
        source="test",
        keyframe_pattern="work/keyframes/{shot_id}.png",
        baseline={},
        shots=[SampleShot(shot_id=i, t009_verdict="mismatch") for i in ids],
    )


@pytest.fixture
def old_index(tmp_path: Path) -> Path:
    path = tmp_path / "footage_index.json"
    path.write_text(_index(_fine()).model_dump_json(), encoding="utf-8")
    return path


def test_maps_by_timestamp_not_by_id(old_index: Path) -> None:
    """``shot_004`` (8-10s) lands in the coarse shot covering 8-12s, which is ``shot_002``."""
    result = remap_sample(old_index, _coarse(), new_threshold=55.0, sample=_sample(["shot_004"]))

    assert [r.new_shot_id for r in result.rows] == ["shot_002"]
    assert result.rows[0].old_shot_ids == ["shot_004"]
    assert result.rows[0].old_midpoints_s == [9.0]
    assert not result.rows[0].collided


def test_merged_neighbours_collapse_to_one_row(old_index: Path) -> None:
    """Two sampled shots inside one coarse shot are graded once, not twice."""
    result = remap_sample(
        old_index, _coarse(), new_threshold=55.0, sample=_sample(["shot_000", "shot_001"])
    )

    assert result.n_old == 2
    assert result.n_new == 1
    assert result.rows[0].new_shot_id == "shot_000"
    assert result.rows[0].old_shot_ids == ["shot_000", "shot_001"]
    assert result.rows[0].collided
    assert result.collisions == result.rows


def test_denominator_is_carried_into_the_emitted_sample(old_index: Path) -> None:
    """A number produced from this sample cannot be quoted without its denominator attached."""
    result = remap_sample(
        old_index,
        _coarse(),
        new_threshold=55.0,
        sample=_sample(["shot_000", "shot_001", "shot_004"]),
    )
    emitted = result.to_sample()

    assert result.n_new == 2
    assert emitted.n == 2
    assert len(emitted.shots) == 2
    assert "DENOMINATOR IS 2, NOT 3" in emitted.rule
    assert emitted.baseline["n_this_sample"] == 2


def test_carried_verdict_comes_from_the_nearest_midpoint(old_index: Path) -> None:
    """When merged shots disagree, the verdict of the one nearest the new midpoint is carried."""
    sample = AlignmentSample(
        video="in.mp4",
        n=2,
        rule="test",
        source="test",
        keyframe_pattern="work/keyframes/{shot_id}.png",
        baseline={},
        shots=[
            SampleShot(shot_id="shot_000", t009_verdict="match"),
            SampleShot(shot_id="shot_001", t009_verdict="mismatch"),
        ],
    )
    # Coarse shot_000 spans 0-4s, midpoint 2.0. shot_000's midpoint is 1.0, shot_001's is 3.0 -
    # equidistant, so min() keeps the first. Shift the window to break the tie deliberately.
    coarse = [
        Shot(id="shot_000", t_start=0.0, t_end=5.0),
        Shot(id="shot_001", t_start=5.0, t_end=20.0),
    ]
    result = remap_sample(old_index, coarse, new_threshold=55.0, sample=sample)

    assert result.rows[0].collided
    assert result.rows[0].carried_verdict == "mismatch"  # midpoint 2.5 is nearer 3.0 than 1.0


def test_unknown_sampled_id_is_an_error(old_index: Path) -> None:
    with pytest.raises(ValueError, match="absent from"):
        remap_sample(old_index, _coarse(), new_threshold=55.0, sample=_sample(["shot_099"]))


def test_empty_new_shot_list_is_an_error(old_index: Path) -> None:
    with pytest.raises(ValueError, match="nothing to remap onto"):
        remap_sample(old_index, [], new_threshold=55.0, sample=_sample(["shot_000"]))


def test_load_shots_reads_the_recorded_threshold(old_index: Path) -> None:
    """D-013 shipped ``scene_threshold`` so a written index records how it was cut."""
    shots, threshold = load_shots(old_index)

    assert threshold == 27.0
    assert len(shots) == 10


def test_load_shots_rejects_a_missing_index(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_shots(tmp_path / "nope.json")


def test_shot_at_is_half_open(old_index: Path) -> None:
    """``t_start <= t < t_end`` — a boundary instant belongs to the shot it starts."""
    shots = _fine()

    assert shot_at(shots, 0.0).id == "shot_000"
    assert shot_at(shots, 1.999).id == "shot_000"
    assert shot_at(shots, 2.0).id == "shot_001"


def test_shot_at_clamps_past_the_final_boundary() -> None:
    """A midpoint can only land here through float rounding at the very end of the clip."""
    shots = _fine()

    assert shot_at(shots, 20.0).id == "shot_009"
    assert shot_at(shots, 999.0).id == "shot_009"


def test_shot_at_rejects_an_empty_list() -> None:
    with pytest.raises(ValueError, match="empty shot list"):
        shot_at([], 1.0)

"""Carry the frozen alignment sample across a change of shot boundaries.

``elvideo/eval/alignment_sample.json`` is keyed on ``shot_###`` ids, and those ids only mean
anything relative to one detector setting. T012 raises the ``ContentDetector`` threshold
(``state/decisions-log.md`` D-012, D-026) so adjacent micro-cuts merge, which renumbers every
shot after the first merge — ``shot_059`` at ``--threshold 40`` is not the footage ``shot_059``
was at ``--threshold 27``. Grading the new index under the old ids would silently compare
different footage and still produce a plausible number.

**The fix, per D-032 and T012's "two costs": map by *timestamp*, not by id.** Each sampled shot
is located by its midpoint in the old index, and that instant is looked up in the new shot list.
The sample then names the new shots that cover the same moments of ``in.mp4``.

**The denominator changes, and that is the point to report, not to hide.** Merging is
many-to-one: the frozen sample contains runs of adjacent shots (``shot_057`` … ``shot_061``), and
if a coarser detector merges them the 17 sampled moments land on fewer than 17 distinct new
shots. Grading one new shot five times would inflate whatever verdict it received, so collisions
are collapsed to one row and :attr:`RemapResult.n_new` reports the real denominator.

**``agreement_with_t009`` stops being calibration on collided rows.** The T009 human column was
recorded against the old boundaries; where several old shots with different verdicts merge into
one, no single human verdict applies. The nearest-midpoint verdict is carried so the field stays
populated, and :attr:`RemapRow.collided` marks every row where that number is no longer evidence.

See ``docs/IDEA.md`` § *Definition of done (s1)* for why boundaries are PySceneDetect's in both
indexes, and ``tasks/T012-coarser-intervals.md`` for the task this exists to serve.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, Field

from elvideo.eval.alignment import AlignmentSample, SampleShot, Verdict, load_sample
from elvideo.schema.models import FootageIndex, Shot

__all__ = [
    "RemapResult",
    "RemapRow",
    "load_shots",
    "main",
    "remap_sample",
    "shot_at",
]


class RemapRow(BaseModel):
    """One row of the remapped sample: a new shot, and the old shots that landed in it."""

    new_shot_id: str = Field(description="Id in the NEW shot list. Names its keyframe file too.")
    new_t_start: float = Field(ge=0, description="New shot start, seconds.")
    new_t_end: float = Field(gt=0, description="New shot end, seconds.")
    old_shot_ids: list[str] = Field(
        description="Sampled old ids whose midpoints fall in this new shot, in sample order."
    )
    old_midpoints_s: list[float] = Field(
        description="The instants actually carried over. This is the mapping key, not the ids."
    )
    carried_verdict: Verdict = Field(
        description="T009 verdict of the old shot whose midpoint is nearest this new shot's."
    )
    collided: bool = Field(
        description="True when more than one sampled old shot merged into this new shot."
    )


class RemapResult(BaseModel):
    """The remapped sample plus the provenance the report has to state."""

    old_index_path: str
    old_threshold: float | None = Field(
        default=None, description="Detector threshold of the old index, from index_meta if present."
    )
    new_threshold: float = Field(description="Detector threshold the new shot list was cut at.")
    n_old: int = Field(description="Rows in the frozen sample. 17.")
    n_new: int = Field(description="Distinct new shots the 17 moments land on. The denominator.")
    n_old_shots: int = Field(description="Total shots in the old index. 117 at threshold 27.")
    n_new_shots: int = Field(description="Total shots in the new list.")
    rows: list[RemapRow]

    @property
    def collisions(self) -> list[RemapRow]:
        """Rows where several sampled old shots merged into one new shot."""
        return [r for r in self.rows if r.collided]

    def to_sample(self) -> AlignmentSample:
        """Build the :class:`AlignmentSample` that :func:`elvideo.eval.alignment.grade_index` takes.

        The ``rule`` and ``source`` strings carry the changed denominator into the report, so a
        number produced from this sample cannot be quoted without the caveat attached.
        """
        merged = len(self.collisions)
        return AlignmentSample(
            video="in.mp4",
            n=self.n_new,
            rule=(
                f"REMAPPED, not frozen. The {self.n_old} shots of the frozen T009 sample were "
                f"located by midpoint in {self.old_index_path} (threshold "
                f"{self.old_threshold}, {self.n_old_shots} shots) and mapped onto the shot list "
                f"cut at threshold {self.new_threshold} ({self.n_new_shots} shots). They land on "
                f"{self.n_new} distinct new shots: {merged} row(s) absorbed more than one sampled "
                f"moment. THE DENOMINATOR IS {self.n_new}, NOT {self.n_old} - see "
                f"elvideo/eval/remap.py and tasks/T012-coarser-intervals.md."
            ),
            source="elvideo/eval/remap.py; state/decisions-log.md D-032; tasks/T012",
            keyframe_pattern="{work_dir}/keyframes/{shot_id}.png",
            baseline={
                "note": (
                    "Not directly comparable to the frozen sample's 2/2/13 T009 baseline or to "
                    "T011's mean 10.7/17 - different shots, different denominator. Compare RATES, "
                    "and state both denominators."
                ),
                "t011_best_mean_of_17": 10.7,
                "n_this_sample": self.n_new,
            },
            shots=[
                SampleShot(shot_id=r.new_shot_id, t009_verdict=r.carried_verdict) for r in self.rows
            ],
        )


def load_shots(index_path: str | Path) -> tuple[list[Shot], float | None]:
    """Read a written ``footage_index.json`` back as shots plus its detector threshold.

    The threshold comes from ``index_meta.scene_threshold`` (D-013 shipped that field precisely
    so a written index records how it was cut); ``None`` when an older index predates it.

    Raises:
        FileNotFoundError: If the index is missing.
    """
    src = Path(index_path)
    if not src.is_file():
        raise FileNotFoundError(f"index not found: {src}")
    raw = json.loads(src.read_text(encoding="utf-8"))
    index = FootageIndex.model_validate(raw)
    meta = raw.get("index_meta") or {}
    threshold = meta.get("scene_threshold")
    return list(index.shots), float(threshold) if threshold is not None else None


def shot_at(shots: Sequence[Shot], t: float) -> Shot:
    """Return the shot covering instant ``t``.

    Coverage is gapless and contiguous by construction (:func:`elvideo.index.scenes.detect_shots`),
    so exactly one shot matches on ``t_start <= t < t_end``. ``t`` at or past the final boundary
    resolves to the last shot rather than raising — a midpoint can only land there through float
    rounding at the very end of the clip.

    Raises:
        ValueError: If ``shots`` is empty.
    """
    if not shots:
        raise ValueError("cannot locate an instant in an empty shot list")
    for shot in shots:
        if shot.t_start <= t < shot.t_end:
            return shot
    return shots[-1] if t >= shots[-1].t_start else shots[0]


def remap_sample(
    old_index_path: str | Path,
    new_shots: Sequence[Shot],
    *,
    new_threshold: float,
    sample: AlignmentSample,
) -> RemapResult:
    """Carry ``sample`` from the old index's boundaries onto ``new_shots``, by timestamp.

    Args:
        old_index_path: The ``footage_index.json`` the sample's ids refer to — the threshold-27
            index. Only its ``shots[]`` timings are used.
        new_shots: The coarser shot list, from ``detect_shots(path, threshold=new_threshold)``.
        new_threshold: The threshold ``new_shots`` was cut at. Recorded, not re-derived.
        sample: The frozen sample to carry over. Passed explicitly rather than defaulted, so a
            remap can never happen by accident.

    Returns:
        A :class:`RemapResult` whose ``n_new`` is the denominator any resulting number must be
        quoted against.

    Raises:
        ValueError: If a sampled shot id is absent from the old index, or ``new_shots`` is empty.
    """
    old_shots, old_threshold = load_shots(old_index_path)
    by_id = {s.id: s for s in old_shots}
    if not new_shots:
        raise ValueError("new_shots is empty - nothing to remap onto")

    missing = [s.shot_id for s in sample.shots if s.shot_id not in by_id]
    if missing:
        raise ValueError(f"sampled shots absent from {old_index_path}: {', '.join(missing)}")

    # Group the sampled moments by the new shot that contains them. Insertion order is sample
    # order, which keeps the remapped rows in timeline order because the sample already is.
    grouped: dict[str, list[tuple[str, float]]] = defaultdict(list)
    new_by_id = {s.id: s for s in new_shots}
    for row in sample.shots:
        old = by_id[row.shot_id]
        midpoint = (old.t_start + old.t_end) / 2.0
        grouped[shot_at(new_shots, midpoint).id].append((row.shot_id, midpoint))

    verdicts = {s.shot_id: s.t009_verdict for s in sample.shots}
    rows: list[RemapRow] = []
    for new_id, hits in grouped.items():
        new = new_by_id[new_id]
        new_mid = (new.t_start + new.t_end) / 2.0
        nearest = min(hits, key=lambda h: abs(h[1] - new_mid))[0]
        rows.append(
            RemapRow(
                new_shot_id=new_id,
                new_t_start=new.t_start,
                new_t_end=new.t_end,
                old_shot_ids=[h[0] for h in hits],
                old_midpoints_s=[round(h[1], 3) for h in hits],
                carried_verdict=verdicts[nearest],
                collided=len(hits) > 1,
            )
        )

    return RemapResult(
        old_index_path=str(old_index_path),
        old_threshold=old_threshold,
        new_threshold=new_threshold,
        n_old=len(sample.shots),
        n_new=len(rows),
        n_old_shots=len(old_shots),
        n_new_shots=len(new_shots),
        rows=rows,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m elvideo.eval.remap OLD_INDEX NEW_INDEX --out sample.json``.

    Reads the new shot list out of the new index rather than re-detecting it, so the sample is
    guaranteed to name shots that actually exist in the index it will be used to grade.
    """
    parser = argparse.ArgumentParser(
        description="Carry the frozen alignment sample onto a coarser shot list (T012, D-033)."
    )
    parser.add_argument("old_index", help="The threshold-27 index the sample's ids refer to")
    parser.add_argument("new_index", help="The coarser index to grade")
    parser.add_argument("--out", default="", help="Write the remapped sample JSON here")
    parser.add_argument(
        "--provenance", default="", help="Write the full RemapResult here, collisions included"
    )
    args = parser.parse_args(argv)

    new_shots, new_threshold = load_shots(args.new_index)
    if new_threshold is None:
        raise SystemExit(
            f"{args.new_index} has no index_meta.scene_threshold (D-013); cannot record how it "
            "was cut, and an unlabelled denominator is what this module exists to prevent."
        )
    result = remap_sample(
        args.old_index, new_shots, new_threshold=new_threshold, sample=load_sample()
    )

    print(
        f"threshold {result.old_threshold} -> {result.new_threshold}: "
        f"{result.n_old_shots} -> {result.n_new_shots} shots; "
        f"{result.n_old} sampled moments -> {result.n_new} distinct shots "
        f"({len(result.collisions)} collision row(s))"
    )
    for row in result.collisions:
        print(
            f"  {row.new_shot_id} [{row.new_t_start:.2f}-{row.new_t_end:.2f}s] "
            f"<- {', '.join(row.old_shot_ids)}"
        )

    if args.out:
        Path(args.out).write_text(
            result.to_sample().model_dump_json(indent=2), encoding="utf-8"
        )
    if args.provenance:
        Path(args.provenance).write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover - thin entry point
    raise SystemExit(main())

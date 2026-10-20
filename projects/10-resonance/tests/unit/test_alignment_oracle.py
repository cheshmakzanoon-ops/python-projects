"""Enumerate all edit paths, independently of the production recurrence."""

import random
from collections.abc import Iterator

import pytest

from pp_resonance.alignment.dynamic import align
from pp_resonance.model import NoteEvent, ReferenceNote


def paths(rows: int, cols: int) -> Iterator[tuple[int, ...]]:
    if not rows and not cols:
        yield ()
    if rows and cols:
        for prefix in paths(rows - 1, cols - 1):
            yield (*prefix, 0)
    if rows:
        for prefix in paths(rows - 1, cols):
            yield (*prefix, 1)
    if cols:
        for prefix in paths(rows, cols - 1):
            yield (*prefix, 2)


@pytest.mark.parametrize("seed", range(40))
def test_alignment_minimizes_exhaustive_path_cost(seed: int) -> None:
    rng = random.Random(seed)
    rate, scale = 48000, rng.choice((0.5, 1.0, 1.5, 2.0))
    reference = [
        ReferenceNote(f"r{i}", rng.randrange(60, 64), i * 24000, i * 24000 + 12000)
        for i in range(rng.randrange(5))
    ]
    detected = [
        NoteEvent(
            f"n{i}",
            rng.randrange(60, 64),
            i * 24000 + rng.randrange(2400),
            i * 24000 + 12000,
            440,
            rng.choice((0.4, 0.95)),
            17,
        )
        for i in range(rng.randrange(5))
    ]

    def score(path: tuple[int, ...]) -> float:
        i, j, total = 0, 0, 0.0
        for operation in path:
            if operation == 0:
                ref, note = reference[i], detected[j]
                total += (
                    1.5 * abs(ref.midi - note.midi)
                    + min(2.0, abs(scale * ref.start - note.start) / rate)
                    + (3.0 if note.confidence < 0.8 else 0.0)
                )
                i, j = i + 1, j + 1
            else:
                total += 1.2
                i += operation == 1
                j += operation == 2
        return total

    costs = [score(path) for path in paths(len(reference), len(detected))]
    result = align(reference, detected, rate, scale)
    assert sum(item.cost for item in result) == pytest.approx(min(costs), abs=1e-12)
    assert [item.reference_id for item in result if item.reference_id is not None] == [
        r.id for r in reference
    ]
    assert [item.detected_id for item in result if item.detected_id is not None] == [
        n.id for n in detected
    ]
    for item in result:
        if item.reference_id is not None and item.detected_id is not None:
            ref = next(r for r in reference if r.id == item.reference_id)
            note = next(n for n in detected if n.id == item.detected_id)
            assert item.timing_samples == note.start - round(ref.start * scale)
            assert item.cents == (note.midi - ref.midi) * 100 + 17


def test_exact_tie_prefers_diagonal_and_gap_order_is_stable() -> None:
    # A timing-capped match costs 2.0; pick a 0.4-semitone-free difference
    # by adding timing 0.9 to a one-semitone substitution: exactly 2.4.
    ref = [ReferenceNote("r", 60, 0, 1000)]
    note = [NoteEvent("n", 61, 43200, 44000, 440, 0.95, 0)]
    assert [(a.reference_id, a.detected_id) for a in align(ref, note, 48000)] == [("r", "n")]
    # An expensive substitution has equally cheap insertion/deletion orders.
    note = [NoteEvent("n", 80, 0, 1000, 440, 0.95, 0)]
    assert [(a.reference_id, a.detected_id) for a in align(ref, note, 48000)] == [
        (None, "n"),
        ("r", None),
    ]


def test_explicit_tempo_changes_position_mapping_without_retiming_input() -> None:
    ref = [ReferenceNote("r", 60, 12000, 18000)]
    note = [NoteEvent("n", 60, 18000, 24000, 440, 0.95, -12)]
    result = align(ref, note, 48000, 1.5)
    assert result[0].timing_samples == 0 and result[0].cost == 0
    assert ref[0].start == 12000 and note[0].start == 18000

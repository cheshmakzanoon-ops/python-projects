"""External numerical records fail before allocation or output replacement."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from pp_resonance.alignment.dynamic import align
from pp_resonance.midi.export import export
from pp_resonance.model import AnalysisConfig, AudioSpec, FrameConfig, NoteEvent, ReferenceNote


@pytest.mark.parametrize("rate,channels", [(48000.0, 1), (48000, True), (48000, 1.0)])
def test_audio_dimensions_require_integers(rate: int, channels: int) -> None:
    with pytest.raises(ValueError):
        AudioSpec(rate, channels)


@pytest.mark.parametrize(
    "size,hop", [(2048.0, 256), (2048, True), (2048, 256.0), (2**40, 256), (2048, 0)]
)
def test_frame_dimensions_are_integer_and_bounded(size: int, hop: int) -> None:
    with pytest.raises(ValueError):
        FrameConfig(size, hop)


@pytest.mark.parametrize("threshold", [float("inf"), float("nan"), True])
def test_analysis_configuration_rejects_nonfinite_or_boolean_values(threshold: float) -> None:
    with pytest.raises(ValueError):
        AnalysisConfig(silence_rms=threshold)


def test_alignment_budget_is_checked_before_allocating_the_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse_allocation(*args: object, **kwargs: object) -> None:
        pytest.fail("oversized alignment must be refused before NumPy allocation")

    monkeypatch.setattr(np, "zeros", refuse_allocation)
    reference = [ReferenceNote("r", 60, 0, 4800)] * 2000
    detected = [NoteEvent("n", 60, 0, 4800, 261.6, 1, 0)] * 2000
    with pytest.raises(ValueError, match="cells"):
        align(reference, detected, 48000)


@pytest.mark.parametrize("budget", [0, -1, True, 4.0])
def test_alignment_budget_must_be_an_explicit_positive_integer(budget: int) -> None:
    with pytest.raises(ValueError, match="budget"):
        align([], [], 48000, max_cells=budget)


def test_alignment_validates_rate_and_event_identity() -> None:
    with pytest.raises(ValueError, match="sample rates"):
        align([], [], 0)
    reference = [
        ReferenceNote("duplicate", 60, 0, 4800),
        ReferenceNote("duplicate", 64, 4800, 9600),
    ]
    with pytest.raises(ValueError, match="unique IDs"):
        align(reference, [], 48000)


def test_alignment_can_use_an_exact_explicit_budget() -> None:
    reference = [ReferenceNote("r", 60, 0, 4800)]
    detected = [NoteEvent("n", 60, 0, 4800, 261.6, 1, 0)]
    assert [
        (match.reference_id, match.detected_id)
        for match in align(reference, detected, 48000, max_cells=4)
    ] == [("r", "n")]
    with pytest.raises(ValueError, match="cells"):
        align(reference, detected, 48000, max_cells=3)


@pytest.mark.parametrize(
    "field,value",
    [("confidence", float("inf")), ("cents", float("nan")), ("start", False), ("midi", 60.5)],
)
def test_alignment_rejects_invalid_event_metadata(field: str, value: object) -> None:
    note = replace(NoteEvent("n", 60, 0, 4800, 261.6, 1, 0), **{field: value})
    with pytest.raises(ValueError):
        align([], [note], 48000)


@pytest.mark.parametrize("scale", [float("nan"), float("inf"), True])
def test_alignment_rejects_invalid_tempo_scale(scale: float) -> None:
    with pytest.raises(ValueError):
        align([], [], 48000, scale)


@pytest.mark.parametrize(
    "field,value",
    [
        ("start", True),
        ("end", 48000.0),
        ("midi", 60.0),
        ("frequency", float("inf")),
        ("confidence", True),
        ("spread_cents", float("nan")),
    ],
)
def test_midi_rejects_invalid_note_metadata_without_replacing_existing_output(
    tmp_path: Path, field: str, value: object
) -> None:
    path = tmp_path / "notes.mid"
    path.write_bytes(b"keep existing MIDI")
    note = replace(NoteEvent("n", 60, 0, 48000, 261.6, 1, 0), **{field: value})
    with pytest.raises(ValueError):
        export(path, [note], 48000)
    assert path.read_bytes() == b"keep existing MIDI"


@pytest.mark.parametrize("tempo", [True, 500000.0])
def test_midi_tempo_requires_an_integer(tmp_path: Path, tempo: int) -> None:
    with pytest.raises(ValueError, match="tempo"):
        export(tmp_path / "notes.mid", [], 48000, tempo=tempo)

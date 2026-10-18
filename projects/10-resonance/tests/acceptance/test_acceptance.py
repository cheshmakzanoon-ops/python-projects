from dataclasses import replace

import pytest

from pp_resonance.alignment.dynamic import align
from pp_resonance.analysis import analyze
from pp_resonance.metrics.evaluate import pitch_grid
from pp_resonance.model import NoteEvent, ReferenceNote
from pp_resonance.notes.decode import cents, frequency
from pp_resonance.synthesis.tones import Tone, clean_plucks, render


def test_RE01_fixed_full_denominator() -> None:
    metrics = pitch_grid()
    assert metrics["eligible_frames"] == 6272
    assert metrics["success_ratio"] >= 0.95
    assert metrics["voicing_recall"] >= 0.95


def test_RE05_clean_events_no_silent_inventions() -> None:
    truth = clean_plucks()
    report = analyze(render(truth, 48000, 235200), 48000)
    assert len(report.notes) == len(truth) == len(report.onsets) == 6
    for note, event, onset in zip(report.notes, truth, report.onsets, strict=True):
        assert note.midi == event.midi
        assert abs(note.start / 48000 - event.onset) <= 0.060
        assert abs(note.end / 48000 - event.onset - event.duration) <= 0.080
        assert abs(onset.sample / 48000 - event.onset) <= 0.060
    # Abrupt fixture note-offs create positive spectral flux but must not become onsets.
    assert all(
        not any(abs(o.sample / 48000 - (t.onset + t.duration)) < 0.10 for t in truth)
        for o in report.onsets
    )


def test_RE06_expected_insert_delete_mapping() -> None:
    rate = 48000
    refs = [
        ReferenceNote(id, pitch, round(t * rate), round((t + 0.4) * rate))
        for id, pitch, t in zip("abcde", [60, 62, 64, 65, 67], [0, 0.6, 1.2, 1.8, 2.4], strict=True)
    ]
    notes = [
        NoteEvent(
            f"x{i}", pitch, round(t * rate), round((t + 0.4) * rate), frequency(pitch), 0.99, 0
        )
        for i, (pitch, t) in enumerate(
            zip([60, 62, 71, 65, 67], [0, 0.6, 1, 1.8, 2.4], strict=True)
        )
    ]
    output = align(refs, notes, rate)
    pairs = {(item.reference_id, item.detected_id) for item in output}
    assert pairs == {("a", "x0"), ("b", "x1"), ("c", None), (None, "x2"), ("d", "x3"), ("e", "x4")}
    perturbed = [
        replace(n, start=n.start + (1 if i % 2 else -1) * 1000) for i, n in enumerate(notes)
    ]
    assert {(a.reference_id, a.detected_id) for a in align(refs, perturbed, rate)} == pairs
    uncertain = [replace(n, confidence=0.1) for n in notes]
    assert all(
        a.reference_id is None or a.detected_id is None for a in align(refs, uncertain, rate)
    )
    assert len(align([], notes, rate)) == 5
    assert len(align(refs, [], rate)) == 5
    with pytest.raises(ValueError):
        align(refs, notes, rate, tempo_scale=5)


def test_bends_vibrato_are_reported_as_spread_not_criticism() -> None:
    audio = render([Tone(64, 0.2, 0.7, vibrato_cents=20, bend_cents=100)], 48000, 48000)
    report = analyze(audio, 48000)
    assert report.notes
    assert max(n.spread_cents for n in report.notes) > 15
    assert all(n.confidence >= 0.8 for n in report.notes)
    with pytest.raises(ValueError):
        cents(0, 440)


def test_RE01_missing_unvoiced_nonfinite_nonpositive_are_failures() -> None:
    from pp_resonance.metrics.evaluate import coverage_metrics, frame_errors
    from pp_resonance.model import PitchFrame

    expected = {index * 256: 440.0 for index in range(7)}
    frames = [
        PitchFrame(i * 256, i * 256 + 1024, hz, 1, 0.1, "test")
        for i, hz in enumerate((440, None, float("nan"), float("inf"), 0, 880))
    ]
    metrics = coverage_metrics(frame_errors(frames, expected))
    assert metrics["eligible_frames"] == 7
    assert metrics["successful_frames"] == 1
    assert metrics["voiced_frames"] == 2
    assert metrics["success_ratio"] == 1 / 7
    failed = coverage_metrics(frame_errors([], expected))
    assert failed["success_ratio"] == failed["voicing_recall"] == 0
    assert failed["conditional_p95_abs_cents"] is None


def test_repeated_same_pitch_reattacks_are_distinct_notes() -> None:
    # Adjacent same-pitch plucks have no silent gap to force an unvoiced split.
    # The original decoder merged these despite detecting both attacks.
    truth = [Tone(60, 0.30, 0.45), Tone(60, 0.75, 0.45)]
    result = analyze(render(truth, 48000, 72000), 48000)
    assert len(result.onsets) == len(result.notes) == 2
    assert [n.midi for n in result.notes] == [60, 60]
    for note, event in zip(result.notes, truth, strict=True):
        assert abs(note.start / 48000 - event.onset) < 0.06
        assert abs(note.end / 48000 - event.onset - event.duration) < 0.08
    assert result.notes[0].end <= result.notes[1].start
    bent = analyze(
        render([Tone(64, 0.2, 0.7, vibrato_cents=20, bend_cents=100)], 48000, 48000), 48000
    )
    assert len(bent.notes) == 1
    assert bent.notes[0].spread_cents > 15

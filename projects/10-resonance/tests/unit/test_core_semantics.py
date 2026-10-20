"""Independent invariants for signal scale, temporal locality and evaluator coverage."""

import numpy as np
import pytest

from pp_resonance.metrics.evaluate import note_metrics, onset_metrics, trajectory_metrics
from pp_resonance.model import AnalysisConfig, FrameConfig, OnsetEvent, PitchFrame
from pp_resonance.notes.decode import decode
from pp_resonance.onsets.detect import detect
from pp_resonance.pitch.difference import estimate, normalize
from pp_resonance.streaming.framing import Framer
from pp_resonance.synthesis.tones import Tone


def test_cmnd_is_invariant_to_energy_units() -> None:
    values = np.array([0, 2, 5, 1, 3, 0.1], dtype=np.float64)
    # The common scale cancels algebraically, including at very small energies.
    expected = np.concatenate(([1.0], values[1:] * np.arange(1, 6) / np.cumsum(values[1:])))
    for scale in (1e-30, 1e-10, 1, 1e20):
        np.testing.assert_allclose(normalize(values * scale), expected, atol=1e-14)


@pytest.mark.parametrize("rate", [44100, 48000])
def test_pitch_decisions_are_scale_invariant_above_configured_silence(rate: int) -> None:
    config = AnalysisConfig(silence_rms=1e-18)
    signal = np.sin(2 * np.pi * 440 * np.arange(2048) / rate)
    frames = [estimate(signal * scale, rate, 0, config) for scale in (1, 1e-6, 1e-15)]
    assert all(frame.frequency is not None for frame in frames)
    np.testing.assert_allclose([f.frequency for f in frames], 440, rtol=1e-4)
    np.testing.assert_allclose([f.confidence for f in frames], frames[0].confidence, atol=1e-12)


def test_distant_future_peak_cannot_change_an_earlier_onset() -> None:
    prefix = [0.0] * 40
    prefix[10] = 1.0
    future = [0.0] * 40
    future[20] = 100.0
    original = detect(prefix, list(range(0, 40 * 256, 256)), 48000, 2048)
    extended = detect(prefix + future, list(range(0, 80 * 256, 256)), 48000, 2048)
    assert len(original) == 1
    assert [o for o in extended if o.sample < 40 * 256] == original


def test_weak_onsets_cannot_retime_a_confident_note() -> None:
    frames = [PitchFrame(s, s + 1024, 440, 0.99, 0.2, "voiced") for s in range(4096, 24000, 256)]
    clean = decode(frames, [], 48000, 256, 30000)
    weak = decode(frames, [OnsetEvent(6000, 0.1)], 48000, 256, 30000)
    assert len(clean) == 1
    assert weak == clean


def test_feed_owns_input_immediately_and_rejects_interleaved_batches() -> None:
    framer = Framer(FrameConfig(size=1024, hop=256))
    samples = np.arange(2048, dtype=np.float64)
    expected = samples.copy()
    batch = framer.feed(samples)
    samples[:] = -1
    assert framer.received == 2048
    first = next(batch)
    np.testing.assert_array_equal(first[1], expected[:1024])
    with pytest.raises(ValueError, match="previous frame batch"):
        framer.feed(np.zeros(1))
    batch.close()
    remaining = list(framer.feed(np.empty(0), final=True))
    assert [first[0], *(start for start, _ in remaining)] == list(range(0, 2048, 256))
    for start, frame in remaining:
        count = min(1024, 2048 - start)
        np.testing.assert_array_equal(frame[:count], expected[start : start + count])
        np.testing.assert_array_equal(frame[count:], 0)
    assert framer.closed and framer.buffer.size == 0


def test_interrupted_flush_may_only_resume_with_an_empty_final_feed() -> None:
    framer = Framer(FrameConfig(size=1024, hop=256))
    batch = framer.feed(np.arange(1500, dtype=np.float64), final=True)
    assert next(batch)[0] == 0
    batch.close()
    with pytest.raises(ValueError, match="flush"):
        framer.feed(np.ones(1))
    assert [s for s, _ in framer.feed(np.empty(0), final=True)] == [256, 512, 768, 1024, 1280]
    with pytest.raises(ValueError, match="flushed"):
        framer.feed(np.empty(0), final=True)


@pytest.mark.parametrize("seed", range(4))
def test_partial_consumption_schedules_match_an_independent_padded_grid(seed: int) -> None:
    rng = np.random.default_rng(seed)
    original = rng.normal(size=16000)
    framer = Framer(FrameConfig(size=1024, hop=256))
    observed, position = [], 0
    while position < len(original):
        count = int(rng.integers(1, 2100))
        chunk = original[position : position + count].copy()
        position += len(chunk)
        batch = framer.feed(chunk)
        chunk[:] = -999  # A caller can reuse its input immediately after feed.
        for _ in range(int(rng.integers(0, 6))):
            try:
                observed.append(next(batch))
            except StopIteration:
                break
        batch.close()
    observed.extend(framer.feed(np.empty(0), final=True))
    assert [s for s, _ in observed] == list(range(0, len(original), 256))
    for start, frame in observed:
        expected = np.zeros(1024)
        segment = original[start : start + 1024]
        expected[: len(segment)] = segment
        np.testing.assert_array_equal(frame, expected)


@pytest.mark.parametrize("kind", ["duplicate", "off_grid", "wrong_center", "outside"])
def test_evaluator_rejects_ambiguous_output_timestamps(kind: str) -> None:
    good = PitchFrame(9984, 11008, 440, 1, 0.1, "voiced")
    frames = {
        "duplicate": [good, good],
        "off_grid": [PitchFrame(9985, 11009, 440, 1, 0.1, "voiced")],
        "wrong_center": [PitchFrame(9984, 11009, 440, 1, 0.1, "voiced")],
        "outside": [PitchFrame(48128, 49152, 440, 1, 0.1, "voiced")],
    }
    with pytest.raises(ValueError, match="timestamps"):
        trajectory_metrics(frames[kind], [Tone(69, 0.1, 0.4)], 48000, sample_count=48000)


def test_trajectory_denominator_is_independent_of_missing_output() -> None:
    truth = [Tone(69, 0.1, 0.4)]
    rate, count, size, hop = 48000, 48000, 2048, 256
    starts = list(range(0, count, hop))
    eligible = [s for s in starts if 0.2 <= (s + size // 2) / rate <= 0.45]
    frames = [PitchFrame(s, s + size // 2, 440, 1, 0.1, "voiced") for s in eligible]
    complete = trajectory_metrics(frames, truth, rate, sample_count=count)
    omitted = trajectory_metrics(frames[:1], truth, rate, sample_count=count)
    empty = trajectory_metrics([], truth, rate, sample_count=count)
    assert complete["eligible_voiced_frames"] == omitted["eligible_voiced_frames"] == len(eligible)
    assert complete["voicing_recall"] == 1
    assert omitted["voicing_recall"] == pytest.approx(1 / len(eligible))
    assert empty["voiced_misses"] == len(eligible)
    assert empty["conditional_median_abs_cents"] is None
    assert empty["mean_voiced_confidence"] is None
    assert omitted["missing_output_frames"] == len(starts) - 1


def test_unmatched_event_errors_are_undefined() -> None:
    truth = [Tone(69, 0.1, 0.4)]
    assert note_metrics([], truth, 48000)["onset_mae_seconds"] is None
    assert note_metrics([], truth, 48000)["pitch_mae_semitones"] is None
    assert onset_metrics([], truth, 48000)["mean_abs_error_seconds"] is None
    assert onset_metrics([], truth, 48000)["max_abs_error_seconds"] is None

"""Fixed-denominator scientific metrics, independent generator ground truth."""

import math
from typing import TypedDict

import numpy as np

from pp_resonance.analysis import analyze
from pp_resonance.model import AudioSpec, FrameConfig, NoteEvent, PitchFrame
from pp_resonance.notes.decode import cents, frequency
from pp_resonance.synthesis.tones import Tone, render


class PitchMetrics(TypedDict):
    eligible_frames: int
    successful_frames: int
    voiced_frames: int
    success_ratio: float
    voicing_recall: float
    conditional_median_abs_cents: float | None
    conditional_p95_abs_cents: float | None


def frame_errors(frames: list[PitchFrame], expected: dict[int, float]) -> list[float | None]:
    by_start = {frame.start: frame for frame in frames}
    errors: list[float | None] = []
    for start, hz in expected.items():
        frame = by_start.get(start)
        if (
            frame is None
            or frame.frequency is None
            or not math.isfinite(frame.frequency)
            or frame.frequency <= 0
        ):
            errors.append(None)
        else:
            errors.append(abs(cents(frame.frequency, hz)))
    return errors


def coverage_metrics(errors: list[float | None]) -> PitchMetrics:
    voiced = [error for error in errors if error is not None]
    denominator = len(errors)
    successes = sum(error <= 10 for error in voiced)
    return {
        "eligible_frames": denominator,
        "successful_frames": successes,
        "voiced_frames": len(voiced),
        "success_ratio": successes / denominator if denominator else 0,
        "voicing_recall": len(voiced) / denominator if denominator else 0,
        "conditional_median_abs_cents": float(np.median(voiced)) if voiced else None,
        "conditional_p95_abs_cents": float(np.percentile(voiced, 95)) if voiced else None,
    }


def pitch_grid(seed: int = 1729) -> PitchMetrics:
    errors: list[float | None] = []
    for rate in (44100, 48000):
        for midi in range(40, 89):
            audio = render(
                [Tone(midi, 0, 0.6, pluck=False)], rate, round(0.6 * rate), noise=0.0005, seed=seed
            )
            report = analyze(audio, rate)
            expected = {
                start: frequency(midi)
                for start in range(0, len(audio), 256)
                if start >= math.ceil(0.10 * rate) and start + 2048 <= math.floor(0.50 * rate)
            }
            errors.extend(frame_errors(report.pitches, expected))
    return coverage_metrics(errors)


def note_metrics(
    notes: list[NoteEvent], truth: list[Tone], rate: int
) -> dict[str, float | int | None]:
    # Ordered nearest-time evaluation is independent of the production DP aligner.
    remaining = set(range(len(notes)))
    matched, onset_errors, pitch_errors = 0, [], []
    for tone in truth:
        candidates = [i for i in remaining if abs(notes[i].start / rate - tone.onset) <= 0.15]
        if not candidates:
            continue
        index = min(candidates, key=lambda i: abs(notes[i].start / rate - tone.onset))
        remaining.remove(index)
        matched += 1
        onset_errors.append(abs(notes[index].start / rate - tone.onset))
        pitch_errors.append(abs(notes[index].midi - tone.midi))
    return {
        "truth_notes": len(truth),
        "detected_notes": len(notes),
        "matched_notes": matched,
        "misses": len(truth) - matched,
        "extras": len(remaining),
        "onset_mae_seconds": float(np.mean(onset_errors)) if onset_errors else None,
        "pitch_mae_semitones": float(np.mean(pitch_errors)) if pitch_errors else None,
    }


def trajectory_metrics(
    frames: list[PitchFrame],
    truth: list[Tone],
    rate: int,
    frame_size: int = 2048,
    *,
    sample_count: int,
    hop: int = 256,
) -> dict[str, float | int | None]:
    """Score the input's complete framing grid, including omitted output frames.

    Ground truth is analytic phase and event intervals. Recording length and
    framing configuration are independent inputs, never inferred from estimates.
    Conditional errors are undefined (None) when no valid voiced estimate exists.
    """
    AudioSpec(rate)
    FrameConfig(frame_size, hop)
    if type(sample_count) is not int or sample_count < 0:
        raise ValueError("Evaluation requires a nonnegative integer sample count")
    by_start = {}
    for observed in frames:
        if (
            type(observed.start) is not int
            or not 0 <= observed.start < sample_count
            or observed.start % hop
            or observed.center != observed.start + frame_size // 2
            or observed.start in by_start
        ):
            raise ValueError("Evaluation frames must have unique timestamps on the input grid")
        by_start[observed.start] = observed
    errors: list[float] = []
    eligible, missed, silence, false_voiced = 0, 0, 0, 0
    confidences = []
    expected_starts = range(0, sample_count, hop)
    for start in expected_starts:
        frame = by_start.get(start)
        time = (start + frame_size // 2) / rate
        valid = (
            frame is not None
            and frame.frequency is not None
            and math.isfinite(frame.frequency)
            and frame.frequency > 0
        )
        event = next(
            (t for t in truth if t.onset + 0.10 <= time <= t.onset + t.duration - 0.05), None
        )
        if event is not None:
            eligible += 1
            if not valid:
                missed += 1
                continue
            assert frame is not None and frame.frequency is not None
            relative = time - event.onset
            vibrato = event.vibrato_cents * np.log(2) / 1200 * np.sin(2 * np.pi * 5 * relative)
            bend = event.bend_cents * np.log(2) / 1200 * relative / event.duration
            expected = frequency(event.midi) * (1 + vibrato + bend)
            errors.append(abs(cents(frame.frequency, expected)))
            confidences.append(frame.confidence)
        elif not any(
            t.onset < (start + frame_size) / rate and t.onset + t.duration > start / rate
            for t in truth
        ):
            silence += 1
            false_voiced += valid
    return {
        "expected_output_frames": len(expected_starts),
        "missing_output_frames": len(expected_starts) - len(by_start),
        "eligible_voiced_frames": eligible,
        "voiced_misses": missed,
        "voicing_recall": (eligible - missed) / eligible if eligible else 0,
        "silence_frames": silence,
        "false_voiced_silence_frames": false_voiced,
        "within_10_cents_all_eligible": sum(e <= 10 for e in errors) / eligible if eligible else 0,
        "conditional_median_abs_cents": float(np.median(errors)) if errors else None,
        "conditional_p95_abs_cents": float(np.percentile(errors, 95)) if errors else None,
        "mean_voiced_confidence": float(np.mean(confidences)) if confidences else None,
    }


def onset_metrics(
    samples: list[int], truth: list[Tone], rate: int
) -> dict[str, float | int | None]:
    remaining = set(range(len(samples)))
    errors = []
    for tone in truth:
        candidates = [i for i in remaining if abs(samples[i] / rate - tone.onset) <= 0.15]
        if not candidates:
            continue
        index = min(candidates, key=lambda i: abs(samples[i] / rate - tone.onset))
        remaining.remove(index)
        errors.append(abs(samples[index] / rate - tone.onset))
    return {
        "truth_onsets": len(truth),
        "detected_onsets": len(samples),
        "misses": len(truth) - len(errors),
        "extras": len(remaining),
        "mean_abs_error_seconds": float(np.mean(errors)) if errors else None,
        "max_abs_error_seconds": max(errors) if errors else None,
    }

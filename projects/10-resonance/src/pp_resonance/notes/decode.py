"""Confidence-gated temporal decoding with pitch hysteresis and voiced gaps."""

import math
from bisect import bisect_left

import numpy as np

from pp_resonance.model import NoteEvent, OnsetEvent, PitchFrame


def frequency(midi: float) -> float:
    return 440 * 2 ** ((midi - 69) / 12)


def cents(estimated: float, reference: float) -> float:
    if not (
        math.isfinite(estimated) and math.isfinite(reference) and estimated > 0 and reference > 0
    ):
        raise ValueError("Cents require finite positive voiced frequencies")
    # Taking logs separately avoids overflow/underflow in a finite ratio.
    return 1200 * (math.log2(estimated) - math.log2(reference))


def decode(
    frames: list[PitchFrame], onsets: list[OnsetEvent], rate: int, hop: int, sample_count: int
) -> list[NoteEvent]:
    result: list[NoteEvent] = []
    group: list[PitchFrame] = []
    group_pitch: int | None = None
    missing = 0
    onset_index = 0
    # All segmentation decisions use the same credibility rule. A weak peak
    # cannot be ignored for splitting yet silently move a boundary or reattack.
    onset_samples = sorted(o.sample for o in onsets if o.confidence >= 0.5)

    def nearest_onset(sample: int) -> int | None:
        index = bisect_left(onset_samples, sample)
        neighbors = onset_samples[max(0, index - 1) : index + 1]
        return min(neighbors, key=lambda value: abs(value - sample)) if neighbors else None

    def finish(boundary: int | None = None) -> None:
        nonlocal group
        if not group:
            return
        good = [f for f in group if f.frequency is not None]
        start = max(0, good[0].center - hop // 2)
        end = min(sample_count, good[-1].center + hop // 2)
        if boundary is not None:
            end = min(end, boundary)
        nearby = nearest_onset(start)
        if nearby is not None and abs(nearby - start) <= int(0.08 * rate):
            start = nearby
        if result:
            start = max(start, result[-1].end)
        if end - start >= int(0.08 * rate):
            frequencies = [f.frequency for f in good if f.frequency is not None]
            hz = float(np.median(frequencies))
            midi = round(69 + 12 * math.log2(hz / 440))
            offsets = np.asarray([cents(f, hz) for f in frequencies])
            spread = float(np.percentile(offsets, 90) - np.percentile(offsets, 10))
            result.append(
                NoteEvent(
                    f"n{len(result)}",
                    midi,
                    start,
                    end,
                    hz,
                    float(np.mean([f.confidence for f in good])),
                    cents(hz, frequency(midi)),
                    spread,
                )
            )
        group = []

    for frame in frames:
        while onset_index < len(onset_samples) and onset_samples[onset_index] <= frame.center:
            onset = onset_samples[onset_index]
            onset_index += 1
            if group and onset - group[0].center >= int(0.08 * rate):
                finish(boundary=onset)
                group_pitch = None
                missing = 0
        if frame.frequency is None or frame.center >= sample_count:
            missing += 1
            if missing > 2:
                finish()
                group_pitch = None
            continue
        pitch = round(69 + 12 * math.log2(frame.frequency / 440))
        if group_pitch is not None and abs(pitch - group_pitch) >= 1:
            # Require a 60-cent departure to avoid semitone-boundary chatter.
            previous = group[-1].frequency if group else None
            abrupt = previous is not None and abs(cents(frame.frequency, previous)) > 35
            nearby = nearest_onset(frame.center)
            reattack = nearby is not None and abs(nearby - frame.center) < int(0.04 * rate)
            if abs(cents(frame.frequency, frequency(group_pitch))) > 60 and (abrupt or reattack):
                finish()
                group_pitch = None
        if group_pitch is None:
            group_pitch = pitch
        group.append(frame)
        missing = 0
    finish()
    return result

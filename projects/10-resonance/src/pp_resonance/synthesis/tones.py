"""Authored deterministic fixtures: ground truth is explicit synthesis metadata."""

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from pp_resonance.model import Samples
from pp_resonance.notes.decode import frequency


@dataclass(frozen=True)
class Tone:
    midi: int
    onset: float
    duration: float
    amplitude: float = 0.6
    pluck: bool = True
    vibrato_cents: float = 0
    bend_cents: float = 0


def render(
    tones: list[Tone], rate: int, count: int, start: int = 0, noise: float = 0, seed: int = 1729
) -> Samples:
    indices = np.arange(start, start + count)
    output = np.zeros(count)
    for tone in tones:
        onset, length = round(tone.onset * rate), round(tone.duration * rate)
        active = (indices >= onset) & (indices < onset + length)
        t = (indices[active] - onset) / rate
        hz = frequency(tone.midi)
        # Analytic phase modulation: instantaneous frequency has sinusoidal vibrato
        # and a linear cents approximation bend; small challenge perturbations only.
        phase = 2 * np.pi * hz * t
        if tone.vibrato_cents:
            depth = tone.vibrato_cents * np.log(2) / 1200
            phase += hz * depth / 5 * (1 - np.cos(2 * np.pi * 5 * t))
        if tone.bend_cents:
            depth = tone.bend_cents * np.log(2) / 1200
            phase += np.pi * hz * depth * t * t / tone.duration
        values = sum(
            amplitude * np.sin(h * phase + 0.3) for h, amplitude in ((1, 1), (2, 0.35), (3, 0.15))
        )
        envelope = np.minimum(1, t / 0.005) * np.exp(-t / 0.30) if tone.pluck else 1
        output[active] += tone.amplitude / 1.5 * values * envelope
    if noise:
        # Counter-indexed noise keeps generated samples invariant to chunk size.
        # Box-Muller using independent modular affine uniform sequences.
        x = indices.astype(np.uint64) + np.uint64(seed)
        with np.errstate(over="ignore"):
            x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
            x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
            x ^= x >> np.uint64(31)
        u = ((x >> np.uint64(11)).astype(np.float64) + 0.5) / 2**53
        v = ((x & np.uint64(0x1FFFFF)).astype(np.float64) + 0.5) / 2**21
        output += noise * np.sqrt(-2 * np.log(u)) * np.cos(2 * np.pi * v)
    return np.asarray(output, dtype=np.float64)


def chunks(
    tones: list[Tone],
    rate: int,
    duration: float,
    block: int = 8192,
    noise: float = 0,
    seed: int = 1729,
) -> Iterator[Samples]:
    count = round(rate * duration)
    for start in range(0, count, block):
        # Only overlapping events are rendered; ten-minute recordings do not create
        # a sample-sized timeline or repeatedly scan every reference event.
        end = (start + block) / rate
        nearby = [t for t in tones if t.onset < end and t.onset + t.duration > start / rate]
        yield render(nearby, rate, min(block, count - start), start, noise, seed)


def clean_plucks() -> list[Tone]:
    return [Tone(pitch, 0.30 + i * 0.75, 0.42) for i, pitch in enumerate([40, 45, 50, 55, 59, 64])]


def challenge(duration: float) -> list[Tone]:
    pitches = [40, 45, 50, 55, 59, 64, 69, 76, 83, 88]
    return [
        Tone(
            pitches[i % len(pitches)],
            0.3 + i * 0.75 + ((i % 3) - 1) * 0.025,
            0.42,
            vibrato_cents=20 if i % 7 == 0 else 0,
            bend_cents=100 if i % 11 == 0 else 0,
        )
        for i in range(int((duration - 0.8) / 0.75))
    ]

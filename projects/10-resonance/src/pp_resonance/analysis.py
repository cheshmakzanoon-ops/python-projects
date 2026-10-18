"""Offline bounded-input pipeline; output trajectory memory grows with duration."""

from collections.abc import Iterable

import numpy as np

from pp_resonance.audio_io.pcm import mono
from pp_resonance.model import AnalysisConfig, AnalysisReport, AudioSpec, Samples
from pp_resonance.notes.decode import decode
from pp_resonance.onsets.detect import detect
from pp_resonance.pitch.difference import estimate
from pp_resonance.spectral.transforms import flux, window
from pp_resonance.streaming.framing import Framer


def analyze_chunks(
    chunks: Iterable[Samples], rate: int, config: AnalysisConfig = AnalysisConfig()
) -> AnalysisReport:
    AudioSpec(rate)
    framer = Framer(config.frame)
    pitches, fluxes, starts = [], [], []
    previous: Samples | None = None
    clipped = False
    win = window(config.frame.size)

    def consume(start: int, frame: Samples) -> None:
        nonlocal previous
        pitches.append(estimate(frame, rate, start, config))
        magnitude = np.asarray(np.abs(np.fft.rfft(frame * win)), dtype=np.float64)
        fluxes.append(flux(previous, magnitude))
        starts.append(start)
        previous = magnitude

    for chunk in chunks:
        data = np.asarray(chunk, dtype=np.float64)
        if data.ndim != 1:
            raise ValueError("Chunk input must be mono; select stereo channel before streaming")
        clipped = clipped or bool(np.any(np.abs(data) >= 0.999))
        for start, frame in framer.feed(data):
            consume(start, frame)
    for start, frame in framer.feed(np.empty(0, dtype=np.float64), final=True):
        consume(start, frame)
    onsets = detect(fluxes, starts, rate, config.frame.size, [p.rms for p in pitches])
    notes = decode(pitches, onsets, rate, config.frame.hop, framer.received)
    diagnostics = []
    if clipped:
        diagnostics.append("clipping: full-scale samples present; interpret estimates cautiously")
    if framer.received < config.frame.size:
        diagnostics.append("short: recording is shorter than one analysis frame")
        # Padding a few cycles cannot establish a stable musical event.
        notes = []
    if not notes:
        diagnostics.append("no confident sustained notes; silence or uncertain/polyphonic input")
    uncertain = sum(p.frequency is None and p.rms >= config.silence_rms for p in pitches)
    if uncertain:
        diagnostics.append(f"{uncertain} non-silent frames were uncertain; no criticism inferred")
    return AnalysisReport(
        1,
        rate,
        framer.received,
        pitches,
        onsets,
        notes,
        diagnostics,
        framer.peak_buffer_samples,
        config=config,
    )


def analyze(
    samples: Samples, rate: int, config: AnalysisConfig = AnalysisConfig()
) -> AnalysisReport:
    data, warnings = mono(samples)
    # Batch convenience API retains caller's input but avoids a second full copy.
    report = analyze_chunks((data[i : i + 8192] for i in range(0, len(data), 8192)), rate, config)
    report.diagnostics.extend(warnings)
    return report

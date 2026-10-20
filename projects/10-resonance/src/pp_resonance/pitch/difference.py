"""Original fixed-window YIN implementation; FFT supplies only correlation kernels.

Based on de Cheveigné & Kawahara (JASA 2002), DOI 10.1121/1.1458024.
Unlike shrinking-overlap autocorrelation, every lag uses the same window length.
"""

import math

import numpy as np

from pp_resonance.model import AnalysisConfig, PitchFrame, Samples


def difference(samples: Samples, maximum_lag: int) -> Samples:
    width = len(samples) - maximum_lag
    if width <= 0:
        raise ValueError("Lag must be shorter than frame")
    fft_size = 1 << (2 * len(samples) - 1).bit_length()
    reference = np.zeros(len(samples), dtype=np.float64)
    reference[:width] = samples[:width]
    correlation = np.fft.irfft(
        np.fft.rfft(samples, fft_size) * np.conj(np.fft.rfft(reference, fft_size)), fft_size
    )[: maximum_lag + 1]
    prefix = np.concatenate(([0.0], np.cumsum(samples * samples)))
    lags = np.arange(maximum_lag + 1)
    result = prefix[width] + prefix[lags + width] - prefix[lags] - 2 * correlation
    return np.asarray(np.maximum(result, 0), dtype=np.float64)


def normalize(values: Samples) -> Samples:
    result = np.ones_like(values)
    denominator = np.cumsum(values[1:])
    np.divide(
        values[1:] * np.arange(1, len(values)),
        denominator,
        out=result[1:],
        # CMND is dimensionless: an absolute energy epsilon changes the pitch
        # decision when the same waveform is represented at another scale.
        where=denominator > 0,
    )
    return result


def estimate(
    samples: Samples, rate: int, start: int, config: AnalysisConfig = AnalysisConfig()
) -> PitchFrame:
    rms = float(np.sqrt(np.mean(samples * samples)))
    center = start + len(samples) // 2
    if rms < config.silence_rms:
        return PitchFrame(start, center, None, 0.0, rms, "silence")
    lower, upper = max(2, int(rate / 1400)), int(rate / 78)
    curve = normalize(difference(samples - np.mean(samples), upper))
    lag = lower
    while lag < upper and curve[lag] >= config.threshold:
        lag += 1
    if lag == upper:
        return PitchFrame(start, center, None, 0.0, rms, "aperiodic/uncertain")
    while lag + 1 < upper and curve[lag + 1] < curve[lag]:
        lag += 1
    confidence = max(0.0, min(1.0, 1 - float(curve[lag])))
    if confidence < config.minimum_confidence:
        return PitchFrame(start, center, None, confidence, rms, "low confidence")
    a, b, c = map(float, curve[lag - 1 : lag + 2])
    denominator = a - 2 * b + c
    delta = 0.5 * (a - c) / denominator if abs(denominator) > 1e-15 else 0.0
    interpolated = lag + min(0.5, max(-0.5, delta))
    hz = rate / interpolated
    if not math.isfinite(hz):
        return PitchFrame(start, center, None, confidence, rms, "nonfinite")
    return PitchFrame(start, center, hz, confidence, rms, "voiced")

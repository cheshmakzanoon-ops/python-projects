"""Explicit padded STFT and normalized overlap-add inverse."""

import numpy as np
from numpy.typing import NDArray

from pp_resonance.model import Samples


def window(size: int) -> Samples:
    return np.asarray(np.sin(np.pi * (np.arange(size) + 0.5) / size), dtype=np.float64)


def padded(samples: Samples, size: int, hop: int) -> Samples:
    extra = (-(len(samples) + size)) % hop
    return np.pad(samples, (size, size + extra))


def stft(samples: Samples, size: int = 2048, hop: int = 512) -> NDArray[np.complex128]:
    if not 0 < hop <= size:
        raise ValueError("hop outside supported range")
    x = padded(samples, size, hop)
    frames = np.lib.stride_tricks.sliding_window_view(x, size)[::hop]
    return np.asarray(np.fft.rfft(frames * window(size), axis=1), dtype=np.complex128)


def inverse(
    spectrum: NDArray[np.complex128], length: int, size: int = 2048, hop: int = 512
) -> Samples:
    total = (len(spectrum) - 1) * hop + size
    output = np.zeros(total)
    weight = np.zeros(total)
    win = window(size)
    for index, frame in enumerate(np.fft.irfft(spectrum, n=size, axis=1)):
        start = index * hop
        output[start : start + size] += frame * win
        weight[start : start + size] += win * win
    np.divide(output, weight, out=output, where=weight > 1e-15)
    return np.asarray(output[size : size + length], dtype=np.float64)


def flux(previous: Samples | None, current: Samples) -> float:
    if previous is None:
        return 0.0
    return float(np.mean(np.maximum(current - previous, 0.0)))

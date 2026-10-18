"""Safe PCM boundaries. Stereo chooses the energetic channel to avoid cancellation."""

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import soundfile as sf

from pp_resonance.model import AudioSpec, Samples


def mono(samples: Samples) -> tuple[Samples, list[str]]:
    data = np.asarray(samples, dtype=np.float64)
    if not np.all(np.isfinite(data)):
        raise ValueError("Audio contains NaN or infinite samples")
    warnings = []
    if data.ndim == 2 and data.shape[1] == 2:
        # Deterministic left tie break. This policy preserves antiphase instruments.
        channel = int(np.argmax(np.sum(data * data, axis=0)))
        data = data[:, channel].copy()
        warnings.append(f"stereo: selected energetic channel {channel}; channels are not summed")
    elif data.ndim != 1:
        raise ValueError("Expected mono vector or stereo (samples,2) matrix")
    if np.any(np.abs(data) >= 0.999):
        warnings.append("clipping: samples at or above full scale; pitch may be unreliable")
    return data, warnings


def blocks(path: Path, block_size: int = 8192) -> tuple[AudioSpec, Iterator[Samples]]:
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    with sf.SoundFile(path) as file:
        spec = AudioSpec(file.samplerate, file.channels)
        # Choose once for the file. Do not switch channels at chunk boundaries.
        probe = file.read(min(len(file), spec.sample_rate), dtype="float64", always_2d=True)
        channel = int(np.argmax(np.sum(probe * probe, axis=0))) if len(probe) else 0

    def read() -> Iterator[Samples]:
        with sf.SoundFile(path) as audio:
            while len(part := audio.read(block_size, dtype="float64", always_2d=True)):
                yield np.asarray(part[:, channel], dtype=np.float64)

    return spec, read()


def write(path: Path, samples: Samples, sample_rate: int) -> None:
    AudioSpec(sample_rate)
    sf.write(path, samples, sample_rate, subtype="PCM_16")


def preview(path: Path, seconds: int = 30) -> Samples:
    """Read a bounded report clip using exactly the streaming channel policy."""
    if not 1 <= seconds <= 30:
        raise ValueError("Report preview must be 1–30 seconds")
    with sf.SoundFile(path) as file:
        spec = AudioSpec(file.samplerate, file.channels)
        probe = file.read(min(len(file), spec.sample_rate), dtype="float64", always_2d=True)
        channel = int(np.argmax(np.sum(probe * probe, axis=0))) if len(probe) else 0
        file.seek(0)
        clip = file.read(
            min(len(file), seconds * spec.sample_rate), dtype="float64", always_2d=True
        )
        return np.asarray(clip[:, channel], dtype=np.float64)

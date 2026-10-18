"""Chunk-independent start timestamps and bounded overlap retention."""

from collections.abc import Iterator

import numpy as np

from pp_resonance.model import FrameConfig, Samples


class Framer:
    def __init__(self, config: FrameConfig = FrameConfig()) -> None:
        self.config = config
        self.buffer = np.empty(0, dtype=np.float64)
        self.next_start = 0
        self.received = 0
        self.closed = False
        self.peak_buffer_samples = 0

    def feed(self, chunk: Samples, *, final: bool = False) -> Iterator[tuple[int, Samples]]:
        if self.closed:
            raise ValueError("Framer already flushed")
        chunk = np.asarray(chunk, dtype=np.float64)
        if chunk.ndim != 1 or not np.all(np.isfinite(chunk)):
            raise ValueError("Frames require finite mono samples")
        self.received += len(chunk)
        self.buffer = np.concatenate((self.buffer, chunk))
        self.peak_buffer_samples = max(self.peak_buffer_samples, len(self.buffer))
        size, hop = self.config.size, self.config.hop
        while len(self.buffer) >= size or (final and self.next_start < self.received):
            frame = np.zeros(size, dtype=np.float64)
            count = min(size, len(self.buffer))
            frame[:count] = self.buffer[:count]
            yield self.next_start, frame
            self.next_start += hop
            self.buffer = self.buffer[min(hop, len(self.buffer)) :]
        if final:
            self.closed = True
            self.buffer = np.empty(0, dtype=np.float64)

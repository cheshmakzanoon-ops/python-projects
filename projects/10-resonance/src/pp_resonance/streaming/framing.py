"""Chunk-independent framing with explicit ownership of partially consumed batches."""

from collections.abc import Iterator

import numpy as np

from pp_resonance.model import FrameConfig, Samples


class FrameBatch(Iterator[tuple[int, Samples]]):
    """One feed's frame iterator. Close early to release its exclusive ownership.

    Emitted frames are independent copies. Closing leaves unconsumed samples in
    the framer; an interrupted final batch can resume with an empty final feed.
    """

    def __init__(self, framer: "Framer") -> None:
        self._framer = framer
        self._closed = False
        framer._feeding = True
        self._complete_if_drained()

    def _complete_if_drained(self) -> None:
        framer = self._framer
        if framer._flushing and framer.next_start >= framer.received:
            framer.closed = True
            framer.buffer = np.empty(0, dtype=np.float64)
            self.close()
        elif not framer._flushing and len(framer.buffer) < framer.config.size:
            self.close()

    def __next__(self) -> tuple[int, Samples]:
        if self._closed:
            raise StopIteration
        framer = self._framer
        size, hop = framer.config.size, framer.config.hop
        frame = np.zeros(size, dtype=np.float64)
        count = min(size, len(framer.buffer))
        frame[:count] = framer.buffer[:count]
        start = framer.next_start
        # Commit before exposing the frame. A closed iterator cannot replay it.
        framer.next_start += hop
        framer.buffer = framer.buffer[min(hop, len(framer.buffer)) :]
        self._complete_if_drained()
        return start, frame

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._framer._feeding = False

    def __del__(self) -> None:
        self.close()


class Framer:
    def __init__(self, config: FrameConfig = FrameConfig()) -> None:
        self.config = config
        self.buffer = np.empty(0, dtype=np.float64)
        self.next_start = 0
        self.received = 0
        self.closed = False
        self.peak_buffer_samples = 0
        self._feeding = False
        self._flushing = False

    def feed(self, chunk: Samples, *, final: bool = False) -> FrameBatch:
        """Copy input now; exhaust or close this batch before accepting another.

        After accepting a final feed, no additional samples may be appended.
        The final feed emits every start below received, padding only its tail.
        """
        if self.closed:
            raise ValueError("Framer already flushed")
        if self._feeding:
            raise ValueError("Exhaust or close the previous frame batch before feeding again")
        chunk = np.asarray(chunk, dtype=np.float64)
        if chunk.ndim != 1 or not np.all(np.isfinite(chunk)):
            raise ValueError("Frames require finite mono samples")
        if self._flushing and (len(chunk) or not final):
            raise ValueError("An interrupted flush requires an empty final feed")
        self.received += len(chunk)
        self.buffer = np.concatenate((self.buffer, chunk))
        self.peak_buffer_samples = max(self.peak_buffer_samples, len(self.buffer))
        self._flushing = self._flushing or final
        return FrameBatch(self)

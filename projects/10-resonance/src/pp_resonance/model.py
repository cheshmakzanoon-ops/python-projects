"""Versioned public records; integer samples are the timing authority."""

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

Samples = NDArray[np.float64]


@dataclass(frozen=True)
class AudioSpec:
    sample_rate: int
    channels: int = 1

    def __post_init__(self) -> None:
        if self.sample_rate not in (44100, 48000):
            raise ValueError("Supported sample rates are 44100 and 48000 Hz; resample explicitly")
        if self.channels not in (1, 2):
            raise ValueError("Only mono or stereo PCM is supported")


@dataclass(frozen=True)
class FrameConfig:
    size: int = 2048
    hop: int = 256

    def __post_init__(self) -> None:
        if self.size < 1024 or not 0 < self.hop <= self.size:
            raise ValueError("Require frame size >=1024 and hop in [1,size]")


@dataclass(frozen=True)
class PitchFrame:
    start: int
    center: int
    frequency: float | None
    confidence: float
    rms: float
    reason: str


@dataclass(frozen=True)
class OnsetEvent:
    sample: int
    confidence: float


@dataclass(frozen=True)
class NoteEvent:
    id: str
    midi: int
    start: int
    end: int
    frequency: float
    confidence: float
    cents: float
    spread_cents: float = 0.0


@dataclass(frozen=True)
class ReferenceNote:
    id: str
    midi: int
    start: int
    end: int


@dataclass(frozen=True)
class AlignedNote:
    reference_id: str | None
    detected_id: str | None
    cost: float
    timing_samples: int | None
    cents: float | None


@dataclass(frozen=True)
class AnalysisConfig:
    frame: FrameConfig = field(default_factory=FrameConfig)
    threshold: float = 0.15
    silence_rms: float = 0.003
    minimum_confidence: float = 0.8

    def __post_init__(self) -> None:
        if not 0 < self.threshold < 1 or not 0 < self.minimum_confidence <= 1:
            raise ValueError("Pitch threshold/confidence must be in (0,1)")
        if not self.silence_rms > 0:
            raise ValueError("Silence RMS must be positive")


@dataclass
class AnalysisReport:
    schema_version: int
    sample_rate: int
    sample_count: int
    pitches: list[PitchFrame]
    onsets: list[OnsetEvent]
    notes: list[NoteEvent]
    diagnostics: list[str]
    peak_buffer_samples: int
    alignment: list[AlignedNote] = field(default_factory=list)
    config: AnalysisConfig = field(default_factory=AnalysisConfig)

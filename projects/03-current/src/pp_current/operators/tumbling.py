"""Half-open event-time tumbling/sliding window assignment and aggregates."""

from __future__ import annotations

from dataclasses import dataclass


def windows(timestamp: int, size: int, slide: int) -> list[int]:
    if size < 1 or slide < 1 or size % slide:
        raise ValueError("positive size must be an integer multiple of slide")
    latest = timestamp // slide * slide
    return [latest - i * slide for i in range(size // slide)]


@dataclass
class Aggregate:
    count: int = 0
    total: int = 0
    minimum: int | None = None
    maximum: int | None = None

    def add(self, value: int) -> None:
        self.count += 1
        self.total += value
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)

    def result(self) -> dict[str, int | float | None]:
        return {
            "count": self.count,
            "sum": self.total,
            "min": self.minimum,
            "max": self.maximum,
            "average": self.total / self.count if self.count else None,
        }

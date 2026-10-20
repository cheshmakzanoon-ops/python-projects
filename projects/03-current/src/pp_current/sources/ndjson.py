"""Replayable caller-selected NDJSON source with bounded line size."""

from collections.abc import Iterator
from pathlib import Path

from pp_current.model.envelope import Record


def read_ndjson(path: Path) -> Iterator[Record]:
    with path.open(encoding="utf-8") as handle:
        while raw := handle.readline(16_385):
            # Allow the delimiter in addition to the 16 KiB record itself.
            if len(raw.encode()) > 16_385 or not raw.endswith("\n"):
                raise ValueError("overlong or unterminated NDJSON record")
            yield Record.parse(raw)

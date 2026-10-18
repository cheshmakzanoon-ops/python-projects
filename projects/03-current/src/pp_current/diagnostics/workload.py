"""Seeded generated readings/metadata; no external data assets."""

from __future__ import annotations

import random
from collections.abc import Iterator

from pp_current.model.envelope import Record, canonical

INPUTS = tuple(canonical(["devices", partition]) for partition in range(4))


def generate(count: int, seed: int, *, hot: bool = False) -> Iterator[Record]:
    randomizer = random.Random(seed)
    offsets = [0] * 4

    def control(partition: int, kind: str, timestamp: int = 0) -> Record:
        from typing import cast

        from pp_current.model.envelope import Kind

        record = Record("devices", partition, offsets[partition], timestamp, kind=cast(Kind, kind))
        offsets[partition] += 1
        return record

    for i in range(count):
        partition = i % 4
        timestamp = i * 100
        if i and i % 1000 == 0:
            for source in range(4):
                yield control(source, "watermark", timestamp - 2000)
        if i == count // 2:
            yield control(3, "idle")
        if i == count // 2 + min(1000, count // 4):
            yield control(3, "resume")
        # While idle, partition 3 is explicitly excluded and no events admitted to it.
        if count // 2 <= i < count // 2 + min(1000, count // 4) and partition == 3:
            partition = 2
        if randomizer.random() < 0.1:
            timestamp -= randomizer.randrange(1, 25_000)
        key = "hot" if hot and i % 2 == 0 else f"device-{randomizer.randrange(10_000)}"
        record = Record(
            "devices",
            partition,
            offsets[partition],
            timestamp,
            key,
            randomizer.randrange(-100, 101),
            stream="metadata" if i % 7 == 0 else "reading",
            event_id=f"event-{i}",
            payload="x" * 64,
        )
        offsets[partition] += 1
        yield record
    for source in range(4):
        yield control(source, "resume")
        yield control(source, "end")

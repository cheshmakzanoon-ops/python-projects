"""An original deterministic skip-list ordered by (user key, descending sequence)."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass

from pp_strata.codec.records import Record

LEVELS = 20


@dataclass(slots=True)
class Node:
    record: Record | None
    forward: list[Node | None]


class Memtable:
    def __init__(self) -> None:
        self.head = Node(None, [None] * LEVELS)
        self.bytes = 0
        self.count = 0

    def add(self, record: Record) -> None:
        update = [self.head] * LEVELS
        node = self.head
        for level in range(LEVELS - 1, -1, -1):
            while (following := node.forward[level]) is not None:
                assert following.record is not None
                if following.record.order >= record.order:
                    break
                node = following
            update[level] = node
        digest = int.from_bytes(
            hashlib.blake2b(record.key + record.sequence.to_bytes(8), digest_size=8).digest()
        )
        height = 1
        while height < LEVELS and digest & 1:
            height += 1
            digest >>= 1
        new = Node(record, [None] * height)
        for level in range(height):
            new.forward[level] = update[level].forward[level]
            update[level].forward[level] = new
        self.bytes += len(record.key) + len(record.value or b"") + 15
        self.count += 1

    def records(self, start: bytes = b"", stop: bytes | None = None) -> Iterator[Record]:
        node = self.head
        for level in range(LEVELS - 1, -1, -1):
            while (following := node.forward[level]) is not None:
                assert following.record is not None
                if following.record.key >= start:
                    break
                node = following
        node_or_none = node.forward[0]
        while node_or_none is not None:
            record = node_or_none.record
            assert record is not None
            if stop is not None and record.key >= stop:
                return
            yield record
            node_or_none = node_or_none.forward[0]

    def get(self, key: bytes, sequence: int) -> Record | None:
        # Seek the complete internal key, not the beginning of the user-key run.
        # Old snapshots must not walk every newer version of a hot key.
        target = key, -sequence
        node = self.head
        for level in range(LEVELS - 1, -1, -1):
            while (following := node.forward[level]) is not None:
                assert following.record is not None
                if following.record.order >= target:
                    break
                node = following
        candidate = node.forward[0]
        if candidate is not None:
            record = candidate.record
            assert record is not None
            if record.key == key:
                return record
        return None

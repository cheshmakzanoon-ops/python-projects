"""One-pass MVCC retention and conflict-head reclamation at a pinned sequence floor."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from pp_strata.codec.records import Record


@dataclass(slots=True)
class VersionRetention:
    floor: int
    pinned: bool
    heads: dict[bytes, int] = field(default_factory=dict, init=False)

    def records(self, source: Iterable[Record]) -> Iterator[Record]:
        """Keep all versions above the floor and one visible floor version.

        A deleted key needs a conflict head only while a handle predating that
        deletion exists. Live keys always keep their latest sequence. The caller
        installs these heads only after consuming the stream and durably installing
        the corresponding table; failed construction cannot change live state.
        """
        seen_key: bytes | None = None
        kept_floor = False
        for record in source:
            if record.key != seen_key:
                seen_key, kept_floor = record.key, False
                if record.value is not None or record.sequence > self.floor:
                    self.heads[record.key] = record.sequence
            if record.sequence > self.floor:
                yield record
            elif not kept_floor:
                kept_floor = True
                if record.value is not None or self.pinned:
                    yield record

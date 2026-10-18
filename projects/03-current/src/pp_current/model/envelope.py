"""Version-one integer-millisecond wire envelope."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

Kind = Literal["event", "watermark", "idle", "resume", "end"]


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class Record:
    source_id: str
    partition: int
    source_offset: int
    event_time: int = 0
    key: str = ""
    value: int = 0
    stream: str = "reading"
    event_id: str = ""
    kind: Kind = "event"
    schema_version: int = 1
    payload: str = ""
    ingress_ordinal: int = 0

    def __post_init__(self) -> None:
        for name in ("source_id", "key", "stream", "event_id", "payload"):
            if not isinstance(getattr(self, name), str):
                raise ValueError("string fields required")
        for name in ("partition", "source_offset", "schema_version", "ingress_ordinal"):
            if type(getattr(self, name)) is not int:
                raise ValueError("integer identity fields required")
        if not -(2**62) <= self.event_time < 2**62:
            raise ValueError("timestamp outside supported integer range")
        if not self.source_id or self.partition < 0 or self.source_offset < 0:
            raise ValueError("invalid source identity")
        if self.schema_version != 1 or self.kind not in (
            "event",
            "watermark",
            "idle",
            "resume",
            "end",
        ):
            raise ValueError("unsupported record schema/kind")
        if type(self.event_time) is not int or type(self.value) is not int:
            raise ValueError("integer timestamps and values required")
        if self.stream not in ("reading", "metadata"):
            raise ValueError("unsupported stream")
        if len(canonical(self.dictionary()).encode()) > 16_384:
            raise ValueError("record exceeds 16 KiB")

    def dictionary(self) -> dict[str, object]:
        # This wire schema contains scalars only; avoid recursive dataclass deepcopy.
        return {
            "source_id": self.source_id,
            "partition": self.partition,
            "source_offset": self.source_offset,
            "event_time": self.event_time,
            "key": self.key,
            "value": self.value,
            "stream": self.stream,
            "event_id": self.event_id,
            "kind": self.kind,
            "schema_version": self.schema_version,
            "payload": self.payload,
            "ingress_ordinal": self.ingress_ordinal,
        }

    @property
    def input_id(self) -> str:
        return canonical([self.source_id, self.partition])

    def wire(self) -> str:
        data = self.dictionary()
        data["ingress_ordinal"] = 0
        return canonical(data)

    @classmethod
    def parse(cls, raw: str, *, ordinal: int | None = None) -> Record:
        data: dict[str, object] = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("record object required")
        if ordinal is not None:
            data["ingress_ordinal"] = ordinal
        return cls(**data)  # type: ignore[arg-type]


def partition_for(key: str, workers: int) -> int:
    if workers < 1:
        raise ValueError("positive worker count required")
    return int.from_bytes(hashlib.blake2b(key.encode(), digest_size=8).digest(), "big") % workers

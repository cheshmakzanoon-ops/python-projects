"""Monotonic minimum-active-input watermark policy; idleness is journaled."""

from __future__ import annotations

from dataclasses import dataclass, field

from pp_current.model.envelope import Record

MIN_TIME = -(2**63)
MAX_TIME = 2**63 - 1


@dataclass
class Progress:
    inputs: dict[str, int]
    idle: set[str] = field(default_factory=set)
    watermark: int = MIN_TIME

    def apply(self, record: Record) -> int:
        identity = record.input_id
        if identity not in self.inputs:
            raise ValueError("input must be registered before run")
        if record.kind == "idle":
            self.idle.add(identity)
        elif record.kind == "resume":
            self.idle.discard(identity)
        elif record.kind in ("watermark", "end"):
            next_time = MAX_TIME if record.kind == "end" else record.event_time
            if next_time < self.inputs[identity]:
                raise ValueError("input watermark regression")
            self.inputs[identity] = next_time
        active = [v for k, v in self.inputs.items() if k not in self.idle]
        if active:
            self.watermark = max(self.watermark, min(active))
        return self.watermark

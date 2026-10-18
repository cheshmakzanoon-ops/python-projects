"""Deterministic ordered state machine. All effects are staged until checkpoint."""

from __future__ import annotations

import heapq
import json
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import cast

from pp_current.event_time.policy import MIN_TIME, Progress
from pp_current.model.envelope import Record, canonical
from pp_current.operators.tumbling import Aggregate, windows

CODE_VERSION = "current-1"


@dataclass(frozen=True)
class Config:
    inputs: tuple[str, ...]
    workers: int = 4
    size: int = 30_000
    slide: int = 15_000
    lateness: int = 10_000
    join_interval: int = 5_000
    state_limit: int = 1_000_000
    pipeline_version: str = "identity-v1"

    def __post_init__(self) -> None:
        if not self.inputs or len(set(self.inputs)) != len(self.inputs):
            raise ValueError("unique registered inputs required")
        windows(0, self.size, self.slide)
        if min(self.workers, self.state_limit) < 1 or min(self.lateness, self.join_interval) < 0:
            raise ValueError("invalid configuration")


@dataclass(frozen=True)
class Delivery:
    job_id: str
    operator_id: str
    logical_result_key: str
    revision: int
    payload: str

    def __post_init__(self) -> None:
        if (
            not self.job_id
            or not self.operator_id
            or type(self.revision) is not int
            or self.revision < 1
        ):
            raise ValueError("invalid delivery identity")
        if canonical(json.loads(self.payload)) != self.payload:
            raise ValueError("delivery payload must be canonical JSON")

    @property
    def identity(self) -> tuple[str, str, str, int]:
        return self.job_id, self.operator_id, self.logical_result_key, self.revision


@dataclass
class Window:
    operator: str
    key: str
    start: int
    aggregate: Aggregate = field(default_factory=Aggregate)
    revision: int = 0
    dirty: bool = True


class Engine:
    def __init__(self, config: Config, job_id: str = "demo") -> None:
        self.config = config
        self.job_id = job_id
        self.progress = Progress(dict.fromkeys(config.inputs, MIN_TIME))
        self.position = 0
        self.state: dict[str, Window] = {}
        self.join: dict[str, list[Record]] = {}
        self.pending: list[Delivery] = []
        self.dispositions: dict[str, int] = {"on-time": 0, "accepted-late": 0, "rejected-late": 0}
        self.trace: deque[tuple[int, str, int]] = deque(maxlen=10_000)
        self.join_count = 0
        self.close_heap: list[tuple[int, str]] = []
        self.expire_heap: list[tuple[int, str]] = []
        self.peak_state = 0
        self.max_watermark_lag = 0
        self.max_finalization_lag = 0

    def _emit(self, window: Window) -> None:
        if self.progress.watermark < 2**62:
            self.max_finalization_lag = max(
                self.max_finalization_lag, self.progress.watermark - window.start - self.config.size
            )
        window.revision += 1
        window.dirty = False
        key = canonical([window.key, window.start, window.start + self.config.size])
        payload = canonical(
            {
                "key": window.key,
                "start": window.start,
                "end": window.start + self.config.size,
                **window.aggregate.result(),
            }
        )
        self.pending.append(Delivery(self.job_id, window.operator, key, window.revision, payload))

    def apply(self, record: Record) -> str:
        if record.ingress_ordinal != self.position + 1:
            raise ValueError("records must form a contiguous journal prefix")
        if record.input_id not in self.progress.inputs:
            raise ValueError("unknown input")
        if record.kind == "event" and record.input_id in self.progress.idle:
            raise ValueError("explicit resume required before event")
        watermark = self.progress.watermark
        disposition: str
        if record.kind != "event":
            self.progress.apply(record)
            disposition = record.kind
        else:
            disposition = (
                "rejected-late"
                if record.event_time + self.config.lateness < watermark
                else "accepted-late"
                if record.event_time < watermark
                else "on-time"
            )
            if watermark > MIN_TIME:
                self.max_watermark_lag = max(self.max_watermark_lag, record.event_time - watermark)
            self.dispositions[disposition] += 1
            if disposition != "rejected-late":
                self._event(record)
        self.position = record.ingress_ordinal
        if record.kind != "event":
            self._expire()
        self.trace.append((self.position, disposition, self.progress.watermark))
        self.peak_state = max(self.peak_state, len(self.state) + self.join_count)
        if self.peak_state > self.config.state_limit:
            raise MemoryError("operator state limit reached: restore checkpoint and raise budget")
        return disposition

    def _event(self, record: Record) -> None:
        if record.stream == "reading":
            for operator, slide in [("tumbling", self.config.size), ("sliding", self.config.slide)]:
                for start in windows(record.event_time, self.config.size, slide):
                    identity = canonical([operator, record.key, start])
                    if identity not in self.state:
                        self.state[identity] = Window(operator, record.key, start)
                        heapq.heappush(self.close_heap, (start + self.config.size, identity))
                        heapq.heappush(
                            self.expire_heap,
                            (start + self.config.size + self.config.lateness, identity),
                        )
                    window = self.state[identity]
                    window.aggregate.add(record.value)
                    window.dirty = True
                    if start + self.config.size <= self.progress.watermark:
                        self._emit(window)
        matches = self.join.setdefault(record.key, [])
        for other in matches:
            if (
                other.stream != record.stream
                and abs(other.event_time - record.event_time) <= self.config.join_interval
            ):
                left, right = (record, other) if record.stream == "reading" else (other, record)
                key = canonical([left.ingress_ordinal, right.ingress_ordinal])
                self.pending.append(
                    Delivery(
                        self.job_id,
                        "interval-join",
                        key,
                        1,
                        canonical(
                            {
                                "key": record.key,
                                "reading_ordinal": left.ingress_ordinal,
                                "metadata_ordinal": right.ingress_ordinal,
                                "value": left.value,
                                "metadata": right.payload,
                                "delta_ms": right.event_time - left.event_time,
                            }
                        ),
                    )
                )
        matches.append(record)
        self.join_count += 1

    def _expire(self) -> None:
        watermark = self.progress.watermark
        while self.close_heap and self.close_heap[0][0] <= watermark:
            _, identity = heapq.heappop(self.close_heap)
            window = self.state.get(identity)
            if window and window.dirty:
                self._emit(window)
        while self.expire_heap and self.expire_heap[0][0] < watermark:
            _, identity = heapq.heappop(self.expire_heap)
            self.state.pop(identity, None)
        for key in list(self.join):
            self.join_count -= len(self.join[key])
            self.join[key] = [
                r
                for r in self.join[key]
                if r.event_time + self.config.join_interval + self.config.lateness >= watermark
            ]
            self.join_count += len(self.join[key])
            if not self.join[key]:
                del self.join[key]

    def dump(self) -> str:
        return canonical(
            {
                "version": CODE_VERSION,
                "config": asdict(self.config),
                "job_id": self.job_id,
                "position": self.position,
                "watermarks": self.progress.inputs,
                "idle": sorted(self.progress.idle),
                "watermark": self.progress.watermark,
                "windows": {k: asdict(v) for k, v in self.state.items()},
                "join": {k: [asdict(r) for r in rows] for k, rows in self.join.items()},
                "dispositions": self.dispositions,
                "peak_state": self.peak_state,
                "max_watermark_lag": self.max_watermark_lag,
                "max_finalization_lag": self.max_finalization_lag,
            }
        )

    @classmethod
    def restore(cls, raw: str, config: Config) -> Engine:
        data = json.loads(raw)
        if data["version"] != CODE_VERSION or canonical(data["config"]) != canonical(
            asdict(config)
        ):
            raise ValueError("incompatible checkpoint/code/config version")
        engine = cls(config, data["job_id"])
        engine.position = data["position"]
        engine.progress = Progress(data["watermarks"], set(data["idle"]), data["watermark"])
        for key, w in data["windows"].items():
            engine.state[key] = Window(
                w["operator"],
                w["key"],
                w["start"],
                Aggregate(**w["aggregate"]),
                w["revision"],
                w["dirty"],
            )
        for key, window in engine.state.items():
            end = window.start + config.size
            if end > engine.progress.watermark:
                heapq.heappush(engine.close_heap, (end, key))
            heapq.heappush(engine.expire_heap, (end + config.lateness, key))
        engine.join = {k: [Record(**r) for r in rows] for k, rows in data["join"].items()}
        engine.join_count = sum(map(len, engine.join.values()))
        engine.dispositions = cast(dict[str, int], data["dispositions"])
        engine.peak_state = data["peak_state"]
        engine.max_watermark_lag = data["max_watermark_lag"]
        engine.max_finalization_lag = data["max_finalization_lag"]
        return engine

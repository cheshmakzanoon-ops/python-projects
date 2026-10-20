"""Deterministic ordered state machine. All effects are staged until checkpoint."""

from __future__ import annotations

import heapq
import json
from collections import deque
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from typing import cast

from pp_current.errors import BudgetExceeded
from pp_current.event_time.policy import MAX_TIME, MIN_TIME, Progress
from pp_current.model.envelope import Record, canonical
from pp_current.operators.tumbling import Aggregate, validate_windows, window_starts

CODE_VERSION = "current-3"


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
        for name in ("workers", "size", "slide", "lateness", "join_interval", "state_limit"):
            if type(getattr(self, name)) is not int:
                raise ValueError("integer configuration limits required")
        if not self.inputs or len(set(self.inputs)) != len(self.inputs):
            raise ValueError("unique registered inputs required")
        if any(not isinstance(identity, str) or not identity for identity in self.inputs):
            raise ValueError("nonempty string input identities required")
        if not isinstance(self.pipeline_version, str) or not self.pipeline_version:
            raise ValueError("nonempty pipeline version required")
        validate_windows(self.size, self.slide)
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
            any(
                not isinstance(identity, str)
                for identity in (self.job_id, self.operator_id, self.logical_result_key)
            )
            or not self.job_id
            or not self.operator_id
            or type(self.revision) is not int
            or self.revision < 1
        ):
            raise ValueError("invalid delivery identity")
        if not isinstance(self.payload, str) or canonical(json.loads(self.payload)) != self.payload:
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
        if not isinstance(job_id, str) or not job_id:
            raise ValueError("nonempty job identity required")
        self.config = config
        self.job_id = job_id
        self._identity = canonical([job_id, asdict(config)])
        self._checkpoint: str | None = None
        self._pending_limit: int | None = None
        self._failed = False
        self._running = False
        self.progress = Progress(dict.fromkeys(config.inputs, MIN_TIME))
        self.position = 0
        self.state: dict[str, Window] = {}
        self.join: dict[str, list[Record]] = {}
        self._join_index: dict[tuple[str, str, int], list[Record]] = {}
        self.join_candidates_examined = 0
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
        revision = window.revision + 1
        key = canonical([window.key, window.start, window.start + self.config.size])
        payload = canonical(
            {
                "key": window.key,
                "start": window.start,
                "end": window.start + self.config.size,
                **window.aggregate.result(),
            }
        )
        self._stage(Delivery(self.job_id, window.operator, key, revision, payload))
        window.revision = revision
        window.dirty = False

    def _stage(self, delivery: Delivery) -> None:
        if self._pending_limit is not None and len(self.pending) >= self._pending_limit:
            raise BudgetExceeded(
                "staged output budget reached: recover and adjust delivery capacity"
            )
        self.pending.append(delivery)

    def validate(self, record: Record) -> None:
        """Check ordered admission and input lifecycle before applying or filtering."""
        if record.ingress_ordinal != self.position + 1:
            raise ValueError("records must form a contiguous journal prefix")
        if record.input_id not in self.progress.inputs:
            raise ValueError("unknown input")
        if self.progress.inputs[record.input_id] == MAX_TIME and record.kind != "end":
            raise ValueError("input has ended")
        if record.kind == "event" and record.input_id in self.progress.idle:
            raise ValueError("explicit resume required before event")

    def ensure_usable(self) -> None:
        if self._failed:
            raise RuntimeError("engine failed: discard it and recover the durable checkpoint")

    def apply(self, record: Record, *, filtered: bool = False) -> str:
        self.ensure_usable()
        self.validate(record)
        try:
            return self._apply(record, filtered=filtered)
        except BaseException:
            self._failed = True
            raise

    def _apply(self, record: Record, *, filtered: bool) -> str:
        if filtered:
            if record.kind != "event":
                raise ValueError("control records cannot be filtered")
            self.position = record.ingress_ordinal
            self.trace.append((self.position, "filtered", self.progress.watermark))
            return "filtered"
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
        return disposition

    def _event(self, record: Record) -> None:
        if record.stream == "reading":
            for operator, slide in [("tumbling", self.config.size), ("sliding", self.config.slide)]:
                for start in window_starts(record.event_time, self.config.size, slide):
                    identity = canonical([operator, record.key, start])
                    if identity not in self.state:
                        self._reserve_state()
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
        for other in self._join_candidates(record):
            if abs(other.event_time - record.event_time) <= self.config.join_interval:
                left, right = (record, other) if record.stream == "reading" else (other, record)
                key = canonical([left.ingress_ordinal, right.ingress_ordinal])
                self._stage(
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
        self._reserve_state()
        self.join.setdefault(record.key, []).append(record)
        self._index_join(record)
        self.join_count += 1

    def _reserve_state(self) -> None:
        if len(self.state) + self.join_count >= self.config.state_limit:
            raise MemoryError("operator state limit reached: recover with an adequate state budget")

    def _index_join(self, record: Record) -> None:
        width = self.config.join_interval + 1
        identity = record.key, record.stream, record.event_time // width
        self._join_index.setdefault(identity, []).append(record)

    def _join_candidates(self, record: Record) -> Iterator[Record]:
        # Each bucket is already in ingress order. Merge at most three iterators
        # lazily, so a staging limit stops fanout without copying its candidate
        # history. Floor division also handles negative event times.
        interval = self.config.join_interval
        width = interval + 1
        opposite = "metadata" if record.stream == "reading" else "reading"
        buckets = (
            self._join_index.get((record.key, opposite, part), ())
            for part in range(
                (record.event_time - interval) // width, (record.event_time + interval) // width + 1
            )
        )
        for other in heapq.merge(*buckets, key=lambda other: other.ingress_ordinal):
            self.join_candidates_examined += 1
            yield other

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
        self._join_index.clear()
        self.join_count = 0
        retained: dict[str, list[Record]] = {}
        for key, records in self.join.items():
            kept = []
            for record in records:
                if (
                    record.event_time + self.config.join_interval + self.config.lateness
                    >= watermark
                ):
                    kept.append(record)
                    self._index_join(record)
            if kept:
                retained[key] = kept
                self.join_count += len(kept)
        self.join = retained

    def dump(self) -> str:
        self.ensure_usable()
        if canonical([self.job_id, asdict(self.config)]) != self._identity:
            raise RuntimeError(
                "job/config identity changed: recover with the original configuration"
            )
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
        """Restore a compatible, internally consistent committed state."""
        try:
            return cls._restore(raw, config)
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError("invalid checkpoint structure") from error

    @classmethod
    def _restore(cls, raw: str, config: Config) -> Engine:
        data = json.loads(raw)
        if data["version"] != CODE_VERSION:
            raise ValueError("incompatible checkpoint/code/config version")
        stored_config = Config(**data["config"])
        saved = asdict(stored_config)
        saved["state_limit"] = config.state_limit
        if canonical(saved) != canonical(asdict(config)):
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
        engine._validate_checkpoint()
        for records in engine.join.values():
            for record in records:
                engine._index_join(record)
        return engine

    def _validate_checkpoint(self) -> None:
        """Reject corrupt state instead of replaying from an invented processing prefix."""

        def integer(value: object, minimum: int = 0, maximum: int | None = None) -> bool:
            return type(value) is int and value >= minimum and (maximum is None or value <= maximum)

        if not integer(self.position, maximum=MAX_TIME):
            raise ValueError("invalid checkpoint position")
        progress = self.progress
        if set(progress.inputs) != set(self.config.inputs) or not progress.idle <= set(
            progress.inputs
        ):
            raise ValueError("invalid checkpoint input topology")
        if not integer(progress.watermark, MIN_TIME, MAX_TIME) or any(
            not integer(value, MIN_TIME, MAX_TIME) for value in progress.inputs.values()
        ):
            raise ValueError("invalid checkpoint watermarks")
        if (progress.watermark == MAX_TIME) != all(
            value == MAX_TIME for value in progress.inputs.values()
        ):
            raise ValueError(
                "premature terminal checkpoint: unfinished inputs require raw-ingress replay"
            )
        active = [
            value
            for identity, value in progress.inputs.items()
            if identity not in progress.idle and value != MAX_TIME
        ]
        if progress.watermark > max(progress.inputs.values()) or (
            active and progress.watermark < min(active)
        ):
            raise ValueError("inconsistent checkpoint watermarks")
        if any(progress.inputs[identity] == MAX_TIME for identity in progress.idle):
            raise ValueError("ended checkpoint input cannot be idle")
        if set(self.dispositions) != {"on-time", "accepted-late", "rejected-late"} or any(
            not integer(value) for value in self.dispositions.values()
        ):
            raise ValueError("invalid checkpoint dispositions")
        if sum(self.dispositions.values()) > self.position:
            raise ValueError("checkpoint dispositions exceed processing prefix")
        for identity, window in self.state.items():
            if (
                window.operator not in ("tumbling", "sliding")
                or not isinstance(window.key, str)
                or type(window.start) is not int
                or not integer(window.revision)
                or type(window.dirty) is not bool
                or identity != canonical([window.operator, window.key, window.start])
            ):
                raise ValueError("invalid checkpoint window identity")
            slide = self.config.size if window.operator == "tumbling" else self.config.slide
            end = window.start + self.config.size
            if window.start % slide or end + self.config.lateness < progress.watermark:
                raise ValueError("invalid checkpoint window lifetime")
            if (end > progress.watermark) != (window.revision == 0 and window.dirty):
                raise ValueError("inconsistent checkpoint window revision")
            if end <= progress.watermark and window.dirty:
                raise ValueError("unpublished checkpoint window")
            aggregate = window.aggregate
            if (
                not integer(aggregate.count, 1)
                or type(aggregate.total) is not int
                or type(aggregate.minimum) is not int
                or type(aggregate.maximum) is not int
                or not aggregate.minimum * aggregate.count
                <= aggregate.total
                <= aggregate.maximum * aggregate.count
                or aggregate.minimum > aggregate.maximum
            ):
                raise ValueError("invalid checkpoint aggregate")
        ordinals: set[int] = set()
        for key, records in self.join.items():
            if not records:
                raise ValueError("empty checkpoint join bucket")
            for record in records:
                if (
                    key != record.key
                    or record.kind != "event"
                    or record.input_id not in progress.inputs
                    or not 1 <= record.ingress_ordinal <= self.position
                    or record.ingress_ordinal in ordinals
                    or record.event_time + self.config.join_interval + self.config.lateness
                    < progress.watermark
                ):
                    raise ValueError("invalid checkpoint join record")
                ordinals.add(record.ingress_ordinal)
        retained = len(self.state) + self.join_count
        if (
            not integer(self.peak_state, retained)
            or retained > self.config.state_limit
            or not integer(self.max_watermark_lag)
            or not integer(self.max_finalization_lag)
        ):
            raise ValueError("invalid checkpoint resource metrics")

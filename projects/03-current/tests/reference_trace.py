"""Unindexed full-history model of the documented event-time and delivery contracts."""

from collections import Counter, defaultdict

from pp_current import Config, Delivery, Record, canonical


class TraceModel:
    """Retain all accepted records; recompute window aggregates and scan join history."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.clocks = dict.fromkeys(config.inputs, -(2**63))
        self.inactive: set[str] = set()
        self.finished: set[str] = set()
        self.watermark = -(2**63)
        self.accepted: list[Record] = []
        self.members: dict[tuple[str, str, int, int], list[int]] = defaultdict(list)
        self.revisions: Counter[tuple[str, str, int, int]] = Counter()
        self.dispositions: Counter[str] = Counter()

    def _window(self, key: tuple[str, str, int, int]) -> Delivery:
        operator, grouping, start, end = key
        samples = self.members[key]
        self.revisions[key] += 1
        return Delivery(
            "trace",
            operator,
            canonical([grouping, start, end]),
            self.revisions[key],
            canonical(
                {
                    "key": grouping,
                    "start": start,
                    "end": end,
                    "count": len(samples),
                    "sum": sum(samples),
                    "min": min(samples),
                    "max": max(samples),
                    "average": sum(samples) / len(samples),
                }
            ),
        )

    def apply(self, record: Record) -> tuple[str, list[Delivery]]:
        output = []
        source = record.input_id
        if record.kind != "event":
            if record.kind == "end":
                self.finished.add(source)
                self.inactive.discard(source)
            elif record.kind == "idle":
                self.inactive.add(source)
            elif record.kind == "resume":
                self.inactive.discard(source)
            else:
                self.clocks[source] = record.event_time
            running = [
                time
                for identity, time in self.clocks.items()
                if identity not in self.inactive | self.finished
            ]
            if len(self.finished) == len(self.clocks):
                self.watermark = 2**63 - 1
            elif running:
                self.watermark = max(self.watermark, min(running))
            for window in self.members:
                if window[3] <= self.watermark and not self.revisions[window]:
                    output.append(self._window(window))
            return record.kind, output
        status = (
            "on-time"
            if record.event_time >= self.watermark
            else "accepted-late"
            if record.event_time >= self.watermark - self.config.lateness
            else "rejected-late"
        )
        self.dispositions[status] += 1
        if status == "rejected-late":
            return status, output
        if record.stream == "reading":
            for operator, step in (("tumbling", self.config.size), ("sliding", self.config.slide)):
                for boundary in range(
                    (record.event_time - self.config.size) // step + 1,
                    record.event_time // step + 1,
                ):
                    start = boundary * step
                    window = operator, record.key, start, start + self.config.size
                    self.members[window].append(record.value)
                    if window[3] <= self.watermark:
                        output.append(self._window(window))
        for previous in self.accepted:
            if (
                previous.key == record.key
                and previous.stream != record.stream
                and previous.event_time
                >= self.watermark - self.config.join_interval - self.config.lateness
                and abs(previous.event_time - record.event_time) <= self.config.join_interval
            ):
                reading, metadata = (
                    (record, previous) if record.stream == "reading" else (previous, record)
                )
                output.append(
                    Delivery(
                        "trace",
                        "interval-join",
                        canonical([reading.ingress_ordinal, metadata.ingress_ordinal]),
                        1,
                        canonical(
                            {
                                "key": record.key,
                                "reading_ordinal": reading.ingress_ordinal,
                                "metadata_ordinal": metadata.ingress_ordinal,
                                "value": reading.value,
                                "metadata": metadata.payload,
                                "delta_ms": metadata.event_time - reading.event_time,
                            }
                        ),
                    )
                )
        self.accepted.append(record)
        return status, output

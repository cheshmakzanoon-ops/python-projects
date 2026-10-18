"""Bounded keyed preparation, ordered commit, and explicit checkpoint barriers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import Callable

from pp_current.ingress.journal import Journal
from pp_current.model.envelope import Record, partition_for
from pp_current.runtime.engine import Engine


@dataclass
class Metrics:
    queue_peak: int = 0
    blocked_puts: int = 0
    processed: int = 0


class Runtime:
    def __init__(
        self,
        journal: Journal,
        engine: Engine,
        *,
        capacity: int = 32,
        mapper: Callable[[int], int] = int,
        predicate: Callable[[Record], bool] = lambda _: True,
    ) -> None:
        if capacity < 1:
            raise ValueError("positive capacity required")
        self.journal = journal
        self.engine = engine
        self.capacity = capacity
        self.mapper = mapper
        self.predicate = predicate
        self.metrics = Metrics()

    async def run(self, *, checkpoint_interval: int = 1000) -> None:
        if checkpoint_interval < 1:
            raise ValueError("positive checkpoint interval required")
        queues: list[asyncio.Queue[tuple[Record, asyncio.Future[Record | None]] | None]] = [
            asyncio.Queue(self.capacity) for _ in range(self.engine.config.workers)
        ]

        async def worker(
            queue: asyncio.Queue[tuple[Record, asyncio.Future[Record | None]] | None],
        ) -> None:
            while (item := await queue.get()) is not None:
                record, future = item
                try:
                    result = record
                    if record.kind == "event":
                        mapped = self.mapper(record.value)
                        result = record if mapped == record.value else replace(record, value=mapped)
                        if not self.predicate(result):
                            # Filtered records still advance the durable ordered prefix.
                            future.set_result(None)
                            continue
                    future.set_result(result)
                except Exception as error:
                    future.set_exception(error)

        async with asyncio.TaskGroup() as group:
            for queue in queues:
                group.create_task(worker(queue))
            while True:
                records = await asyncio.to_thread(
                    self.journal.read, self.engine.position, self.capacity
                )
                if not records:
                    break
                futures = []
                for record in records:
                    future: asyncio.Future[Record | None] = (
                        asyncio.get_running_loop().create_future()
                    )
                    queue = queues[partition_for(record.key, len(queues))]
                    if queue.full():
                        self.metrics.blocked_puts += 1
                    await queue.put((record, future))
                    self.metrics.queue_peak = max(self.metrics.queue_peak, queue.qsize())
                    futures.append((record, future))
                for original, prepared in futures:
                    processed_record = await prepared
                    if processed_record is None:
                        self.engine.position = original.ingress_ordinal
                        self.engine.trace.append(
                            (original.ingress_ordinal, "filtered", self.engine.progress.watermark)
                        )
                    else:
                        self.engine.apply(processed_record)
                    self.metrics.processed += 1
                    if self.engine.position % checkpoint_interval == 0:
                        await asyncio.to_thread(self.journal.publish, self.engine)
            await asyncio.to_thread(self.journal.publish, self.engine)
            for queue in queues:
                await queue.put(None)

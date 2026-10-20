"""Bounded keyed preparation, ordered application, and settled SQLite barriers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import Callable, ParamSpec, TypeVar, cast

from pp_current.ingress.journal import Journal
from pp_current.model.envelope import Record, partition_for
from pp_current.runtime.engine import Engine

P = ParamSpec("P")
T = TypeVar("T")


async def _io(function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Cancellation cannot abandon a thread that still owns a SQLite transaction."""

    async def outcome() -> tuple[T | None, BaseException | None]:
        try:
            return await asyncio.to_thread(function, *args, **kwargs), None
        except BaseException as failure:
            # A cancelled shield may report its inner task's later exception to
            # the loop even when another await retrieves it (Python 3.14). Keep
            # the shielded task successful; propagate its failure after settling.
            return None, failure

    operation = asyncio.create_task(outcome())
    cancellation: asyncio.CancelledError | None = None
    try:
        value, failure = await asyncio.shield(operation)
    except asyncio.CancelledError as cancelled:
        cancellation = cancelled
        # Cancelling an executor future does not stop its thread. Keep waiting,
        # including through repeated cancellation requests, before giving the
        # caller permission to close/recover the journal connection.
        while not operation.done():
            try:
                await asyncio.shield(operation)
            except asyncio.CancelledError:
                continue
        value, failure = operation.result()
    if cancellation is not None:
        if failure is not None:
            raise cancellation from failure
        raise cancellation
    if failure is not None:
        raise failure
    return cast(T, value)


@dataclass
class Metrics:
    queue_peak: int = 0
    blocked_puts: int = 0
    processed: int = 0


@dataclass(frozen=True)
class _Prepared:
    record: Record | None = None
    error: BaseException | None = None


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
        if type(capacity) is not int or capacity < 1:
            raise ValueError("positive capacity required")
        self.journal = journal
        self.engine = engine
        self.engine._pending_limit = journal.max_outbox
        self.capacity = capacity
        self.mapper = mapper
        self.predicate = predicate
        self.metrics = Metrics()

    def _prepare(self, record: Record) -> _Prepared:
        try:
            if record.kind != "event":
                return _Prepared(record)
            mapped = self.mapper(record.value)
            if type(mapped) is not int:
                raise ValueError("mapper must return an integer")
            prepared = record if mapped == record.value else replace(record, value=mapped)
            return _Prepared(prepared if self.predicate(prepared) else None)
        except BaseException as error:
            # Exceptions are ordered result values, not failed futures whose
            # unobserved errors would leak when an earlier record aborts a batch.
            return _Prepared(error=error)

    async def run(self, *, checkpoint_interval: int = 1000) -> None:
        if type(checkpoint_interval) is not int or checkpoint_interval < 1:
            raise ValueError("positive checkpoint interval required")
        self.engine.ensure_usable()
        if self.engine._running:
            raise RuntimeError("engine already has an active runtime owner")
        self.engine._running = True
        try:
            await self._run(checkpoint_interval)
        except BaseException:
            self.engine._failed = True
            raise
        finally:
            self.engine._running = False

    async def _run(self, checkpoint_interval: int) -> None:
        queues: list[asyncio.Queue[tuple[Record, asyncio.Future[_Prepared]] | None]] = [
            asyncio.Queue(self.capacity) for _ in range(self.engine.config.workers)
        ]

        async def worker(
            queue: asyncio.Queue[tuple[Record, asyncio.Future[_Prepared]] | None],
        ) -> None:
            while (item := await queue.get()) is not None:
                record, future = item
                if not future.done():
                    future.set_result(self._prepare(record))

        async with asyncio.TaskGroup() as group:
            for queue in queues:
                group.create_task(worker(queue))
            while True:
                records = await _io(self.journal.read, self.engine.position, self.capacity)
                if not records:
                    break
                futures = []
                for record in records:
                    future: asyncio.Future[_Prepared] = asyncio.get_running_loop().create_future()
                    queue = queues[partition_for(record.key, len(queues))]
                    if queue.full():
                        self.metrics.blocked_puts += 1
                    await queue.put((record, future))
                    self.metrics.queue_peak = max(self.metrics.queue_peak, queue.qsize())
                    futures.append((record, future))
                for original, prepared in futures:
                    outcome = await prepared
                    if outcome.error is not None:
                        raise outcome.error
                    if outcome.record is None:
                        self.engine.apply(original, filtered=True)
                    else:
                        self.engine.apply(outcome.record)
                    self.metrics.processed += 1
                    if self.engine.position % checkpoint_interval == 0:
                        await _io(self.journal.publish, self.engine)
            await _io(self.journal.publish, self.engine)
            for queue in queues:
                await queue.put(None)

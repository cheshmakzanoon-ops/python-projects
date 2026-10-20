"""Deterministic interleavings around state ownership and SQLite publication."""

import asyncio
import gc
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from pp_current import Config, Journal, Record, Runtime, canonical

INPUT = canonical(["s", 0])
CONFIG = Config((INPUT,), size=10, slide=5, lateness=5)


@pytest.mark.parametrize("different_job", [False, True])
def test_stale_owner_cannot_rewind_a_committed_prefix(tmp_path: Path, different_job: bool) -> None:
    path = tmp_path / "owners.db"
    writer = Journal(path)
    contender = Journal(path)
    try:
        writer.admit([Record("s", 0, 0, 1, value=7), Record("s", 0, 1, 10, kind="watermark")])
        fresh = writer.recover(CONFIG, job_id="current-job")
        stale = contender.recover(CONFIG, job_id="other-job" if different_job else "current-job")
        for record in writer.read(0):
            fresh.apply(record)
        writer.publish(fresh)
        expected = writer.export()
        stale.apply(contender.read(0, 1)[0])
        with pytest.raises(RuntimeError, match="checkpoint"):
            contender.publish(stale)
        assert writer.recover(CONFIG, job_id="current-job").position == 2
        assert writer.export() == expected
    finally:
        contender.close()
        writer.close()


def test_acknowledgement_never_joins_an_uncommitted_checkpoint_transaction(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "ack.db")
    engine = journal.recover(CONFIG)
    for record in journal.admit(
        [Record("s", 0, 0, 1, value=7), Record("s", 0, 1, 10, kind="watermark")]
    ):
        engine.apply(record)
    journal.publish(engine)
    delivery = journal.pending(1)[0]
    staged, release, acknowledged = threading.Event(), threading.Event(), threading.Event()

    def fail(point: str) -> None:
        if point == "checkpoint-before-publication":
            staged.set()
            if not release.wait(5):
                raise TimeoutError("test release was not signalled")
            raise OSError("checkpoint rollback")

    def acknowledge() -> None:
        journal.acknowledge(delivery)
        acknowledged.set()

    journal.failpoint = fail
    try:
        with ThreadPoolExecutor(max_workers=2) as threads:
            publication = threads.submit(journal.publish, engine)
            assert staged.wait(5)
            ack = threads.submit(acknowledge)
            escaped = acknowledged.wait(0.05)
            release.set()
            with pytest.raises(OSError, match="rollback"):
                publication.result(5)
            ack.result(5)
        assert not escaped, "acknowledgement escaped while its SQL update could still roll back"
        assert delivery not in journal.pending()
    finally:
        release.set()
        journal.close()


def test_cancel_waits_for_the_sqlite_operation_to_settle_before_returning(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "cancel.db")
    journal.admit([Record("s", 0, 0, 1, value=7), Record("s", 0, 1, kind="end")])
    staged, release, committed = threading.Event(), threading.Event(), threading.Event()

    def pause(point: str) -> None:
        if point == "checkpoint-before-publication":
            staged.set()
            if not release.wait(5):
                raise TimeoutError("test release was not signalled")
        elif point == "checkpoint-after-publication":
            committed.set()

    journal.failpoint = pause

    async def scenario() -> None:
        task = asyncio.create_task(Runtime(journal, journal.recover(CONFIG)).run())
        try:
            for _ in range(1000):
                if staged.is_set():
                    break
                await asyncio.sleep(0.001)
            assert staged.is_set()
            task.cancel()
            await asyncio.sleep(0.02)
            escaped = task.done()
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert await asyncio.to_thread(committed.wait, 5)
        assert not escaped, "Runtime returned while its publication thread was still running"

    try:
        asyncio.run(scenario())
        journal.failpoint = lambda _: None
        assert journal.recover(CONFIG).position == 2
    finally:
        release.set()
        journal.close()


@pytest.mark.parametrize(
    "failure", ["checkpoint-before-publication", "checkpoint-after-publication"]
)
def test_cancelled_failed_publication_is_observed_after_settlement(
    tmp_path: Path, failure: str
) -> None:
    journal = Journal(tmp_path / "cancel-failure.db")
    journal.admit([Record("s", 0, 0, 1, value=7), Record("s", 0, 1, kind="end")])
    staged, release = threading.Event(), threading.Event()
    errors: list[dict[str, object]] = []

    def pause(point: str) -> None:
        if point == failure:
            staged.set()
            if not release.wait(5):
                raise TimeoutError("test release was not signalled")
            raise OSError("publication failed during cancellation")

    journal.failpoint = pause

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(lambda _, context: errors.append(context))
        task = asyncio.create_task(Runtime(journal, journal.recover(CONFIG)).run())
        try:
            for _ in range(1000):
                if staged.is_set():
                    break
                await asyncio.sleep(0.001)
            assert staged.is_set()
            for _ in range(8):
                task.cancel()
                await asyncio.sleep(0.001)
                assert not task.done(), "cancellation returned before the database settled"
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError) as cancellation:
                await task
            assert isinstance(cancellation.value.__cause__, OSError)
        gc.collect()
        await asyncio.sleep(0)
        assert not errors, errors

    try:
        asyncio.run(scenario())
        journal.failpoint = lambda _: None
        committed = failure == "checkpoint-after-publication"
        assert journal.recover(CONFIG).position == (2 if committed else 0)
    finally:
        release.set()
        journal.close()


def test_many_mapper_failures_propagate_without_unobserved_future_errors(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "callbacks.db")
    journal.admit([Record("s", 0, offset) for offset in range(4)])
    errors: list[dict[str, object]] = []

    def broken(value: int) -> int:
        raise ValueError("mapping failed")

    async def scenario() -> None:
        asyncio.get_running_loop().set_exception_handler(lambda _, context: errors.append(context))
        runtime = Runtime(journal, journal.recover(CONFIG), mapper=broken)
        with pytest.raises(ExceptionGroup, match="TaskGroup"):
            await runtime.run()
        gc.collect()
        await asyncio.sleep(0)

    try:
        asyncio.run(scenario())
        assert journal.recover(CONFIG).position == 0
        assert not errors, errors
    finally:
        journal.close()


def test_cancelled_mapper_aborts_without_hanging_an_ordered_future(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "mapper-cancel.db")
    journal.admit([Record("s", 0, 0)])

    def cancel(value: int) -> int:
        raise asyncio.CancelledError("mapper cancelled")

    async def scenario() -> None:
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(
                Runtime(journal, journal.recover(CONFIG), mapper=cancel).run(), timeout=1
            )

    try:
        asyncio.run(scenario())
        assert journal.recover(CONFIG).position == 0
    finally:
        journal.close()


def test_fanout_backpressure_bounds_staging_and_requires_fresh_recovery(tmp_path: Path) -> None:
    from pp_current import BudgetExceeded

    path = tmp_path / "fanout.db"
    journal = Journal(path, max_outbox=5)
    records = [Record("s", 0, offset, 1, "hot", offset) for offset in range(10)]
    records.extend(
        [Record("s", 0, 10, 1, "hot", stream="metadata"), Record("s", 0, 11, kind="end")]
    )
    journal.admit(records)
    engine = journal.recover(CONFIG)
    runtime = Runtime(journal, engine)
    try:
        with pytest.raises(ExceptionGroup) as raised:
            asyncio.run(runtime.run())
        assert any(isinstance(error, BudgetExceeded) for error in raised.value.exceptions)
        assert len(engine.pending) <= 5
        assert engine.join_candidates_examined <= 6  # stop at the first unstaged pair
        assert journal.pending() == []
        assert journal.recover(CONFIG).position == 0
        with pytest.raises(RuntimeError, match="recover"):
            journal.publish(engine)
        with pytest.raises(RuntimeError, match="recover"):
            asyncio.run(runtime.run())
    finally:
        journal.close()
    with_recovery = Journal(path, max_outbox=20)
    try:
        asyncio.run(Runtime(with_recovery, with_recovery.recover(CONFIG)).run())
        assert with_recovery.recover(CONFIG).position == len(records)
        assert len(with_recovery.pending()) == 13  # ten pairs; one tumbling and two sliding windows
    finally:
        with_recovery.close()

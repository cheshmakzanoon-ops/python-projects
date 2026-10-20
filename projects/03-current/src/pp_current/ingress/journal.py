"""SQLite FULL-synchronous admission and atomic checkpoint/outbox publication."""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import replace
from functools import wraps
from pathlib import Path
from typing import Callable, Concatenate, ParamSpec, TypeVar

from pp_current.errors import BudgetExceeded, CheckpointConflict
from pp_current.ingress.schema import STATEMENTS
from pp_current.ingress.schema import validate as validate_schema
from pp_current.model.envelope import Record
from pp_current.runtime.engine import Config, Delivery, Engine

Failpoint = Callable[[str], None]
_BUSY_TIMEOUT = 10.0


def no_failure(point: str) -> None:
    pass


P = ParamSpec("P")
T = TypeVar("T")


def serialized(
    method: Callable[Concatenate["Journal", P], T],
) -> Callable[Concatenate["Journal", P], T]:
    """Keep one connection's readers and acknowledgements outside writer transactions."""

    @wraps(method)
    def call(self: Journal, /, *args: P.args, **kwargs: P.kwargs) -> T:
        with self._lock:
            return method(self, *args, **kwargs)

    return call


class Journal:
    def __init__(
        self,
        path: Path,
        *,
        max_records: int = 2_000_000,
        max_outbox: int = 2_000_000,
        max_disk_bytes: int = 1_073_741_824,
        failpoint: Failpoint = no_failure,
        read_only: bool = False,
    ) -> None:
        for limit in (max_records, max_outbox, max_disk_bytes):
            if type(limit) is not int or limit < 0:
                raise ValueError("nonnegative integer journal budgets required")
        if max_disk_bytes < 40960:
            raise ValueError("disk budget must allow at least ten pages")
        self._lock = threading.RLock()
        self.max_records = max_records
        self.max_outbox = max_outbox
        self.failpoint = failpoint
        self.replayed = 0
        self.checkpoint_seconds: list[float] = []
        if read_only:
            self.db = sqlite3.connect(
                path.resolve().as_uri() + "?mode=ro",
                uri=True,
                isolation_level=None,
                check_same_thread=False,
                timeout=_BUSY_TIMEOUT,
            )
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(
                path, isolation_level=None, check_same_thread=False, timeout=_BUSY_TIMEOUT
            )
        try:
            self._validate_format(allow_empty=not read_only)
            if not read_only:
                self._initialize(max_disk_bytes)
        except BaseException:
            self.db.close()
            raise

    def _validate_format(self, *, allow_empty: bool) -> bool:
        """Recognize the journal before changing pragmas or creating any tables."""
        return validate_schema(self.db, allow_empty=allow_empty)

    def _initialize(self, max_disk_bytes: int) -> None:
        # SQLite's journal-mode transition can report BUSY without invoking its
        # normal busy handler when two empty-file initializers race. Retry only
        # that transient condition, within the connection's bounded wait budget.
        deadline = time.monotonic() + _BUSY_TIMEOUT
        while True:
            try:
                self.db.execute("PRAGMA journal_mode=WAL")
                break
            except sqlite3.OperationalError as error:
                remaining = deadline - time.monotonic()
                if (
                    getattr(error, "sqlite_errorcode", 0) & 0xFF != sqlite3.SQLITE_BUSY
                    or remaining <= 0
                ):
                    raise
                time.sleep(min(0.01, remaining))
        self.db.execute("PRAGMA synchronous=FULL")
        page_size = self.db.execute("PRAGMA page_size").fetchone()[0]
        self.db.execute(f"PRAGMA max_page_count={max_disk_bytes // page_size}")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            # Another initializer may have completed after our first read.
            if not self._validate_format(allow_empty=True):
                for statement in STATEMENTS:
                    self.db.execute(statement)
                self.db.execute("INSERT INTO format VALUES(1)")
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    @serialized
    def close(self) -> None:
        self.db.close()

    @serialized
    def admit(self, records: list[Record]) -> list[Record]:
        admitted = []
        replayed = 0
        self.db.execute("BEGIN IMMEDIATE")
        try:
            count = self.db.execute("SELECT COUNT(*) FROM ingress").fetchone()[0]
            for record in records:
                old = self.db.execute(
                    "SELECT ordinal,wire FROM ingress WHERE source=? AND partition=? AND offset=?",
                    (record.source_id, record.partition, record.source_offset),
                ).fetchone()
                if old:
                    if old[1] != record.wire():
                        raise ValueError("conflicting source-offset reuse")
                    ordinal = old[0]
                    replayed += 1
                else:
                    if count >= self.max_records:
                        raise BudgetExceeded("durable ingress record budget reached")
                    cursor = self.db.execute(
                        "INSERT INTO ingress(source,partition,offset,wire) VALUES(?,?,?,?)",
                        (record.source_id, record.partition, record.source_offset, record.wire()),
                    )
                    ordinal = cursor.lastrowid
                    assert ordinal is not None
                    count += 1
                admitted.append(replace(record, ingress_ordinal=ordinal))
            self.failpoint("admission-before-commit")
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise
        self.replayed += replayed
        self.failpoint("admission-after-commit")
        return admitted

    @staticmethod
    def _validate_cursor(after: int, limit: int) -> None:
        if type(after) is not int or not 0 <= after < 2**63:
            raise ValueError("nonnegative integer journal cursor required")
        if type(limit) is not int or not 1 <= limit < 2**63:
            raise ValueError("positive integer page limit required")

    @serialized
    def read(self, after: int, limit: int = 1000) -> list[Record]:
        self._validate_cursor(after, limit)
        rows = self.db.execute(
            "SELECT ordinal,wire FROM ingress WHERE ordinal>? ORDER BY ordinal LIMIT ?",
            (after, limit),
        ).fetchall()
        return [Record.parse(raw, ordinal=ordinal) for ordinal, raw in rows]

    @serialized
    def recover(self, config: Config, job_id: str | None = None) -> Engine:
        row = self.db.execute("SELECT position,state FROM checkpoint WHERE id=1").fetchone()
        if row:
            engine = Engine.restore(row[1], config)
            last_ordinal = self.db.execute(
                "SELECT COALESCE(MAX(ordinal),0) FROM ingress"
            ).fetchone()[0]
            if (
                type(row[0]) is not int
                or row[0] != engine.position
                or engine.position > last_ordinal
            ):
                raise ValueError("checkpoint position does not match durable ingress")
            if job_id is not None and engine.job_id != job_id:
                raise ValueError("checkpoint belongs to a different job")
            engine._checkpoint = row[1]
            engine._pending_limit = self.max_outbox
            return engine
        engine = Engine(config, "demo" if job_id is None else job_id)
        engine._pending_limit = self.max_outbox
        return engine

    @serialized
    def publish(self, engine: Engine) -> None:
        started = time.perf_counter()
        self.failpoint("checkpoint-before-stage")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current = self.db.execute("SELECT position,state FROM checkpoint WHERE id=1").fetchone()
            expected = current[1] if current else None
            if engine._checkpoint != expected or (current and engine.position < current[0]):
                raise CheckpointConflict("checkpoint changed: discard the stale engine and recover")
            last = self.db.execute("SELECT COALESCE(MAX(ordinal),0) FROM ingress").fetchone()[0]
            if not 0 <= engine.position <= last:
                raise ValueError("checkpoint position exceeds durable ingress")
            unsent = self.db.execute("SELECT COUNT(*) FROM deliveries WHERE sent=0").fetchone()[0]
            if unsent + len(engine.pending) > self.max_outbox:
                raise BudgetExceeded("outbox budget reached: drain sink before checkpoint retry")
            if any(delivery.job_id != engine.job_id for delivery in engine.pending):
                raise ValueError("checkpoint outbox contains a different job")
            state = engine.dump()
            self.db.execute(
                "INSERT OR REPLACE INTO checkpoint VALUES(1,?,?)", (engine.position, state)
            )
            self.failpoint("checkpoint-during-stage")
            for delivery in engine.pending:
                self._insert(delivery)
            self.failpoint("checkpoint-before-publication")
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise
        engine._checkpoint = state
        self.checkpoint_seconds.append(time.perf_counter() - started)
        engine.pending.clear()
        self.failpoint("checkpoint-after-publication")

    def _insert(self, d: Delivery) -> None:
        old = self.db.execute(
            "SELECT payload FROM deliveries WHERE job=? AND operator=? AND key=? AND revision=?",
            d.identity,
        ).fetchone()
        if old and old[0] != d.payload:
            raise ValueError("conflicting delivery revision")
        self.db.execute(
            "INSERT OR IGNORE INTO deliveries(job,operator,key,revision,payload) VALUES(?,?,?,?,?)",
            (*d.identity, d.payload),
        )
        self.db.execute(
            """INSERT INTO results VALUES(?,?,?,?,?) ON CONFLICT(job,operator,key)
          DO UPDATE SET revision=excluded.revision,payload=excluded.payload
          WHERE excluded.revision>results.revision""",
            (*d.identity, d.payload),
        )

    @serialized
    def pending(self, limit: int = 100) -> list[Delivery]:
        self._validate_cursor(0, limit)
        return [
            Delivery(*row)
            for row in self.db.execute(
                "SELECT job,operator,key,revision,payload FROM deliveries WHERE sent=0 ORDER BY rowid LIMIT ?",
                (limit,),
            )
        ]

    @serialized
    def acknowledge(self, delivery: Delivery) -> None:
        cursor = self.db.execute(
            "UPDATE deliveries SET sent=1 WHERE job=? AND operator=? AND key=? AND revision=? AND payload=?",
            (*delivery.identity, delivery.payload),
        )
        if cursor.rowcount != 1:
            raise ValueError("unknown delivery or conflicting acknowledgement payload")

    @serialized
    def export(self) -> list[dict[str, object]]:
        import json

        return [
            {
                "job_id": job,
                "operator_id": operator,
                "logical_result_key": key,
                "revision": revision,
                "payload": json.loads(payload),
            }
            for job, operator, key, revision, payload in self.db.execute(
                "SELECT job,operator,key,revision,payload FROM results ORDER BY job,operator,key"
            )
        ]

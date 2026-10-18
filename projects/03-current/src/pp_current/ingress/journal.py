"""SQLite FULL-synchronous admission and atomic checkpoint/outbox publication."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable

from pp_current.model.envelope import Record
from pp_current.runtime.engine import Config, Delivery, Engine

Failpoint = Callable[[str], None]


def no_failure(point: str) -> None:
    pass


class BudgetExceeded(RuntimeError):
    """An admission or output budget has been reached; caller must back off."""


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
                timeout=10,
            )
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(
                path, isolation_level=None, check_same_thread=False, timeout=10
            )
        try:
            if not read_only:
                self._initialize(max_disk_bytes)
            if self.db.execute("SELECT version FROM format").fetchall() != [(1,)]:
                raise ValueError("unsupported journal format")
        except BaseException:
            self.db.close()
            raise

    def _initialize(self, max_disk_bytes: int) -> None:
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute(f"PRAGMA max_page_count={max_disk_bytes // 4096}")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS format(version INTEGER NOT NULL);
        INSERT INTO format SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM format);
        CREATE TABLE IF NOT EXISTS ingress(ordinal INTEGER PRIMARY KEY, source TEXT NOT NULL,
          partition INTEGER NOT NULL, offset INTEGER NOT NULL, wire TEXT NOT NULL,
          UNIQUE(source,partition,offset));
        CREATE TABLE IF NOT EXISTS checkpoint(id INTEGER PRIMARY KEY CHECK(id=1),
          position INTEGER NOT NULL, state TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS deliveries(job TEXT,operator TEXT,key TEXT,revision INTEGER,
          payload TEXT NOT NULL,sent INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(job,operator,key,revision));
        CREATE TABLE IF NOT EXISTS results(job TEXT,operator TEXT,key TEXT,revision INTEGER,
          payload TEXT NOT NULL,PRIMARY KEY(job,operator,key));
        """)

    def close(self) -> None:
        self.db.close()

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

    def read(self, after: int, limit: int = 1000) -> list[Record]:
        rows = self.db.execute(
            "SELECT ordinal,wire FROM ingress WHERE ordinal>? ORDER BY ordinal LIMIT ?",
            (after, limit),
        ).fetchall()
        return [Record.parse(raw, ordinal=ordinal) for ordinal, raw in rows]

    def recover(self, config: Config, job_id: str | None = None) -> Engine:
        row = self.db.execute("SELECT state FROM checkpoint WHERE id=1").fetchone()
        if row:
            engine = Engine.restore(row[0], config)
            if job_id is not None and engine.job_id != job_id:
                raise ValueError("checkpoint belongs to a different job")
            return engine
        return Engine(config, "demo" if job_id is None else job_id)

    def publish(self, engine: Engine) -> None:
        started = time.perf_counter()
        self.failpoint("checkpoint-before-stage")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            unsent = self.db.execute("SELECT COUNT(*) FROM deliveries WHERE sent=0").fetchone()[0]
            if unsent + len(engine.pending) > self.max_outbox:
                raise BudgetExceeded("outbox budget reached: drain sink before checkpoint retry")
            self.db.execute(
                "INSERT OR REPLACE INTO checkpoint VALUES(1,?,?)", (engine.position, engine.dump())
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

    def pending(self, limit: int = 100) -> list[Delivery]:
        return [
            Delivery(*row)
            for row in self.db.execute(
                "SELECT job,operator,key,revision,payload FROM deliveries WHERE sent=0 ORDER BY rowid LIMIT ?",
                (limit,),
            )
        ]

    def acknowledge(self, delivery: Delivery) -> None:
        cursor = self.db.execute(
            "UPDATE deliveries SET sent=1 WHERE job=? AND operator=? AND key=? AND revision=? AND payload=?",
            (*delivery.identity, delivery.payload),
        )
        if cursor.rowcount != 1:
            raise ValueError("unknown delivery or conflicting acknowledgement payload")

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

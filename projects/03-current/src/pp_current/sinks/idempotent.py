"""Independent SQLite sink: immutable delivery identities and greatest-revision view."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pp_current.runtime.engine import Delivery


class IdempotentSink:
    def __init__(self, path: Path) -> None:
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""CREATE TABLE IF NOT EXISTS seen(job TEXT,operator TEXT,key TEXT,
          revision INTEGER,payload TEXT,PRIMARY KEY(job,operator,key,revision));
          CREATE TABLE IF NOT EXISTS latest(job TEXT,operator TEXT,key TEXT,revision INTEGER,
          payload TEXT,PRIMARY KEY(job,operator,key));""")

    def put(self, d: Delivery) -> None:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            prior = self.db.execute(
                "SELECT payload FROM seen WHERE job=? AND operator=? AND key=? AND revision=?",
                d.identity,
            ).fetchone()
            if prior and prior[0] != d.payload:
                raise ValueError("conflicting immutable delivery identity")
            self.db.execute(
                "INSERT OR IGNORE INTO seen VALUES(?,?,?,?,?)", (*d.identity, d.payload)
            )
            self.db.execute(
                """INSERT INTO latest VALUES(?,?,?,?,?) ON CONFLICT(job,operator,key)
              DO UPDATE SET revision=excluded.revision,payload=excluded.payload
              WHERE excluded.revision>latest.revision""",
                (*d.identity, d.payload),
            )
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def close(self) -> None:
        self.db.close()

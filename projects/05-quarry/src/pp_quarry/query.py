"""Explicit pinned manifests: directory globs are never analytical inputs."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb

from pp_quarry.storage.catalog import connect
from pp_quarry.storage.files import literal


class Snapshot:
    def __init__(self, root: str | Path, snapshot: int | None = None) -> None:
        self.root = Path(root).resolve()
        self.db = connect(self.root)
        self.token = uuid.uuid4().hex
        self.closed = False
        self.db.execute("BEGIN IMMEDIATE")
        row = (
            self.db.execute("SELECT id,manifest FROM snapshots WHERE id=?", (snapshot,)).fetchone()
            if snapshot is not None
            else self.db.execute(
                "SELECT id,manifest FROM snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
        )
        if row is None:
            self.db.rollback()
            self.db.close()
            raise ValueError("snapshot does not exist")
        self.id: int = row[0]
        self.manifest: dict[str, Any] = json.loads(row[1])
        self.db.execute("INSERT INTO pins VALUES (?,?)", (self.token, self.id))
        self.db.commit()

    def rows(self, node: str = "facts", limit: int | None = None) -> Iterator[dict[str, Any]]:
        if self.closed:
            raise ValueError("snapshot handle is closed")
        if node not in {"normalized", "facts", "daily"} or (limit is not None and limit < 0):
            raise ValueError("unknown node or invalid limit")
        paths = [
            str(self.root / nodes[node]["path"]) for nodes in self.manifest["partitions"].values()
        ]
        with duckdb.connect() as engine:
            settings = self.manifest.get("execution_settings", {"threads": 1, "memory_mb": 128})
            engine.execute(f"SET threads={int(settings['threads'])}")
            engine.execute(f"SET memory_limit='{int(settings['memory_mb'])}MB'")
            engine.execute(f"SET temp_directory={literal(str(self.root / 'tmp'))}")
            if node == "daily":
                sql = 'SELECT "day",sum(count)::BIGINT count,sum(total) total FROM read_parquet(?) GROUP BY "day" ORDER BY "day"'
            else:
                sql = "SELECT * FROM read_parquet(?) ORDER BY namespace,key"
            if limit is not None:
                sql += f" LIMIT {limit}"
            cursor = engine.execute(sql, [paths])
            columns = [d[0] for d in cursor.description]
            while batch := cursor.fetchmany(1024):
                for row in batch:
                    yield dict(zip(columns, row, strict=True))

    def close(self) -> None:
        if not self.closed:
            self.db.execute("DELETE FROM pins WHERE token=?", (self.token,))
            self.db.commit()
            self.db.close()
            self.closed = True

    def __enter__(self) -> Snapshot:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

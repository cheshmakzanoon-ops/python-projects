"""Explicit pinned manifests: directory globs are never analytical inputs."""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any
from weakref import WeakValueDictionary

from pp_quarry.execution.analytics import DAILY_AGGREGATE, analytical_session, check_daily_totals
from pp_quarry.storage.catalog import connect, read_format
from pp_quarry.storage.files import verify_entry
from pp_quarry.storage.manifest import validate_manifest


class Snapshot:
    def __init__(self, root: str | Path, snapshot: int | None = None) -> None:
        self.root = Path(root).resolve()
        self.db = connect(self.root, initialize=False)
        self.token = uuid.uuid4().hex
        self.closed = False
        self._readers: WeakValueDictionary[str, Generator[dict[str, Any], None, None]] = (
            WeakValueDictionary()
        )
        try:
            self.db.execute("BEGIN IMMEDIATE")
            row = (
                self.db.execute(
                    "SELECT id,manifest FROM snapshots WHERE id=?", (snapshot,)
                ).fetchone()
                if snapshot is not None
                else self.db.execute(
                    "SELECT id,manifest FROM snapshots ORDER BY id DESC LIMIT 1"
                ).fetchone()
            )
            if row is None:
                raise ValueError("snapshot does not exist")
            stored = read_format(self.db)
            if stored is None:
                raise ValueError("snapshot requires stored dataset format")
            self._buckets: int = stored["config"]["buckets"]
            self.id: int = row[0]
            self.manifest = validate_manifest(json.loads(row[1]), self._buckets)
            self.db.execute("INSERT INTO pins VALUES (?,?)", (self.token, self.id))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            self.db.close()
            raise

    def rows(
        self, node: str = "facts", limit: int | None = None
    ) -> Generator[dict[str, Any], None, None]:
        if self.closed:
            raise ValueError("snapshot handle is closed")
        if node not in {"normalized", "facts", "daily"} or (
            limit is not None and (type(limit) is not int or limit < 0)
        ):
            raise ValueError("unknown node or invalid limit")
        token = uuid.uuid4().hex
        reader = self._rows(node, limit, token)
        self._readers[token] = reader
        return reader

    def _rows(
        self, node: str, limit: int | None, token: str
    ) -> Generator[dict[str, Any], None, None]:
        try:
            validate_manifest(self.manifest, self._buckets)
            paths = [
                str(verify_entry(self.root, nodes[node]))
                for nodes in self.manifest["partitions"].values()
            ]
            settings = self.manifest.get("execution_settings", {"threads": 1, "memory_mb": 128})
            with analytical_session(self.root, **settings) as engine:
                if node == "daily":
                    check_daily_totals(engine, paths)
                    sql = DAILY_AGGREGATE + ' ORDER BY "day"'
                else:
                    sql = "SELECT * FROM read_parquet(?) ORDER BY namespace,key"
                if limit is not None:
                    sql += f" LIMIT {limit}"
                cursor = engine.execute(sql, [paths])
                columns = [d[0] for d in cursor.description]
                while batch := cursor.fetchmany(1024):
                    for row in batch:
                        yield dict(zip(columns, row, strict=True))
        finally:
            self._readers.pop(token, None)

    def close(self) -> None:
        if not self.closed:
            # Stop all live queries and release their file descriptors before
            # unregistering the pin that protects those files from reclamation.
            for reader in tuple(self._readers.values()):
                reader.close()
            self._readers.clear()
            self.db.execute("DELETE FROM pins WHERE token=?", (self.token,))
            self.db.commit()
            self.db.close()
            self.closed = True

    def __enter__(self) -> Snapshot:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

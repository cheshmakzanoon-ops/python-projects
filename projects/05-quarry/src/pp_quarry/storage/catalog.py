"""SQLite authoritative catalog. Single writer; immutable snapshot manifests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DDL = """
CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS identities(namespace TEXT,key TEXT,version INTEGER,fingerprint TEXT NOT NULL,payload TEXT NOT NULL,operation TEXT NOT NULL,source TEXT NOT NULL,offset INTEGER NOT NULL,PRIMARY KEY(namespace,key,version));
CREATE TABLE IF NOT EXISTS latest(namespace TEXT,key TEXT,version INTEGER,operation TEXT,payload TEXT,fingerprint TEXT,bucket INTEGER,source TEXT,offset INTEGER,PRIMARY KEY(namespace,key));
CREATE INDEX IF NOT EXISTS latest_bucket ON latest(bucket,namespace,key);
CREATE TABLE IF NOT EXISTS sources(hash TEXT PRIMARY KEY,path TEXT,offset INTEGER,events INTEGER,snapshot INTEGER);
CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,manifest TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS pins(token TEXT PRIMARY KEY,snapshot INTEGER NOT NULL);
"""


def read_format(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute("SELECT value FROM config WHERE key='format'").fetchone()
    if row is None:
        return None
    stored = json.loads(row[0])
    if (
        not isinstance(stored, dict)
        or type(stored.get("format_version")) is not int
        or stored["format_version"] != 1
        or stored.get("bucket_hash") != "sha256-canonical-key-first8-big-endian"
        or stored.get("salt") is not None
        or not isinstance(stored.get("config"), dict)
        or type(stored["config"].get("buckets")) is not int
        or not 1 <= stored["config"]["buckets"] <= 4096
    ):
        raise ValueError("unsupported stored format/hash/config; explicit migration required")
    return stored


def check_storage_paths(root: Path) -> None:
    for name in (
        ".quarry-owned",
        "data",
        "tmp",
        "catalog.sqlite",
        "catalog.sqlite-wal",
        "catalog.sqlite-shm",
    ):
        if (root / name).is_symlink():
            raise ValueError("owned storage paths cannot be symlinks")


def connect(root: Path, *, initialize: bool = True) -> sqlite3.Connection:
    check_storage_paths(root)
    if not initialize and (
        not (root / ".quarry-owned").is_file() or not (root / "catalog.sqlite").is_file()
    ):
        raise ValueError("snapshot requires an existing Quarry-owned dataset")
    conn = sqlite3.connect(
        f"{(root / 'catalog.sqlite').as_uri()}?mode={'rwc' if initialize else 'rw'}",
        uri=True,
        timeout=30,
    )
    try:
        if initialize:
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        if initialize:
            conn.executescript(DDL)
        return conn
    except BaseException:
        conn.close()
        raise

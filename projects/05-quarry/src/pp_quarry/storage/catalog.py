"""SQLite authoritative catalog. Single writer; immutable snapshot manifests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DDL = """
CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS identities(namespace TEXT,key TEXT,version INTEGER,fingerprint TEXT NOT NULL,payload TEXT NOT NULL,operation TEXT NOT NULL,source TEXT NOT NULL,offset INTEGER NOT NULL,PRIMARY KEY(namespace,key,version));
CREATE TABLE IF NOT EXISTS latest(namespace TEXT,key TEXT,version INTEGER,operation TEXT,payload TEXT,fingerprint TEXT,bucket INTEGER,source TEXT,offset INTEGER,PRIMARY KEY(namespace,key));
CREATE INDEX IF NOT EXISTS latest_bucket ON latest(bucket,namespace,key);
CREATE TABLE IF NOT EXISTS sources(hash TEXT PRIMARY KEY,path TEXT,offset INTEGER,events INTEGER,snapshot INTEGER);
CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,manifest TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS pins(token TEXT PRIMARY KEY,snapshot INTEGER NOT NULL);
"""


def connect(root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(root / "catalog.sqlite", timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.executescript(DDL)
    return conn

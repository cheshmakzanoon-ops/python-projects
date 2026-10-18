"""Tenant-separated SQLite metadata; coherent generation and ACL snapshots."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, cast

from pp_atlas.ingest.tokenizer import TOKENIZER_VERSION


@dataclass(frozen=True)
class Active:
    revision: str
    acl: frozenset[str]
    metadata: dict[str, str]


@dataclass(frozen=True)
class CatalogSnapshot:
    generation: int
    acl_revision: int
    segments: tuple[tuple[str, str], ...]
    documents: dict[str, Active]
    groups: dict[str, frozenset[str]]


def tenant_directory(root: Path, tenant: str) -> Path:
    if not tenant or len(tenant) > 256:
        raise ValueError("invalid tenant")
    return root / hashlib.sha256(tenant.encode()).hexdigest()


class Catalog:
    def __init__(self, root: Path, tenant: str) -> None:
        self.directory = tenant_directory(root, tenant)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "catalog.sqlite3"
        with self.connection() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS state (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    format INTEGER NOT NULL, tokenizer TEXT NOT NULL,
                    generation INTEGER NOT NULL, acl_revision INTEGER NOT NULL,
                    segments TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, revision TEXT NOT NULL,
                    acl TEXT NOT NULL, metadata TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS groups (
                    subject TEXT PRIMARY KEY, memberships TEXT NOT NULL
                );
            """)
            connection.execute(
                "INSERT OR IGNORE INTO state VALUES (1,1,?,0,0,'[]')", (TOKENIZER_VERSION,)
            )
            state = connection.execute("SELECT format,tokenizer FROM state").fetchone()
            if state != (1, TOKENIZER_VERSION):
                raise ValueError("unsupported catalog/tokenizer version")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.execute("PRAGMA synchronous=FULL")
        try:
            yield connection
        finally:
            connection.close()

    def snapshot(self, previous: CatalogSnapshot | None = None) -> CatalogSnapshot:
        with self.connection() as connection:
            connection.execute("BEGIN")
            generation, acl_revision, segments = connection.execute(
                "SELECT generation,acl_revision,segments FROM state WHERE singleton=1"
            ).fetchone()
            if previous and (previous.generation, previous.acl_revision) == (
                generation,
                acl_revision,
            ):
                return previous
            docs = {
                ident: Active(
                    revision, frozenset(json.loads(acl)), cast(dict[str, str], json.loads(metadata))
                )
                for ident, revision, acl, metadata in connection.execute(
                    "SELECT id,revision,acl,metadata FROM documents"
                )
            }
            groups = {
                subject: frozenset(json.loads(memberships))
                for subject, memberships in connection.execute(
                    "SELECT subject,memberships FROM groups"
                )
            }
            return CatalogSnapshot(
                generation,
                acl_revision,
                tuple(tuple(s) for s in json.loads(segments)),
                docs,
                groups,
            )

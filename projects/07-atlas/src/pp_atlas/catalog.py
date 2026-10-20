"""Tenant-separated SQLite metadata; coherent generation and ACL snapshots."""

import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Iterator, cast

from pp_atlas.ingest.tokenizer import TOKENIZER_VERSION

_TABLES = {
    "state": """singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        format INTEGER NOT NULL, tokenizer TEXT NOT NULL,
        generation INTEGER NOT NULL, acl_revision INTEGER NOT NULL,
        segments TEXT NOT NULL""",
    "documents": """id TEXT PRIMARY KEY, revision TEXT NOT NULL,
        acl TEXT NOT NULL, metadata TEXT NOT NULL""",
    "groups": "subject TEXT PRIMARY KEY, memberships TEXT NOT NULL",
}


def _create_tables(connection: sqlite3.Connection) -> None:
    # Separate execute calls remain inside the caller's explicit transaction;
    # executescript would commit that transaction before running its statements.
    for name, columns in _TABLES.items():
        connection.execute(f"CREATE TABLE {name} ({columns})")


@cache
def _table_signatures() -> dict[str, tuple[tuple[object, ...], ...]]:
    """Derive expected column/type/default/key metadata from the creation SQL."""
    with closing(sqlite3.connect(":memory:")) as connection:
        _create_tables(connection)
        return {
            name: tuple(tuple(row) for row in connection.execute(f"PRAGMA table_info({name})"))
            for name in _TABLES
        }


class IncompatibleCatalog(ValueError):
    """Persisted format cannot be interpreted or modified by this process."""


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
        if self.path.exists():
            # A writable last connection can checkpoint a WAL merely on close.
            # Unsupported state is recognized through a genuinely read-only
            # connection before any persistent pragma or schema operation.
            with self.connection(read_only=True) as connection:
                connection.execute("BEGIN")
                empty = self._recognize(connection)
                mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
                if not empty and mode == "wal":
                    return
        with self.connection() as connection:
            # Journal mode cannot change inside a transaction. Exclusive locking
            # mode is connection-local and retains the acquired SQLite lock over
            # COMMIT, protecting recognition -> WAL conversion -> atomic DDL.
            connection.execute("PRAGMA locking_mode=EXCLUSIVE")
            connection.execute("BEGIN EXCLUSIVE")
            empty = self._recognize(connection)
            connection.commit()
            if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
                raise IncompatibleCatalog("catalog requires SQLite WAL support")
            if empty:
                connection.execute("BEGIN IMMEDIATE")
                _create_tables(connection)
                connection.execute(
                    "INSERT INTO state VALUES (1,1,?,0,0,'[]')", (TOKENIZER_VERSION,)
                )
                connection.commit()

    @classmethod
    def _recognize(cls, connection: sqlite3.Connection) -> bool:
        """Return whether a database is empty; never repair an existing schema."""
        try:
            objects = set(
                connection.execute(
                    "SELECT type,name FROM sqlite_schema WHERE substr(name,1,7) != 'sqlite_'"
                )
            )
            if any(
                connection.execute(f"PRAGMA {name}").fetchone() != (0,)
                for name in ("application_id", "user_version")
            ):
                raise IncompatibleCatalog("unrecognized catalog identity metadata")
            if not objects:
                return True
            cls._check_compatibility(connection)
            expected = _table_signatures()
            if objects != {("table", name) for name in _TABLES} or any(
                tuple(tuple(row) for row in connection.execute(f"PRAGMA table_info({name})"))
                != expected[name]
                for name in _TABLES
            ):
                raise IncompatibleCatalog("unrecognized or incomplete catalog schema")
            if connection.execute("SELECT COUNT(*) FROM state").fetchone() != (1,):
                raise IncompatibleCatalog("catalog must have exactly one state header")
        except sqlite3.DatabaseError as error:
            raise IncompatibleCatalog("unrecognized or incomplete catalog schema") from error
        return False

    @staticmethod
    def _check_compatibility(connection: sqlite3.Connection) -> None:
        state = connection.execute(
            "SELECT format,tokenizer FROM state WHERE singleton=1"
        ).fetchone()
        if state != (1, TOKENIZER_VERSION):
            raise IncompatibleCatalog(
                "unsupported catalog/tokenizer version; offline rebuild required"
            )

    @contextmanager
    def connection(self, *, read_only: bool = False) -> Iterator[sqlite3.Connection]:
        path = self.path.resolve().as_uri() + "?mode=ro" if read_only else str(self.path)
        connection = sqlite3.connect(path, timeout=30, isolation_level=None, uri=read_only)
        try:
            if not read_only:
                connection.execute("PRAGMA synchronous=FULL")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        """Check compatibility inside the same snapshot/lock as the operation.

        Checking before BEGIN would leave a race with a different catalog writer.
        Closing on every exit rolls back any failed publication, including commit
        failures. Raw connections are reserved for initialization and repair tests.
        """
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            self._check_compatibility(connection)
            yield connection
            if write:
                connection.commit()

    def snapshot(self, previous: CatalogSnapshot | None = None) -> CatalogSnapshot:
        with self.transaction() as connection:
            return read_snapshot(connection, previous)


def read_snapshot(
    connection: sqlite3.Connection, previous: CatalogSnapshot | None = None
) -> CatalogSnapshot:
    """Read inside a transaction whose format/tokenizer has already been checked."""
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
        for subject, memberships in connection.execute("SELECT subject,memberships FROM groups")
    }
    return CatalogSnapshot(
        generation,
        acl_revision,
        tuple(tuple(s) for s in json.loads(segments)),
        docs,
        groups,
    )

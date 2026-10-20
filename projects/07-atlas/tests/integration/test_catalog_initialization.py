"""Catalog recognition must precede persistent pragmas and schema publication."""

import hashlib
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from threading import Event, get_ident

import pytest

from pp_atlas import Engine, IncompatibleCatalog, Principal
from pp_atlas.catalog import Catalog, tenant_directory
from pp_atlas.ingest.tokenizer import TOKENIZER_VERSION

SCHEMA = (
    "CREATE TABLE state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), format INTEGER NOT NULL, tokenizer TEXT NOT NULL, generation INTEGER NOT NULL, acl_revision INTEGER NOT NULL, segments TEXT NOT NULL)",
    "CREATE TABLE documents (id TEXT PRIMARY KEY, revision TEXT NOT NULL, acl TEXT NOT NULL, metadata TEXT NOT NULL)",
    "CREATE TABLE groups (subject TEXT PRIMARY KEY, memberships TEXT NOT NULL)",
)


def path_for(root):
    path = tenant_directory(root, "t") / "catalog.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def fingerprint(path):
    # Read-only SQLite may touch shared-memory coordination. The catalog and WAL
    # bytes, schema and journal mode are the persistent content being protected.
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        schema = connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY name"
        ).fetchall()
        mode = connection.execute("PRAGMA journal_mode").fetchone()
    wal = path.with_name(path.name + "-wal")
    return (
        hashlib.sha256(path.read_bytes()).hexdigest(),
        hashlib.sha256(wal.read_bytes()).hexdigest() if wal.exists() else None,
        schema,
        mode,
    )


@pytest.mark.parametrize(
    "kind",
    [
        "future",
        "unrelated",
        "sqlite_prefix_lookalike",
        "missing_groups",
        "missing_header",
        "redesigned_documents",
        "foreign_empty",
    ],
)
def test_unrecognized_delete_catalog_is_rejected_without_mutation(tmp_path, kind):
    path = path_for(tmp_path)
    with closing(sqlite3.connect(path)) as connection:
        if kind in {"unrelated", "sqlite_prefix_lookalike"}:
            name = "sqliteXdata" if kind == "sqlite_prefix_lookalike" else "accounts"
            connection.execute(f"CREATE TABLE {name} (payload TEXT)")
            connection.execute(f"INSERT INTO {name} VALUES ('preserve')")
        elif kind == "foreign_empty":
            connection.execute("PRAGMA application_id=89145")
        else:
            for statement in SCHEMA:
                if kind == "missing_groups" and "CREATE TABLE groups" in statement:
                    continue
                if kind == "redesigned_documents" and "CREATE TABLE documents" in statement:
                    statement = "CREATE TABLE documents (future_payload BLOB)"
                connection.execute(statement)
            if kind != "missing_header":
                connection.execute(
                    "INSERT INTO state VALUES (1,?,?,0,0,'[]')",
                    (999 if kind == "future" else 1, TOKENIZER_VERSION),
                )
            if kind == "future":
                connection.execute("DROP TABLE documents")
                connection.execute("DROP TABLE groups")
                connection.execute("CREATE TABLE future_payload (value TEXT)")
                connection.execute("INSERT INTO future_payload VALUES ('preserve')")
        connection.commit()
    before = fingerprint(path)
    with pytest.raises(IncompatibleCatalog):
        Engine(tmp_path).search(Principal("t", "reader"), "")
    assert fingerprint(path) == before


def test_future_uncheckpointed_wal_is_not_modified_or_checkpointed(tmp_path):
    path = path_for(tmp_path)
    code = """
import os,sqlite3,sys
connection=sqlite3.connect(sys.argv[1])
connection.execute('PRAGMA journal_mode=WAL')
connection.executescript('''CREATE TABLE state(singleton INTEGER PRIMARY KEY,format INTEGER,tokenizer TEXT,generation INTEGER,acl_revision INTEGER,segments TEXT);
INSERT INTO state VALUES(1,999,'future',4,7,'[]');
CREATE TABLE future_payload(value TEXT);
INSERT INTO future_payload VALUES('preserve');''')
connection.commit()
os._exit(0)
"""
    subprocess.run([sys.executable, "-c", code, str(path)], check=True)
    before = fingerprint(path)
    assert before[1] is not None
    with pytest.raises(IncompatibleCatalog):
        Catalog(tmp_path, "t")
    assert fingerprint(path) == before


@pytest.mark.parametrize("empty", ["absent", "zero_byte", "sqlite_empty"])
def test_empty_catalog_initialization_and_reopen(tmp_path, empty):
    path = path_for(tmp_path)
    if empty == "zero_byte":
        path.touch()
    elif empty == "sqlite_empty":
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("VACUUM")
    snapshot = Catalog(tmp_path, "t").snapshot()
    assert snapshot == Catalog(tmp_path, "t").snapshot()
    assert (snapshot.generation, snapshot.documents, snapshot.groups) == (0, {}, {})
    assert fingerprint(path)[3] == ("wal",)


def test_known_delete_catalog_is_recognized_before_wal_conversion(tmp_path):
    path = path_for(tmp_path)
    with closing(sqlite3.connect(path)) as connection:
        for statement in SCHEMA:
            connection.execute(statement)
        connection.execute("INSERT INTO state VALUES (1,1,?,0,3,'[]')", (TOKENIZER_VERSION,))
        connection.execute("INSERT INTO groups VALUES ('reader','[\"ops\"]')")
        connection.commit()
    schema = fingerprint(path)[2]
    snapshot = Catalog(tmp_path, "t").snapshot()
    assert snapshot.acl_revision == 3
    assert snapshot.groups == {"reader": frozenset({"ops"})}
    assert fingerprint(path)[2:] == (schema, ("wal",))


def test_two_constructors_overlap_one_atomic_initialization(tmp_path, monkeypatch):
    original = Catalog.connection
    partial, second_started, resume = Event(), Event(), Event()
    owner = None

    @contextmanager
    def observed(self, *, read_only=False):
        nonlocal owner
        thread = get_ident()
        if owner is None:
            owner = thread
        elif thread != owner:
            second_started.set()
        with original(self, read_only=read_only) as connection:

            def trace(statement):
                if thread == owner and statement.lstrip().startswith("CREATE TABLE documents"):
                    partial.set()
                    resume.wait(5)

            connection.set_trace_callback(trace)
            yield connection

    monkeypatch.setattr(Catalog, "connection", observed)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(Catalog, tmp_path, "t")
        assert partial.wait(5)
        second = pool.submit(Catalog, tmp_path, "t")
        assert second_started.wait(5)
        resume.set()
        first_snapshot = first.result().snapshot()
        second_snapshot = second.result().snapshot()
    assert first_snapshot == second_snapshot
    assert first_snapshot.generation == 0


def test_failed_schema_publication_rolls_back_and_empty_catalog_can_retry(tmp_path, monkeypatch):
    original = sqlite3.connect
    failed = False

    class FailOnce(sqlite3.Connection):
        def execute(self, statement, parameters=()):
            nonlocal failed
            if not failed and statement.lstrip().startswith("CREATE TABLE documents"):
                failed = True
                raise OSError("injected schema write failure")
            return super().execute(statement, parameters)

    def connect(*args, **kwargs):
        return original(*args, **kwargs, factory=FailOnce)

    monkeypatch.setattr(sqlite3, "connect", connect)
    with pytest.raises(OSError, match="injected schema"):
        Catalog(tmp_path, "t")
    path = path_for(tmp_path)
    assert fingerprint(path)[2] == []
    assert Catalog(tmp_path, "t").snapshot().documents == {}

"""Fail closed on wrong database identity, invalid cursors and corrupt checkpoints."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from pp_current import Config, Engine, Journal, Record, canonical

INPUT = canonical(["s", 0])


@pytest.mark.parametrize("kind", ["unrelated", "future", "incomplete", "trigger", "hidden-trigger"])
def test_open_rejects_unrecognized_database_without_changing_it(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "existing.db"
    if kind in ("future", "trigger", "hidden-trigger"):
        journal = Journal(path)
        journal.admit([Record("s", 0, 0, value=7)])
        journal.close()
    with sqlite3.connect(path) as db:
        if kind == "unrelated":
            db.execute("CREATE TABLE customer_data(value TEXT)")
            db.execute("INSERT INTO customer_data VALUES('preserve me')")
        elif kind == "future":
            db.execute("UPDATE format SET version=99")
        elif kind == "incomplete":
            db.execute("CREATE TABLE format(version INTEGER)")
            db.execute("INSERT INTO format VALUES(1)")
        else:
            name = "sqliteXunexpected" if kind == "hidden-trigger" else "unexpected"
            db.execute(
                f"CREATE TRIGGER {name} AFTER INSERT ON ingress BEGIN DELETE FROM ingress; END"
            )
    db.close()
    before = path.read_bytes()
    for read_only in (False, True):
        with pytest.raises(ValueError, match="journal (format|schema)"):
            Journal(path, read_only=read_only)
        assert path.read_bytes() == before
    if kind in ("unrelated", "incomplete"):
        assert not path.with_name(path.name + "-wal").exists()


@pytest.mark.parametrize("limit", [-1, 0, True, 1.0, 2**63])
def test_public_page_limits_cannot_disable_bounded_reads(tmp_path: Path, limit: object) -> None:
    journal = Journal(tmp_path / "bounded.db")
    try:
        journal.admit([Record("s", 0, number) for number in range(3)])
        with pytest.raises(ValueError, match="limit"):
            journal.read(0, limit)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="limit"):
            journal.pending(limit)  # type: ignore[arg-type]
        assert len(journal.read(0, 2)) == 2
    finally:
        journal.close()


@pytest.mark.parametrize("after", [-1, True, 1.0, 2**63])
def test_public_read_cursor_requires_nonnegative_sqlite_integer(
    tmp_path: Path, after: object
) -> None:
    journal = Journal(tmp_path / "cursor.db")
    try:
        with pytest.raises(ValueError, match="cursor"):
            journal.read(after)  # type: ignore[arg-type]
    finally:
        journal.close()


@pytest.mark.parametrize("corruption", ["negative", "boolean", "column", "beyond_ingress"])
def test_recovery_rejects_inconsistent_checkpoint_prefix_without_rewriting_it(
    tmp_path: Path, corruption: str
) -> None:
    journal = Journal(tmp_path / "checkpoint.db")
    config = Config((INPUT,))
    try:
        engine = journal.recover(config)
        engine.apply(journal.admit([Record("s", 0, 0, value=7)])[0])
        journal.publish(engine)
        data = json.loads(engine.dump())
        position: int | bool = 1
        if corruption == "column":
            position = 0
        else:
            data["position"] = {"negative": -1, "boolean": True, "beyond_ingress": 2}[corruption]
            position = data["position"]
        raw = canonical(data)
        journal.db.execute("UPDATE checkpoint SET position=?,state=?", (position, raw))
        with pytest.raises(ValueError, match="checkpoint"):
            journal.recover(config)
        assert journal.db.execute("SELECT position,state FROM checkpoint").fetchone() == (
            position,
            raw,
        )
        assert journal.read(0)[0].value == 7
    finally:
        journal.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("watermarks", {}),
        ("idle", ["unknown"]),
        ("watermark", True),
        ("watermark", 10),
        ("dispositions", {"on-time": -1, "accepted-late": 0, "rejected-late": 0}),
        ("peak_state", 0),
        ("max_watermark_lag", -1),
        ("max_finalization_lag", "0"),
    ],
)
def test_restore_rejects_invalid_control_and_resource_state(field: str, value: object) -> None:
    engine = Engine(Config((INPUT,)))
    engine.apply(Record("s", 0, 0, event_time=1, value=7, ingress_ordinal=1))
    data = json.loads(engine.dump())
    data[field] = value
    with pytest.raises(ValueError, match="checkpoint"):
        Engine.restore(canonical(data), engine.config)


@pytest.mark.parametrize("corruption", ["key", "aggregate", "revision", "join_ordinal", "join_key"])
def test_restore_rejects_invalid_operator_state(corruption: str) -> None:
    engine = Engine(Config((INPUT,)))
    engine.apply(Record("s", 0, 0, event_time=1, value=7, ingress_ordinal=1))
    data = json.loads(engine.dump())
    window = next(iter(data["windows"].values()))
    if corruption == "key":
        window["key"] = "different"
    elif corruption == "aggregate":
        window["aggregate"]["total"] = 99
    elif corruption == "revision":
        window["revision"] = 2
    elif corruption == "join_ordinal":
        data["join"][""][0]["ingress_ordinal"] = 2
    else:
        data["join"][""][0]["key"] = "different"
    with pytest.raises(ValueError, match="checkpoint"):
        Engine.restore(canonical(data), engine.config)


def test_disk_page_limit_uses_existing_database_page_size(tmp_path: Path) -> None:
    path = tmp_path / "large-pages.db"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA page_size=8192")
        db.execute("VACUUM")
    db.close()
    journal = Journal(path, max_disk_bytes=1024 * 1024)
    try:
        assert journal.db.execute("PRAGMA page_size").fetchone() == (8192,)
        assert journal.db.execute("PRAGMA max_page_count").fetchone() == (128,)
        journal.admit([Record("s", 0, 0, value=7)])
        assert journal.read(0)[0].value == 7
    finally:
        journal.close()


@pytest.mark.parametrize(
    "table,definition",
    [
        (
            "ingress",
            "ordinal INTEGER,source TEXT NOT NULL,partition INTEGER NOT NULL,"
            "offset INTEGER NOT NULL,wire TEXT NOT NULL,UNIQUE(source,partition,offset)",
        ),
        (
            "ingress",
            "ordinal INTEGER PRIMARY KEY,source TEXT NOT NULL,partition INTEGER NOT NULL,"
            "offset INTEGER NOT NULL,wire TEXT NOT NULL",
        ),
        (
            "ingress",
            "ordinal INTEGER PRIMARY KEY,source TEXT,partition INTEGER NOT NULL,"
            "offset INTEGER NOT NULL,wire TEXT NOT NULL,UNIQUE(source,partition,offset)",
        ),
        (
            "ingress",
            "ordinal TEXT PRIMARY KEY,source TEXT NOT NULL,partition INTEGER NOT NULL,"
            "offset INTEGER NOT NULL,wire TEXT NOT NULL,UNIQUE(source,partition,offset)",
        ),
        (
            "ingress",
            "ordinal INTEGER PRIMARY KEY,source TEXT NOT NULL,partition INTEGER NOT NULL,"
            "offset INTEGER NOT NULL,wire TEXT NOT NULL,"
            "UNIQUE(source COLLATE NOCASE,partition,offset)",
        ),
        ("checkpoint", "id INTEGER PRIMARY KEY,position INTEGER NOT NULL,state TEXT NOT NULL"),
        (
            "checkpoint",
            "id INTEGER PRIMARY KEY CHECK(id>=1),position INTEGER NOT NULL,state TEXT NOT NULL",
        ),
        (
            "deliveries",
            "job TEXT,operator TEXT,key TEXT,revision INTEGER CHECK(revision>100),"
            "payload TEXT NOT NULL,sent INTEGER NOT NULL DEFAULT 0,"
            "PRIMARY KEY(job,operator,key,revision)",
        ),
        (
            "deliveries",
            "job TEXT,operator TEXT,key TEXT,revision INTEGER,"
            "payload TEXT NOT NULL COLLATE NOCASE,sent INTEGER NOT NULL DEFAULT 0,"
            "PRIMARY KEY(job,operator,key,revision)",
        ),
    ],
    ids=[
        "primary-key",
        "unique",
        "not-null",
        "type",
        "collation",
        "check-missing",
        "check-widened",
        "extra-check",
        "payload-collation",
    ],
)
def test_same_named_columns_do_not_hide_missing_or_altered_constraints(
    tmp_path: Path, table: str, definition: str
) -> None:
    path = tmp_path / "altered.db"
    journal = Journal(path)
    journal.close()
    with sqlite3.connect(path) as db:
        db.execute(f'DROP TABLE "{table}"')
        db.execute(f'CREATE TABLE "{table}"({definition})')
    db.close()
    before = path.read_bytes()
    for read_only in (True, False):
        with pytest.raises(ValueError, match="unrecognized journal schema"):
            Journal(path, read_only=read_only)
        assert path.read_bytes() == before


def test_interrupted_initialization_rolls_back_schema_and_can_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "initializing.db"
    original_connect = sqlite3.connect

    def interrupted_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        db = original_connect(*args, **kwargs)  # type: ignore[call-overload]
        if str(args[0]) == str(path):
            db.set_authorizer(
                lambda action, name, *_: (
                    sqlite3.SQLITE_DENY
                    if action == sqlite3.SQLITE_CREATE_TABLE and name == "checkpoint"
                    else sqlite3.SQLITE_OK
                )
            )
        return db

    with monkeypatch.context() as patch:
        patch.setattr("pp_current.ingress.journal.sqlite3.connect", interrupted_connect)
        with pytest.raises(sqlite3.DatabaseError, match="authorized"):
            Journal(path)
    with original_connect(path) as db:
        assert db.execute("SELECT name FROM sqlite_schema").fetchall() == []
    db.close()
    journal = Journal(path)
    try:
        admitted = journal.admit([Record("s", 0, 0, value=7)])
        assert admitted[0].ingress_ordinal == 1
        assert journal.read(0) == admitted
        assert journal.db.execute("SELECT version FROM format").fetchall() == [(1,)]
    finally:
        journal.close()


def test_concurrent_initializers_create_one_complete_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "concurrent.db"
    ready = Barrier(2)
    original_initialize = Journal._initialize

    def synchronized_initialize(journal: Journal, budget: int) -> None:
        ready.wait(timeout=10)
        original_initialize(journal, budget)

    monkeypatch.setattr(Journal, "_initialize", synchronized_initialize)

    def open_and_inspect() -> list[tuple[int]]:
        journal = Journal(path)
        try:
            return journal.db.execute("SELECT version FROM format").fetchall()
        finally:
            journal.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: open_and_inspect(), range(2)))
    assert results == [[(1,)], [(1,)]]


def test_initialization_retries_a_transient_wal_mode_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_connect = sqlite3.connect
    blocked = False
    delays: list[float] = []

    class BusyOnce(sqlite3.Connection):
        def execute(self, sql: str, *args: object, **kwargs: object) -> sqlite3.Cursor:
            nonlocal blocked
            if sql == "PRAGMA journal_mode=WAL" and not blocked:
                blocked = True
                error = sqlite3.OperationalError("database is locked")
                error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                raise error
            return super().execute(sql, *args, **kwargs)  # type: ignore[arg-type]

    def busy_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        return original_connect(*args, factory=BusyOnce, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr("pp_current.ingress.journal.sqlite3.connect", busy_connect)
    monkeypatch.setattr("pp_current.ingress.journal.time.sleep", delays.append)
    journal = Journal(tmp_path / "busy.db")
    try:
        admitted = journal.admit([Record("s", 0, 0, value=7)])
        assert journal.read(0) == admitted
        assert blocked and len(delays) == 1
    finally:
        journal.close()

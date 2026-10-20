from __future__ import annotations

import errno
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from pp_strata import Conflict, Corruption, Database, WriterFailed
from pp_strata.codec.records import Record, encode
from pp_strata.io import frame


def test_crashed_value_containing_a_valid_frame_is_not_interior_corruption(tmp_path: Path) -> None:
    script = r"""
import os, sys
from pp_strata import Database
from pp_strata.codec.records import Record, encode
from pp_strata.io import frame
import pp_strata.wal.frames as frames

with Database.open(sys.argv[1]) as db:
    with db.begin() as tx:
        tx.put(b'acknowledged', b'durable')
    nested = b'STW1' + frame(encode([Record(b'user-bytes', 3, b'not-a-transaction')]))
    original = frames.write_all
    def tear(fd, data):
        original(fd, data[:-3])
        os.fsync(fd)
        os._exit(87)
    frames.write_all = tear
    with db.begin() as tx:
        tx.put(b'unacknowledged', nested + b'ordinary-suffix')
"""
    path = tmp_path / "database"
    result = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        timeout=20,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 87, result.stderr
    with Database.open(path) as db, db.snapshot() as snapshot:
        assert list(snapshot.scan()) == [(b"acknowledged", b"durable")]
        assert db.sequence == 1
        with db.begin() as tx:
            tx.put(b"after-recovery", b"new")
        assert db.sequence == 2


def test_rejected_replay_plan_preserves_torn_tail_for_diagnosis(tmp_path: Path) -> None:
    path = tmp_path / "database"
    with Database.open(path):
        pass
    # A complete prefix has been lost. Tail repair must wait until this replay
    # gap has been checked against the authoritative manifest checkpoint.
    original = b"STW1" + frame(encode([Record(b"lost-prefix", 2, b"value")])) + b"ST"
    (path / "WAL").write_bytes(original)
    with pytest.raises(Corruption, match="sequence gap"):
        Database.open(path)
    assert (path / "WAL").read_bytes() == original


@pytest.mark.parametrize("location", ["wal", "table_block", "table_index", "manifest"])
def test_verify_checks_persistent_bytes_even_when_reads_are_cached(
    tmp_path: Path, location: str
) -> None:
    with Database.open(tmp_path / "database") as db:
        with db.begin() as tx:
            tx.put(b"key", b"persistent-value")
        if location.startswith("table"):
            db.flush()
        with db.snapshot() as snapshot:
            assert snapshot.get(b"key") == b"persistent-value"
        if location == "wal":
            path, offset = db.path / "WAL", -1
        elif location == "manifest":
            path, offset = db.path / "MANIFEST", -1
        else:
            path = db.path / str(db.inspect()["tables"][0])
            offset = 20 if location == "table_block" else -20
        content = bytearray(path.read_bytes())
        content[offset] ^= 1
        path.write_bytes(content)
        with pytest.raises(Corruption):
            db.verify()
        assert db.writer_failed
        with pytest.raises(WriterFailed):
            db.begin()


@pytest.mark.parametrize("failed_index", [0, 3])
def test_compaction_attempts_every_retired_descriptor_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_index: int
) -> None:
    before = len(list(Path("/proc/self/fd").iterdir()))
    path = tmp_path / "database"
    with Database.open(path) as db:
        for index in range(4):
            with db.begin() as tx:
                tx.put(str(index).encode(), b"durable")
            db.flush()
        table = db._tables[failed_index]
        real_close = table.close

        def close_then_fail() -> None:
            real_close()
            raise OSError(errno.EIO, "retired table close failed")

        with monkeypatch.context() as patch:
            patch.setattr(table, "close", close_then_fail)
            with pytest.raises(OSError, match="retired table"):
                db.compact()
        assert db.writer_failed
        with db.snapshot() as snapshot:
            assert list(snapshot.scan()) == [(str(i).encode(), b"durable") for i in range(4)]
    assert len(list(Path("/proc/self/fd").iterdir())) == before
    with Database.open(path) as db, db.snapshot() as snapshot:
        assert list(snapshot.scan()) == [(str(i).encode(), b"durable") for i in range(4)]


@pytest.mark.parametrize("operation", ["get", "scan"])
def test_read_corruption_prevents_further_writes(tmp_path: Path, operation: str) -> None:
    with Database.open(tmp_path / "database", cache_blocks=0) as db:
        with db.begin() as tx:
            tx.put(b"key", b"value")
        db.flush()
        path = db._tables[0].path
        content = bytearray(path.read_bytes())
        content[20] ^= 1
        path.write_bytes(content)
        with db.snapshot() as snapshot, pytest.raises(Corruption):
            if operation == "get":
                snapshot.get(b"key")
            else:
                list(snapshot.scan())
        assert db.writer_failed
        with pytest.raises(WriterFailed):
            db.begin()


def test_compaction_reclaims_conflict_heads_only_after_older_handles_close(tmp_path: Path) -> None:
    with Database.open(tmp_path / "database") as db:
        old = db.begin()
        with db.begin() as tx:
            for index in range(3000):
                tx.put(index.to_bytes(4), b"temporary")
        with db.begin() as tx:
            for index in range(3000):
                tx.delete(index.to_bytes(4))
        db.compact()
        old.put(bytes(4), b"must-conflict")
        with pytest.raises(Conflict):
            old.commit()
        with db.snapshot() as after_deletes:
            db.compact()
            assert list(after_deletes.scan()) == []
            assert len(db._latest) == 0
            stale = db.begin()
            with db.begin() as tx:
                tx.put(bytes(4), b"another-insert")
            with db.begin() as tx:
                tx.delete(bytes(4))
            db.compact()
            stale.put(bytes(4), b"also-conflicts")
            with pytest.raises(Conflict):
                stale.commit()
        db.compact()
        assert len(db._latest) == 0
        with db.begin() as tx:
            tx.put(bytes(4), b"fresh-writer")


def test_materialized_backup_outlives_source_snapshot_and_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pp_strata.api as api

    db = Database.open(tmp_path / "source")
    with db.begin() as tx:
        tx.put(b"key", b"historical")
    old = db.snapshot()
    entered, release = threading.Event(), threading.Event()
    target = tmp_path / "backup"
    mkdir = api.durable_mkdir

    def pause_after_capture(path: Path, *, exist_ok: bool = True) -> None:
        if path == target and not exist_ok:
            entered.set()
            assert release.wait(10)
        mkdir(path, exist_ok=exist_ok)

    monkeypatch.setattr(api, "durable_mkdir", pause_after_capture)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(db.backup, target, snapshot=old)
        try:
            assert entered.wait(5)
            old.close()
            with db.begin() as tx:
                tx.put(b"key", b"new-current")
            db.compact()
            db.close()
        finally:
            release.set()
        report = future.result(timeout=10)
    assert report["source_sequence"] == 1
    Database.restore(target, tmp_path / "restored")
    with Database.open(tmp_path / "restored") as restored, restored.snapshot() as snapshot:
        assert list(snapshot.scan()) == [(b"key", b"historical")]

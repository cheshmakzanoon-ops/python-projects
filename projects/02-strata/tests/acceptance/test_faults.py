from __future__ import annotations

import errno
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pp_strata import Corruption, Database, OwnerBusy, WriterFailed
from pp_strata.codec.records import MAX_VALUE
from pp_strata.io import atomic_metadata, read_metadata

WORKER = r"""
import os, sys
from pp_strata import Database
path, phase, target = sys.argv[1:]
armed = False
def fault(name):
    if armed and name == target:
        os._exit(81)
with Database.open(path, failpoint=fault) as db:
    if phase == "wal":
        with db.begin() as tx:
            tx.put(b"ack:1", b"durable")
            tx.put(b"ack:2", b"durable")
        armed = True
        with db.begin() as tx:
            tx.put(b"pending:1", b"complete")
            tx.put(b"pending:2", b"complete")
    else:
        with db.begin() as tx:
            tx.put(b"dead", b"old")
            tx.put(b"live", b"old")
        db.flush()
        with db.begin() as tx:
            tx.delete(b"dead")
            tx.put(b"live", b"new")
        db.flush()
        armed = True
        db.compact()
raise RuntimeError("failpoint was not reached")
"""


@pytest.mark.parametrize(
    "point",
    ["before_wal_append", "after_wal_append", "after_wal_sync", "before_publish", "after_publish"],
)
def test_st02_real_process_crash_atomic_batch(tmp_path: Path, point: str) -> None:
    path = tmp_path / "db"
    result = subprocess.run(
        [sys.executable, "-c", WORKER, str(path), "wal", point],
        timeout=20,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 81, result.stderr
    with Database.open(path) as db, db.snapshot() as snap:
        assert snap.get(b"ack:1") == snap.get(b"ack:2") == b"durable"
        assert snap.get(b"pending:1") == snap.get(b"pending:2")
        assert snap.get(b"pending:1") in (None, b"complete")
        sequence = db.sequence
        with db.begin() as tx:
            tx.put(b"next", b"ok")
        assert db.sequence == sequence + 1


@pytest.mark.parametrize(
    "point",
    [
        "table_created",
        "table_synced",
        "before_manifest_replace",
        "after_manifest_replace",
        "after_manifest_sync",
        "before_obsolete_cleanup",
        "after_obsolete_cleanup",
    ],
)
def test_st07_real_process_compaction_crash_no_resurrection(tmp_path: Path, point: str) -> None:
    path = tmp_path / "db"
    result = subprocess.run(
        [sys.executable, "-c", WORKER, str(path), "table", point],
        timeout=20,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 81, result.stderr
    with Database.open(path) as db, db.snapshot() as snap:
        assert snap.get(b"dead") is None
        assert snap.get(b"live") == b"new"
        db.compact()
        assert snap.get(b"dead") is None
        assert db.verify()["status"] == "passed"


def test_st08_second_owner_process(tmp_path: Path) -> None:
    with Database.open(tmp_path / "db"):
        with pytest.raises(OwnerBusy):
            Database.open(tmp_path / "db")
        code = "from pp_strata import Database, OwnerBusy\nimport sys\ntry: Database.open(sys.argv[1])\nexcept OwnerBusy: sys.exit(42)\n"
        result = subprocess.run([sys.executable, "-c", code, str(tmp_path / "db")], timeout=20)
        assert result.returncode == 42
    with Database.open(tmp_path / "db"):
        pass


@pytest.mark.parametrize("mode", ["diskfull", "zero", "sync"])
def test_st08_uncertain_wal_poison_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    path = tmp_path / "db"
    db = Database.open(path)
    with db.begin() as tx:
        tx.put(b"ack", b"yes")
    with db.snapshot() as snap:
        with monkeypatch.context() as patch:
            if mode == "sync":

                def bad_sync(fd: int) -> None:
                    raise OSError(errno.EIO, "injected fsync failure")

                patch.setattr(os, "fsync", bad_sync)
            elif mode == "diskfull":
                real_write = os.write
                calls = 0

                def diskfull(fd: int, data: bytes) -> int:
                    nonlocal calls
                    calls += 1
                    if calls == 1:
                        return real_write(fd, data[:8])
                    raise OSError(errno.ENOSPC, "injected disk full")

                patch.setattr(os, "write", diskfull)
            else:
                patch.setattr(os, "write", lambda fd, data: 0)
            with pytest.raises(OSError):
                with db.begin() as tx:
                    tx.put(b"uncertain:a", b"a")
                    tx.put(b"uncertain:b", b"b")
        assert db.writer_failed
        assert snap.get(b"ack") == b"yes"
        with pytest.raises(WriterFailed):
            db.begin()
        with pytest.raises(WriterFailed):
            db.flush()
    db.close()
    with Database.open(path) as db, db.snapshot() as snap:
        assert snap.get(b"ack") == b"yes"
        assert (snap.get(b"uncertain:a"), snap.get(b"uncertain:b")) in ((None, None), (b"a", b"b"))
        recovered = db.sequence
        if mode == "sync":
            assert recovered == 2
        with db.begin() as tx:
            tx.put(b"next", b"ok")
        assert db.sequence == recovered + 1


def test_st08_short_write_supported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with Database.open(tmp_path / "db") as db:
        real_write = os.write
        with monkeypatch.context() as patch:
            patch.setattr(os, "write", lambda fd, data: real_write(fd, data[:3]))
            with db.begin() as tx:
                tx.put(b"a", b"one")
                tx.put(b"b", b"two")
        assert not db.writer_failed
    with Database.open(tmp_path / "db") as db, db.snapshot() as snap:
        assert list(snap.scan()) == [(b"a", b"one"), (b"b", b"two")]


def test_st08_oversize_rejected_without_poison(tmp_path: Path) -> None:
    with Database.open(tmp_path / "db") as db, db.begin() as tx:
        for key, value in ((bytes(4097), b"v"), (b"k", bytes(MAX_VALUE + 1))):
            with pytest.raises(ValueError):
                tx.put(key, value)
        for i in range(15):
            tx.put(bytes([i]), bytes(MAX_VALUE))
        with pytest.raises(ValueError):
            tx.put(b"too-much", bytes(MAX_VALUE))
        assert not db.writer_failed


def test_missing_manifest_and_malicious_table_path(tmp_path: Path) -> None:
    path = tmp_path / "db"
    path.mkdir()
    (path / "unknown").write_text("preserve")
    with pytest.raises(Corruption):
        Database.open(path)
    assert (path / "unknown").read_text() == "preserve"
    (path / "unknown").unlink()
    atomic_metadata(path / "MANIFEST", {"format": 1, "sequence": 0, "tables": ["../escape"]})
    with pytest.raises(Corruption):
        Database.open(path)


def test_backup_digest_validation_and_foreign_snapshot(tmp_path: Path) -> None:
    with Database.open(tmp_path / "db") as db, Database.open(tmp_path / "other") as other:
        with other.snapshot() as foreign:
            with pytest.raises(ValueError):
                db.backup(tmp_path / "backup", snapshot=foreign)
        db.backup(tmp_path / "backup")
    metadata = read_metadata(tmp_path / "backup" / "BACKUP")
    metadata["content_sha256"] = "0" * 64
    atomic_metadata(tmp_path / "backup" / "BACKUP", metadata)
    with pytest.raises(Corruption, match="backup content digest mismatch"):
        Database.restore(tmp_path / "backup", tmp_path / "restored")


def test_st07_cleanup_exception_closes_retired_descriptors(tmp_path: Path) -> None:
    before = len(list(Path("/proc/self/fd").iterdir()))
    armed = False

    def fail(name: str) -> None:
        if armed and name == "before_obsolete_cleanup":
            raise OSError(errno.EIO, "injected obsolete cleanup failure")

    with Database.open(tmp_path / "db", failpoint=fail) as db:
        with db.begin() as tx:
            tx.put(b"key", b"old")
        db.flush()
        with db.begin() as tx:
            tx.delete(b"key")
        db.flush()
        armed = True
        with pytest.raises(OSError):
            db.compact()
        assert db.writer_failed
        with db.snapshot() as snap:
            assert snap.get(b"key") is None
    assert len(list(Path("/proc/self/fd").iterdir())) == before
    with Database.open(tmp_path / "db") as db, db.snapshot() as snap:
        assert snap.get(b"key") is None
        assert len(list((tmp_path / "db").glob("*.sst"))) == 1


@pytest.mark.parametrize(
    "point", ["table_created", "before_manifest_replace", "after_manifest_replace"]
)
def test_st07_flush_io_exception_recovers(tmp_path: Path, point: str) -> None:
    armed = False

    def fail(name: str) -> None:
        if armed and name == point:
            raise OSError(errno.EIO, f"injected {name}")

    with Database.open(tmp_path / "db", failpoint=fail) as db:
        with db.begin() as tx:
            tx.put(b"key", b"durable")
        armed = True
        with pytest.raises(OSError):
            db.flush()
        assert db.writer_failed
        with db.snapshot() as snap:
            assert snap.get(b"key") == b"durable"
    with Database.open(tmp_path / "db") as db, db.snapshot() as snap:
        assert snap.get(b"key") == b"durable"


@pytest.mark.parametrize("rename_survives", [False, True])
def test_st07_simulated_unsynced_manifest_rename_reordering(
    tmp_path: Path, rename_survives: bool
) -> None:
    """An unsynced directory rename may survive or roll back after power loss.

    This explicitly simulates those filesystem images; it is not a claim to
    reproduce hardware power loss. Source deletion must remain after dir fsync.
    """
    script = r"""
import os, sys
from pathlib import Path
from pp_strata import Database
path, saved = map(Path, sys.argv[1:])
armed = False
def fail(name):
    if armed and name == "before_manifest_replace":
        saved.write_bytes((path / "MANIFEST").read_bytes())
    if armed and name == "after_manifest_replace":
        os._exit(81)
with Database.open(path, failpoint=fail) as db:
    with db.begin() as tx:
        tx.put(b"deleted", b"old")
        tx.put(b"retained", b"old")
    db.flush()
    with db.begin() as tx:
        tx.delete(b"deleted")
        tx.put(b"retained", b"new")
    db.flush()
    armed = True
    db.compact()
"""
    database = tmp_path / "db"
    saved = tmp_path / "old-manifest"
    process = subprocess.run([sys.executable, "-c", script, str(database), str(saved)], timeout=20)
    assert process.returncode == 81
    if not rename_survives:
        (database / "MANIFEST").write_bytes(saved.read_bytes())
    with Database.open(database) as db, db.snapshot() as snap:
        assert snap.get(b"deleted") is None
        assert snap.get(b"retained") == b"new"
        assert db.sequence == 2


@pytest.mark.parametrize("database_owner", [False, True])
def test_st08_wal_constructor_sync_failure_does_not_leak_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, database_owner: bool
) -> None:
    from pp_strata.wal.frames import WAL

    before = len(list(Path("/proc/self/fd").iterdir()))

    def fail_sync(path: Path) -> None:
        raise OSError(errno.EIO, "injected directory sync during WAL construction")

    with monkeypatch.context() as patch:
        patch.setattr("pp_strata.wal.frames.sync_directory", fail_sync)
        with pytest.raises(OSError, match="WAL construction"):
            if database_owner:
                Database.open(tmp_path / "database")
            else:
                WAL(tmp_path / "direct.wal")
    assert len(list(Path("/proc/self/fd").iterdir())) == before
    if database_owner:
        with Database.open(tmp_path / "database") as db:
            with db.begin() as tx:
                tx.put(b"retry", b"works")


@pytest.mark.parametrize(
    "field,value",
    [
        ("format", 999),
        ("format", True),
        ("format", None),
        ("source_sequence", True),
        ("source_sequence", -1),
        ("source_sequence", 2**64),
        ("source_sequence", "1"),
        ("source_sequence", None),
        ("records", True),
        ("records", -1),
        ("records", "1"),
        ("records", None),
        ("content_sha256", "f" * 63),
        ("content_sha256", "Z" * 64),
        ("content_sha256", None),
        ("unexpected_extension", "unsupported"),
    ],
)
def test_st08_backup_schema_rejected_before_source_open_or_destination_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    with Database.open(tmp_path / "source") as db:
        with db.begin() as tx:
            tx.put(b"key", b"value")
        db.backup(tmp_path / "backup")
    metadata = read_metadata(tmp_path / "backup" / "BACKUP")
    if value is None:
        del metadata[field]
    else:
        metadata[field] = value
    atomic_metadata(tmp_path / "backup" / "BACKUP", metadata)

    def forbid_open(*args: object, **kwargs: object) -> None:
        raise AssertionError("invalid backup metadata caused source-open side effects")

    monkeypatch.setattr(Database, "open", forbid_open)
    with pytest.raises(Corruption, match="backup metadata"):
        Database.restore(tmp_path / "backup", tmp_path / "restored")
    assert not (tmp_path / "restored").exists()

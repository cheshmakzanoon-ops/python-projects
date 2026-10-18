from __future__ import annotations

import errno
import fcntl
import os
from pathlib import Path

import pytest

from pp_strata import Closed, Corruption, Database
from pp_strata.codec.records import Record
from pp_strata.io import atomic_metadata
from pp_strata.wal.frames import WAL


def test_wal_rotation_retains_replacement_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "database"
    with Database.open(path) as db:
        with db.begin() as tx:
            tx.put(b"first", b"durable")
        real_open = os.open

        def fail_reopen(file: str | bytes | Path, flags: int, mode: int = 0o777) -> int:
            if file == path / "WAL" and flags == os.O_RDWR:
                raise OSError(errno.EMFILE, "cannot reopen a published replacement WAL")
            return real_open(file, flags, mode)

        with monkeypatch.context() as patch:
            patch.setattr(os, "open", fail_reopen)
            db.flush()
            with db.begin() as tx:
                tx.put(b"second", b"durable")
        assert not db.writer_failed
    with Database.open(path) as db, db.snapshot() as snapshot:
        assert list(snapshot.scan()) == [(b"first", b"durable"), (b"second", b"durable")]


@pytest.mark.parametrize("operation", ["os.fsync", "os.replace", "sync_directory"])
def test_wal_rotation_failure_closes_replacement_and_preserves_original_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    wal = WAL(tmp_path / "WAL")
    try:
        wal.append([Record(b"key", 1, b"durable")], sync=True)
        before = len(list(Path("/proc/self/fd").iterdir()))
        original = wal.fd

        def fail(*args: object) -> None:
            raise OSError(errno.EIO, "injected rotation failure")

        with monkeypatch.context() as patch:
            patch.setattr(f"pp_strata.wal.frames.{operation}", fail)
            with pytest.raises(OSError, match="rotation failure"):
                wal.rotate()
        assert len(list(Path("/proc/self/fd").iterdir())) == before
        assert wal.fd == original
        os.fstat(wal.fd)
    finally:
        wal.close()


@pytest.mark.parametrize("resource", ["wal", "table", "owner_unlock"])
def test_close_releases_every_resource_when_a_release_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, resource: str
) -> None:
    before = len(list(Path("/proc/self/fd").iterdir()))
    path = tmp_path / "database"
    db = Database.open(path)
    with db.begin() as tx:
        tx.put(b"key", b"durable")
    db.flush()
    if resource == "owner_unlock":
        real_flock = fcntl.flock

        def fail_unlock(fd: int, operation: int) -> None:
            real_flock(fd, operation)
            raise OSError(errno.EIO, "injected release failure")

        monkeypatch.setattr(fcntl, "flock", fail_unlock)
    else:
        target = db._wal if resource == "wal" else db._tables[0]
        real_close = target.close

        def fail_close() -> None:
            real_close()
            raise OSError(errno.EIO, "injected release failure")

        monkeypatch.setattr(target, "close", fail_close)
    with pytest.raises(OSError, match="release failure"):
        db.close()
    assert len(list(Path("/proc/self/fd").iterdir())) == before
    db.close()
    with pytest.raises(Closed):
        db.snapshot()
    monkeypatch.undo()
    with Database.open(path) as recovered, recovered.snapshot() as snapshot:
        assert snapshot.get(b"key") == b"durable"


def test_owner_lock_io_error_does_not_leak_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = len(list(Path("/proc/self/fd").iterdir()))

    def fail_lock(fd: int, operation: int) -> None:
        raise OSError(errno.EIO, "injected owner lock failure")

    monkeypatch.setattr(fcntl, "flock", fail_lock)
    with pytest.raises(OSError, match="owner lock failure"):
        Database.open(tmp_path / "database")
    assert len(list(Path("/proc/self/fd").iterdir())) == before


def test_failed_construction_releases_resources_despite_cleanup_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "database"
    with Database.open(path) as db:
        with db.begin() as tx:
            tx.put(b"key", b"durable")
        db.flush()
    before = len(list(Path("/proc/self/fd").iterdir()))
    real_close = WAL.close

    def fail_cleanup(self: Database) -> None:
        raise OSError(errno.EIO, "injected orphan cleanup failure")

    def fail_close(self: WAL) -> None:
        real_close(self)
        raise OSError(errno.EIO, "injected WAL close failure")

    with monkeypatch.context() as patch:
        patch.setattr(Database, "_cleanup_orphans", fail_cleanup)
        patch.setattr(WAL, "close", fail_close)
        with pytest.raises(OSError, match="WAL close failure"):
            Database.open(path)
    assert len(list(Path("/proc/self/fd").iterdir())) == before
    with Database.open(path) as recovered, recovered.snapshot() as snapshot:
        assert snapshot.get(b"key") == b"durable"


@pytest.mark.parametrize(
    "field,value",
    [("format", True), ("format", 1.0), ("sequence", 2**64), ("sequence", -1)],
)
def test_manifest_rejects_noncanonical_version_and_sequence(
    tmp_path: Path, field: str, value: object
) -> None:
    path = tmp_path / "database"
    path.mkdir()
    metadata: dict[str, object] = {"format": 1, "sequence": 0, "tables": []}
    metadata[field] = value
    atomic_metadata(path / "MANIFEST", metadata)
    with pytest.raises(Corruption, match="manifest schema"):
        Database.open(path)

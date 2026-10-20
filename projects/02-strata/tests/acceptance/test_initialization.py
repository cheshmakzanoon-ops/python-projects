from __future__ import annotations

import errno
import os
import stat
from pathlib import Path

import pytest

from pp_strata import Corruption, Database
from pp_strata.codec.records import Record, encode
from pp_strata.io import frame
from pp_strata.wal.frames import LEGACY_MAGIC, WAL


@pytest.mark.parametrize("flushed", [False, True])
def test_missing_wal_is_file_loss_not_an_empty_database(tmp_path: Path, flushed: bool) -> None:
    path = tmp_path / "database"
    with Database.open(path) as db:
        with db.begin() as tx:
            tx.put(b"acknowledged", b"durable")
        if flushed:
            db.flush()
    (path / "WAL").unlink()
    retained = {p.name: p.read_bytes() for p in path.iterdir()}

    with pytest.raises(Corruption, match="missing WAL"):
        Database.open(path)

    assert not (path / "WAL").exists()
    assert {p.name: p.read_bytes() for p in path.iterdir()} == retained


def test_initial_manifest_failure_can_retry_without_losing_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "database"

    def fail_publication(*args: object) -> None:
        raise OSError(errno.EIO, "initial manifest publication failed")

    with monkeypatch.context() as patch:
        patch.setattr("pp_strata.api.atomic_metadata", fail_publication)
        with pytest.raises(OSError, match="initial manifest"):
            Database.open(path)
    assert (path / "WAL").read_bytes() == b""
    assert not (path / "MANIFEST").exists()

    with Database.open(path) as db:
        with db.begin() as tx:
            tx.put(b"retried", b"durable")
    with Database.open(path) as db, db.snapshot() as snapshot:
        assert snapshot.get(b"retried") == b"durable"


def test_missing_manifest_does_not_initialize_over_nonempty_wal(tmp_path: Path) -> None:
    path = tmp_path / "database"
    with Database.open(path) as db:
        with db.begin() as tx:
            tx.put(b"acknowledged", b"durable")
    (path / "MANIFEST").unlink()
    retained = (path / "WAL").read_bytes()

    with pytest.raises(Corruption, match="missing manifest"):
        Database.open(path)

    assert not (path / "MANIFEST").exists()
    assert (path / "WAL").read_bytes() == retained


def test_initial_wal_sync_failure_does_not_publish_a_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "database"
    path.mkdir()
    before = len(list(Path("/proc/self/fd").iterdir()))
    real_sync = os.fsync

    def fail_regular_file_sync(fd: int) -> None:
        if stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(errno.EIO, "initial WAL synchronization failed")
        real_sync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail_regular_file_sync)
        with pytest.raises(OSError, match="initial WAL"):
            Database.open(path)
    assert len(list(Path("/proc/self/fd").iterdir())) == before
    assert (path / "WAL").read_bytes() == b""
    assert not (path / "MANIFEST").exists()
    with Database.open(path) as db:
        assert db.sequence == 0


@pytest.mark.parametrize("missing_prefix", [False, True])
def test_recovery_refuses_missing_complete_transactions(
    tmp_path: Path, missing_prefix: bool
) -> None:
    path = tmp_path / "database"
    with Database.open(path):
        pass
    batches = [Record(b"first", 1, b"a"), Record(b"last", 3, b"b")]
    if missing_prefix:
        batches = [Record(b"last", 2, b"b")]
    wal = b"".join(LEGACY_MAGIC + frame(encode([record])) for record in batches)
    (path / "WAL").write_bytes(wal)

    with pytest.raises(Corruption, match="WAL sequence gap"):
        Database.open(path)

    assert (path / "WAL").read_bytes() == wal


def test_wal_rejects_special_files_and_releases_its_descriptor(tmp_path: Path) -> None:
    path = tmp_path / "WAL"
    os.mkfifo(path)
    before = len(list(Path("/proc/self/fd").iterdir()))

    with pytest.raises(Corruption, match="regular file"):
        WAL(path)

    assert len(list(Path("/proc/self/fd").iterdir())) == before

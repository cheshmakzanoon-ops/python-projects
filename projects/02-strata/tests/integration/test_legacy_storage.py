from __future__ import annotations

import json
from pathlib import Path

from pp_strata import Database

FIXTURE = Path(__file__).parents[1] / "fixtures/legacy-v1.json"


def restore_fixture(root: Path, role: str) -> tuple[dict[str, object], Path]:
    fixture = json.loads(FIXTURE.read_text())
    path = root / role
    path.mkdir()
    for name, data in fixture[role].items():
        (path / name).write_bytes(bytes.fromhex(data))
    return fixture, path


def test_baseline_sstable_and_unflushed_v1_log_continue_and_restore(tmp_path: Path) -> None:
    fixture, path = restore_fixture(tmp_path, "database")
    expected = [(b"apple", b"new-red"), (b"plum", b"purple")]
    assert fixture["source_revision"] == "39d3a8d4be3e8e2e7de85379790d68f5367d6825"
    assert (path / "WAL").read_bytes().startswith(b"STW1")
    with Database.open(path) as db, db.snapshot() as old:
        assert db.sequence == 2
        assert list(old.scan()) == expected
        db.verify()
        with db.begin() as tx:
            tx.put(b"apple", b"v2-update")
            tx.delete(b"plum")
        db.compact()
        assert list(old.scan()) == expected
        db.backup(tmp_path / "historical-export", snapshot=old)
    Database.restore(tmp_path / "historical-export", tmp_path / "restored")
    with Database.open(tmp_path / "restored") as db, db.snapshot() as snapshot:
        assert list(snapshot.scan()) == expected
        db.verify()


def test_backup_written_by_baseline_restores_without_changing_source(tmp_path: Path) -> None:
    _, backup = restore_fixture(tmp_path, "backup")
    original = {p.name: p.read_bytes() for p in backup.iterdir()}
    report = Database.restore(backup, tmp_path / "restored")
    assert report["records"] == 2
    assert {p.name: p.read_bytes() for p in backup.iterdir()} == original
    with Database.open(tmp_path / "restored") as db, db.snapshot() as snapshot:
        assert list(snapshot.scan()) == [(b"apple", b"new-red"), (b"plum", b"purple")]

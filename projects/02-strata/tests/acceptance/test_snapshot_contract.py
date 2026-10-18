from __future__ import annotations

from pathlib import Path

import pytest

from pp_strata import Closed, Conflict, Database


def test_st04_snapshot_and_iterator_survive_compaction(tmp_path: Path) -> None:
    with Database.open(tmp_path / "db") as db:
        with db.begin() as tx:
            tx.put(b"a", b"first")
            tx.put(b"b", b"second")
        with db.snapshot() as old:
            iterator = old.scan()
            with db.begin() as tx:
                tx.put(b"a", b"updated")
                tx.delete(b"b")
                tx.put(b"c", b"new")
            db.flush()
            db.compact()
            assert old.get(b"a") == b"first"
            assert old.get(b"b") == b"second"
            assert list(old.scan()) == [(b"a", b"first"), (b"b", b"second")]
            assert list(iterator) == [(b"a", b"first"), (b"b", b"second")]
        db.compact()
        with db.snapshot() as current:
            assert list(current.scan()) == [(b"a", b"updated"), (b"c", b"new")]
        assert db.verify()["status"] == "passed"
    with Database.open(tmp_path / "db") as db, db.snapshot() as current:
        assert current.get(b"b") is None
        assert current.get(b"c") == b"new"


def test_st05_first_committer_wins_and_insert_delete(tmp_path: Path) -> None:
    with Database.open(tmp_path / "db") as db:
        first, second = db.begin(), db.begin()
        first.put(b"same", b"first")
        second.put(b"same", b"second")
        first.commit()
        with pytest.raises(Conflict):
            second.commit()
        old = db.begin()
        with db.begin() as tx:
            tx.put(b"absent", b"temporary")
        with db.begin() as tx:
            tx.delete(b"absent")
        db.compact()
        assert old.get(b"absent") is None
        old.put(b"absent", b"stale")
        with pytest.raises(Conflict):
            old.commit()
        # No active snapshot: compaction can remove the tombstone, but preserves
        # process-lifetime conflict heads for transactions begun before the edit.
        db.compact()
        with db.begin() as tx:
            tx.put(b"absent", b"new")


def test_st06_snapshot_isolation_allows_write_skew(tmp_path: Path) -> None:
    with Database.open(tmp_path / "db") as db:
        with db.begin() as tx:
            tx.put(b"doctor:a", b"on")
            tx.put(b"doctor:b", b"on")
        a, b = db.begin(), db.begin()
        assert a.get(b"doctor:b") == b.get(b"doctor:a") == b"on"
        a.put(b"doctor:a", b"off")
        b.put(b"doctor:b", b"off")
        a.commit()
        b.commit()
        with db.snapshot() as snap:
            assert list(snap.scan()) == [(b"doctor:a", b"off"), (b"doctor:b", b"off")]


def test_private_overlay_abort_context_and_bounds(tmp_path: Path) -> None:
    with Database.open(tmp_path / "db") as db:
        with db.begin() as tx:
            tx.put(b"a", b"old")
            tx.put(b"b", b"remove")
        before = db.sequence
        with pytest.raises(RuntimeError):
            with db.begin() as tx:
                tx.put(b"a", b"one")
                tx.put(b"a", b"two")
                tx.delete(b"b")
                tx.put(b"c", b"")
                assert tx.get(b"a") == b"two"
                assert tx.get(b"b") is None
                assert list(tx.scan(b"a", b"d")) == [(b"a", b"two"), (b"c", b"")]
                assert list(tx.scan(b"a", b"b")) == [(b"a", b"two")]
                with db.snapshot() as other:
                    assert other.get(b"a") == b"old"
                raise RuntimeError("abort")
        assert db.sequence == before
        with db.snapshot() as snap:
            assert list(snap.scan()) == [(b"a", b"old"), (b"b", b"remove")]
        with db.begin():
            pass
        assert db.sequence == before
        tx = db.begin()
        tx.abort()
        with pytest.raises(Closed):
            tx.get(b"a")
        with db.snapshot() as closed:
            pass
        with pytest.raises(Closed):
            closed.scan()


def test_st08_snapshot_backup_restore(tmp_path: Path) -> None:
    with Database.open(tmp_path / "db") as db:
        with db.begin() as tx:
            tx.put(b"a", b"old")
            tx.put(b"b", b"old")
        with db.snapshot() as old:
            with db.begin() as tx:
                tx.delete(b"a")
                tx.put(b"b", b"new")
            db.compact()
            report = db.backup(tmp_path / "backup", snapshot=old)
            assert report["records"] == 2
            assert report["source_sequence"] == old.sequence
        with pytest.raises(ValueError):
            db.backup(tmp_path / "backup")
        with pytest.raises(ValueError):
            db.backup(tmp_path / "db" / "nested")
    Database.restore(tmp_path / "backup", tmp_path / "restored")
    with Database.open(tmp_path / "restored") as restored, restored.snapshot() as snap:
        assert list(snap.scan()) == [(b"a", b"old"), (b"b", b"old")]


def test_db_close_and_configuration(tmp_path: Path) -> None:
    for kwargs in ({"durability": "invalid"}, {"memtable_bytes": 1}, {"cache_blocks": -1}):
        with pytest.raises(ValueError):
            Database.open(tmp_path / "db", **kwargs)  # type: ignore[arg-type]
    db = Database.open(tmp_path / "db", durability="flush", memtable_bytes=1024)
    with db.begin() as tx:
        tx.put(b"key", bytes(2000))
    assert db.inspect()["memtable_records"] == 0
    db.flush()
    db.close()
    db.close()
    with pytest.raises(Closed):
        db.begin()

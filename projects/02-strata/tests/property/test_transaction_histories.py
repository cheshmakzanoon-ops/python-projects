from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from pp_strata import Conflict, Database, Snapshot, Transaction


@dataclass
class Pending:
    handle: Transaction
    sequence: int
    base: dict[bytes, bytes]
    writes: dict[bytes, bytes | None] = field(default_factory=dict)

    def view(self) -> dict[bytes, bytes]:
        result = dict(self.base)
        for key, value in self.writes.items():
            if value is None:
                result.pop(key, None)
            else:
                result[key] = value
        return result


def exercise_history(seed: int, operations: int, path: Path) -> dict[str, int | str]:
    """Schedule overlapping writers against independent full dictionary copies."""
    rng = random.Random(seed)
    db = Database.open(path, memtable_bytes=2048, cache_blocks=2)
    visible: dict[bytes, bytes] = {}
    changed: dict[bytes, int] = {}
    pending: list[Pending] = []
    readers: list[tuple[Snapshot, int, dict[bytes, bytes]]] = []
    sequence = 0
    commits = conflicts = compactions = reopens = backups = 0

    def key() -> bytes:
        # Empty and prefix-related keys make ordering/range boundaries observable.
        if rng.randrange(20) == 0:
            return b""
        return [b"", b"prefix", b"prefix:"][rng.randrange(3)] + bytes([rng.randrange(24)])

    def commit(item: Pending) -> None:
        nonlocal sequence, commits, conflicts
        stale = any(changed.get(k, 0) > item.sequence for k in item.writes)
        if stale:
            with pytest.raises(Conflict):
                item.handle.commit()
            conflicts += 1
            return
        expected = sequence + bool(item.writes)
        assert item.handle.commit() == expected
        if item.writes:
            sequence = expected
            commits += 1
            for k, value in item.writes.items():
                changed[k] = sequence
                if value is None:
                    visible.pop(k, None)
                else:
                    visible[k] = value

    try:
        for index in range(operations):
            action = rng.randrange(15)
            if action == 0 and len(pending) < 8:
                pending.append(Pending(db.begin(), sequence, dict(visible)))
            elif action in (1, 2) and pending:
                item = rng.choice(pending)
                k = key()
                value = rng.randbytes(rng.randrange(40)) if action == 1 else None
                if value is None:
                    item.handle.delete(k)
                else:
                    item.handle.put(k, value)
                item.writes[k] = value
            elif action in (3, 4) and pending:
                item = rng.choice(pending)
                expected = item.view()
                k, stop = key(), key()
                assert item.handle.get(k) == expected.get(k)
                assert list(item.handle.scan(k, stop)) == [
                    (k2, value) for k2, value in sorted(expected.items()) if k <= k2 < stop
                ]
            elif action == 5 and pending:
                commit(pending.pop(rng.randrange(len(pending))))
            elif action == 6 and pending:
                pending.pop(rng.randrange(len(pending))).handle.abort()
            elif action == 7:
                db.flush()
            elif action == 8:
                db.compact()
                compactions += 1
                floor = min(
                    [item.sequence for item in pending] + [n for _, n, _ in readers],
                    default=sequence,
                )
                assert db._latest == {k: n for k, n in changed.items() if k in visible or n > floor}
            elif action == 9 and len(readers) < 6:
                readers.append((db.snapshot(), sequence, dict(visible)))
            elif action == 10 and readers:
                reader, at, expected = rng.choice(readers)
                assert reader.sequence == at
                assert list(reader.scan()) == sorted(expected.items())
                k = key()
                assert reader.get(k) == expected.get(k)
            elif action == 11 and readers:
                reader, _, expected = readers.pop(rng.randrange(len(readers)))
                detached = reader.scan()
                reader.close()
                db.compact()
                assert list(detached) == sorted(expected.items())
            elif action == 12:
                item = Pending(db.begin(), sequence, dict(visible))
                for _ in range(rng.randrange(1, 5)):
                    k = key()
                    value = None if rng.randrange(4) == 0 else rng.randbytes(rng.randrange(50))
                    item.writes[k] = value
                    if value is None:
                        item.handle.delete(k)
                    else:
                        item.handle.put(k, value)
                assert list(item.handle.scan()) == sorted(item.view().items())
                commit(item)
            elif action == 13 and readers:
                reader, _, expected = rng.choice(readers)
                with TemporaryDirectory(dir=path.parent) as temporary:
                    backup, restored = Path(temporary) / "backup", Path(temporary) / "restored"
                    report = db.backup(backup, snapshot=reader)
                    assert report["records"] == len(expected)
                    Database.restore(backup, restored)
                    with Database.open(restored) as copy, copy.snapshot() as snapshot:
                        assert list(snapshot.scan()) == sorted(expected.items())
                        copy.verify()
                backups += 1
            elif action == 14:
                loser = Pending(db.begin(), sequence, dict(visible))
                winner = Pending(db.begin(), sequence, dict(visible))
                k = key()
                previous = visible.get(k)
                winner.writes[k] = rng.randbytes(20)
                winner.handle.put(k, winner.writes[k])
                commit(winner)
                assert loser.handle.get(k) == previous
                loser.writes[k] = b"must-not-publish"
                loser.handle.put(k, b"must-not-publish")
                commit(loser)
            if index % 100 == 0:
                with db.snapshot() as snapshot:
                    assert list(snapshot.scan()) == sorted(visible.items())
                for item in pending:
                    assert list(item.handle.scan()) == sorted(item.view().items())
                db.verify()
            if index and index % 250 == 0:
                for item in pending:
                    commit(item)
                pending.clear()
                for reader, _, expected in readers:
                    assert list(reader.scan()) == sorted(expected.items())
                    reader.close()
                readers.clear()
                db.compact()
                db.close()
                db = Database.open(path, memtable_bytes=2048, cache_blocks=2)
                assert db.sequence == sequence
                reopens += 1
        for item in pending:
            commit(item)
        pending.clear()
        for reader, _, expected in readers:
            assert list(reader.scan()) == sorted(expected.items())
            reader.close()
        readers.clear()
        db.compact()
        db.verify()
        assert db._latest == {k: changed[k] for k in visible}
        db.close()
        db = Database.open(path)
        assert db.sequence == sequence
        with db.snapshot() as snapshot:
            assert list(snapshot.scan()) == sorted(visible.items())
        digest = hashlib.sha256()
        for k, value in sorted(visible.items()):
            digest.update(len(k).to_bytes(4) + k + len(value).to_bytes(4) + value)
        return {
            "seed": seed,
            "operations": operations,
            "commits": commits,
            "conflicts": conflicts,
            "compactions": compactions,
            "reopens": reopens,
            "snapshot_backups": backups,
            "final_sequence": sequence,
            "oracle_sha256": digest.hexdigest(),
        }
    finally:
        for item in pending:
            item.handle.abort()
        for reader, _, _ in readers:
            reader.close()
        db.close()


@pytest.mark.parametrize("seed", [0, 17, 1729, 65537])
def test_overlapping_transactions_survive_maintenance_and_recovery(
    tmp_path: Path, seed: int
) -> None:
    report = exercise_history(seed, 1000, tmp_path / "database")
    assert report["conflicts"] > 0
    assert report["reopens"] == 3
    assert report["snapshot_backups"] > 0

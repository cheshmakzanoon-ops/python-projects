from __future__ import annotations

import random
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given, settings
from hypothesis import strategies as st

from pp_strata import Database


def exercise(seed: int, operations: int, path: Path) -> None:
    rng = random.Random(seed)
    model: dict[bytes, bytes] = {}
    # Independent full dictionary copies are the reference version history.
    with Database.open(path, memtable_bytes=8192) as db:
        held = db.snapshot()
        historical = dict(model)
        for index in range(operations):
            key = f"key:{rng.randrange(60):03}".encode()
            choice = rng.randrange(10)
            if choice < 6:
                with db.begin() as tx:
                    if choice == 0:
                        tx.delete(key)
                        model.pop(key, None)
                    else:
                        value = rng.randbytes(rng.randrange(30))
                        tx.put(key, value)
                        model[key] = value
                    # Private scan independently compared before publication.
                    assert list(tx.scan()) == sorted(model.items())
            elif choice == 6:
                with db.snapshot() as snap:
                    assert snap.get(key) == model.get(key)
                    stop = f"key:{rng.randrange(60):03}".encode()
                    assert list(snap.scan(key, stop)) == [
                        (k, v) for k, v in sorted(model.items()) if key <= k < stop
                    ]
            elif choice == 7:
                db.flush()
            elif choice == 8:
                db.compact()
            else:
                assert list(held.scan()) == sorted(historical.items())
                held.close()
                held = db.snapshot()
                historical = dict(model)
            if index % 25 == 0:
                assert list(held.scan()) == sorted(historical.items())
                with db.snapshot() as snap:
                    assert list(snap.scan()) == sorted(model.items())
        assert list(held.scan()) == sorted(historical.items())
        held.close()
    with Database.open(path) as db, db.snapshot() as snap:
        assert list(snap.scan()) == sorted(model.items())


@given(st.integers(min_value=0, max_value=2**32 - 1))
@settings(max_examples=30, deadline=None)
def test_st01_seeded_versioned_oracle(seed: int) -> None:
    with TemporaryDirectory() as temporary:
        exercise(seed, 150, Path(temporary) / "db")


@given(st.lists(st.tuples(st.binary(max_size=30), st.binary(max_size=50)), max_size=60))
@settings(max_examples=40, deadline=None)
def test_random_binary_keys_and_batch_overlay(pairs: list[tuple[bytes, bytes]]) -> None:
    with TemporaryDirectory() as temporary, Database.open(temporary) as db:
        with db.begin() as tx:
            for key, value in pairs:
                tx.put(key, value)
            assert list(tx.scan()) == sorted(dict(pairs).items())
        db.compact()
        with db.snapshot() as snap:
            assert list(snap.scan()) == sorted(dict(pairs).items())

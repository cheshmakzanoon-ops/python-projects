from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pp_strata import Database


def test_concurrent_readers_never_observe_partial_batch(tmp_path: Path) -> None:
    with Database.open(tmp_path / "db", memtable_bytes=2048) as db:

        def writer() -> None:
            for i in range(50):
                with db.begin() as tx:
                    tx.put(b"left", str(i).encode())
                    tx.put(b"right", str(i).encode())
                if i % 10 == 0:
                    db.compact()

        def reader() -> None:
            for _ in range(100):
                with db.snapshot() as snap:
                    assert snap.get(b"left") == snap.get(b"right")
                    rows = dict(snap.scan())
                    assert rows.get(b"left") == rows.get(b"right")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(writer), *(executor.submit(reader) for _ in range(4))]
            for future in futures:
                future.result(timeout=30)

"""Seeded streaming workloads and an independent SQL complete-rebuild oracle."""

from __future__ import annotations

import hashlib
import json
import random
import sqlite3
import time
from collections.abc import Iterable, Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

from pp_quarry import Contract, Field, Lakehouse, Snapshot


def write_events(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w") as stream:
        for event in records:
            stream.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")


def make_event(
    key: int,
    version: int,
    value: float,
    *,
    day: int = 1,
    delete: bool = False,
    firmware: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "device": f"device-{key % 1000}",
        "day": f"2026-01-{day:02}",
        "value": value,
    }
    if firmware:
        payload["firmware"] = "v2"
    return {
        "source_namespace": "synthetic",
        "key": str(key),
        "version": version,
        "operation": "delete" if delete else "upsert",
        "payload": {} if delete else payload,
    }


def generate(directory: Path, count: int, seed: int) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    files = [
        directory / f"{name}.ndjson"
        for name in ("original", "late-updates", "deletes", "schema-evolution")
    ]
    write_events(
        files[0],
        (make_event(i, 1, float(rng.randrange(1000)), day=i % 28 + 1) for i in range(count)),
    )
    write_events(
        files[1],
        (make_event(i, 2, float(i % 777), day=(i + 5) % 28 + 1) for i in range(count // 10)),
    )
    write_events(files[2], (make_event(i, 3, 0, delete=True) for i in range(count // 50)))
    write_events(
        files[3],
        (make_event(i, 4, 10, day=i % 28 + 1, firmware=True) for i in range(min(count, 100))),
    )
    return files


def row_digest(rows: Iterable[tuple[str, str, int, str]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        )
        digest.update(b"\n")
    return digest.hexdigest()


def oracle(files: list[Path], path: Path) -> tuple[str, float]:
    """Independent rebuild: load ALL arrivals, SQL rank per key, then drop tombstones.

    Deliberately does not import production event parsing, version reduction, partitioning,
    source registry or execution SQL. SQLite bounds the reference model's working memory.
    """
    start = time.perf_counter()
    with closing(sqlite3.connect(path)) as db:
        db.execute(
            "CREATE TABLE arrivals(namespace TEXT,key TEXT,version INTEGER,operation TEXT,payload TEXT)"
        )
        for file in files:
            with file.open() as stream:
                for line in stream:
                    event = json.loads(line)
                    payload = json.dumps(
                        event["payload"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
                    )
                    db.execute(
                        "INSERT INTO arrivals VALUES (?,?,?,?,?)",
                        (
                            event.get("source_namespace", "default"),
                            event["key"],
                            event["version"],
                            event["operation"],
                            payload,
                        ),
                    )
        db.commit()
        sql = """SELECT namespace,key,version,payload FROM (
        SELECT *,row_number() OVER(PARTITION BY namespace,key ORDER BY version DESC) rank
        FROM arrivals) WHERE rank=1 AND operation='upsert' ORDER BY namespace,key"""
        digest = row_digest(db.execute(sql))
    return digest, time.perf_counter() - start


def actual(lake: Lakehouse) -> str:
    with Snapshot(lake.root) as view:

        def rows() -> Iterator[tuple[str, str, int, str]]:
            for row in view.rows():
                yield row["namespace"], row["key"], row["version"], row["payload"]

        return row_digest(rows())


def evolved_contract() -> Contract:
    return Contract({**Contract().fields, "firmware": Field("string", True)})

# Strata

Strata is an embedded key-value engine with snapshot-isolated transactions and
crash recovery. Its storage core implements a write-ahead log, an ordered
skip-list memtable, immutable sorted tables, Bloom filters, sparse indexes, and
compaction. Keys and values are bytes. No database library implements the storage
layer; SQLite is used only as an optional benchmark baseline.

A database has one owning process. Independent snapshots support concurrent
readers, while commits and maintenance serialize. First-committer-wins detects
write conflicts; reads do not enter the conflict set, so write skew is possible.
The durability contract requires Linux and a local POSIX filesystem with working
`fsync` and atomic rename. No service or credentials are required.

## Run the demonstration

From `projects/02-strata`, with uv 0.12.23:

```sh
uv sync --locked --python 3.14.8
uv run --locked python -m pp_strata.cli demo --output /tmp/strata-demo --seed 1729
uv run --locked python -m pp_strata.cli inspect /tmp/strata-demo/catalog
uv run --locked python -m pp_strata.cli clean-demo --output /tmp/strata-demo
```

Use a new absolute output path. The demo holds an old catalog snapshot through
an overwrite, deletion, flush, and compaction, then backs up and restores that
view. A separate owner process acknowledges ten transactions and exits after
syncing one additional batch. A fresh owner verifies that every acknowledged
write survived and the unacknowledged batch is whole. `demo.json` records the
checks; `timeline.txt` explains each transition.

## Use the library

```python
from pp_strata import Database

with Database.open("/tmp/example-strata", durability="sync") as db:
    with db.begin() as tx:
        tx.put(b"account:a", b"120")
        tx.put(b"account:b", b"80")

    with db.snapshot() as snapshot:
        assert snapshot.get(b"account:a") == b"120"
        print(list(snapshot.scan(start=b"account:", stop=b"account;")))
```

A successful transaction context exit commits; an exception aborts. `get` returns
`None` for absence and `b""` for a stored empty value. Scans are ordered and
half-open: `start <= key < stop`. Each scan materializes its result while holding
the database lock, so its iterator remains valid after compaction or handle
closure. Close snapshot and transaction handles promptly to release retained
versions. Do not share a handle between threads or inherit it across `fork`.

Keys are limited to 4 KiB, values to 1 MiB, and an encoded transaction to 16 MiB.
Size/type validation occurs before persistent mutation. In sync mode, successful
commit acknowledgement follows WAL synchronization. An I/O error can leave a
whole but unacknowledged batch; further writes fail with `WriterFailed` until
close and recovery. Application operation IDs are needed to resolve retry
ambiguity. See the [runbook](docs/OPERATIONS.md) before recovery or backup.

## Validate changes

```sh
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy src
uv run --locked pytest
uv build --python 3.14.8
```

Python 3.13.16 is also supported. Use a separate virtual environment when testing
the two interpreters, and run their builds sequentially. The acceptance suite
includes process termination, short writes, failed synchronization, malformed
files, missing log records, snapshot retention, backup integrity, and write skew.
The [verification record](docs/VERIFICATION.md) separates current checks from
historical large workloads.

The standard benchmark writes 250,000 initial records, runs 200,000 mixed
operations, and adds 50,000 hot-key churn operations. Full compaction, materialized
scans/backups, and per-key conflict metadata limit scale. Historical measurements
are in [benchmarks](docs/BENCHMARKS.md); they are not production-capacity claims.

Further reading: [architecture](docs/ARCHITECTURE.md),
[formats and design decisions](docs/DECISIONS.md),
[acceptance mapping](docs/ACCEPTANCE.md), [case study](docs/CASE_STUDY.md),
and [dependency and fixture provenance](docs/THIRD_PARTY.md).

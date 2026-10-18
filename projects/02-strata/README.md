# Strata

Strata is a small embedded LSM engine for versioned byte records. Its original
Python core implements binary transaction logs, an ordered skip-list memtable,
checksummed immutable blocks, stable Bloom filters, sparse indexes, snapshot
isolation, full compaction, and crash recovery. It uses no database library for
storage. SQLite appears only as an explicitly configured benchmark baseline.

One process owns a database. Threads may hold independent snapshots; commit
publication and maintenance serialize. Transactions use first-committer-wins
write conflicts. Snapshot isolation permits write skew: this is not a
serializable database. Linux on a local POSIX filesystem is the required tested
durability platform. No network service or credentials are required.

```sh
uv sync --locked --python 3.14.8
uv run --locked python -m pp_strata.cli demo --output /tmp/strata-demo --seed 1729
uv run --locked python -m pp_strata.cli inspect /tmp/strata-demo/catalog
uv run --locked python -m pp_strata.cli clean-demo --output /tmp/strata-demo
```

The demo first retains a catalog snapshot through overwrite, deletion, flush,
and compaction, then backs it up and restores it. After closing all handles,
a subprocess owns a separate database, acknowledges ten transactions, and
terminates after syncing an additional batch. A fresh owner verifies recovery.
The output includes `demo.json` and a readable `timeline.txt`.

```python
from pp_strata import Database

with Database.open("/tmp/example-strata", durability="sync") as db:
    with db.begin() as tx:  # normal exit commits; exceptional exit aborts
        tx.put(b"account:a", b"120")
        tx.put(b"account:b", b"80")
    with db.snapshot() as snapshot:
        assert snapshot.get(b"account:a") == b"120"
        print(list(snapshot.scan(start=b"account:", stop=b"account;")))
```

For a deliberate failure, inspect `tests/acceptance/test_faults.py`: its child
processes terminate at WAL, table, manifest, and retirement boundaries. The
failed-sync test demonstrates a poisoned writer, readable old snapshots,
recovery of a complete unacknowledged batch, and sequence advancement.

```sh
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy src
uv run --locked pytest --cov --cov-report=term-missing
uv build
uv run --locked python benchmarks/extended_stateful.py --output /tmp/strata-extended.json
uv run --locked python -m pp_strata.cli benchmark --profile ci --output /tmp/strata-bench --seed 1729
```

The standard profile generates 250,000 initial 16-byte keys / 256-byte values,
200,000 mixed operations, and a separate 50,000-operation hot-key churn phase.
Run it alone. See [architecture](docs/ARCHITECTURE.md),
[formats and tradeoffs](docs/DECISIONS.md), [runbook](docs/OPERATIONS.md),
[acceptance mapping](docs/ACCEPTANCE.md), [measurements](docs/BENCHMARKS.md),
and [case study](docs/CASE_STUDY.md). Current verification is recorded in
[agent status](docs/AGENT_STATUS.md).

# Anchor

A durable workflow engine for declarative, versioned DAGs. Anchor coordinates
activities, timers, signals and compensation across process failures. PostgreSQL
holds ordered history and task projections; a deterministic reducer reconstructs
state and detects incompatible replay. Activities execute at least once, so external
effects need a stable idempotency key and an explicit cancellation contract.

## Run the recovery demonstration

Use Linux, uv 0.12.23, and an owned PostgreSQL database. From the repository root,
`python scripts/services.py up anchor` starts a loopback PostgreSQL container and
prints its connection URL. Export that URL as `ANCHOR_DATABASE_URL`, then run from
this directory:

```sh
uv sync --locked --python 3.14.8
uv run --locked python -m pp_anchor.cli demo --output /tmp/anchor-demo --seed 1729
uv run --locked python -m pp_anchor.cli clean-demo --output /tmp/anchor-demo
```

The output directory must be empty. The demonstration exports 60 synthetic rows,
joins CSV partitions into a deterministic ZIP, consumes an approval signal and
persists a timer. It kills a worker after provider publication but before the durable
acknowledgement. A replacement reclaims the lease and finishes with one logical
publication. Inspect `history.json`, `timeline.txt` and `dataset.zip` before cleanup.
Cleanup removes only marked output and its dedicated database schema.

## Python interface

```python
import asyncio
import os

from pp_anchor import Definition, Engine, Step, drain

with Engine(os.environ["ANCHOR_DATABASE_URL"], schema="anchor_local") as engine:
    definition = Definition("hello", 1, (Step("first"), Step("last", after=("first",))))
    run_id = engine.submit(definition, {"message": "hello"}, "request-1")
    asyncio.run(drain(engine))
    assert engine.replay(run_id).status == "completed"
```

`ActivityRegistry.register(name, handler)` registers async activities. A handler's
`ActivityContext.task` contains payload, attempt number and lease epoch;
`ActivityContext.business_key` remains stable across retries. Epoch checks fence
stale engine updates. They cannot stop an external effect already in progress.
The included synthetic provider persists a cancellation fence; another provider
must supply equivalent guarantees before claiming full cancellation.

## Development

```sh
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy src
uv run --locked pytest
uv build
```

Persistence tests require `ANCHOR_DATABASE_URL` and fail explicitly when it is absent.
Use `pytest tests/unit` for database-free boundary and reducer tests. CPython 3.13.16
is also supported; use a separate environment when testing interpreter compatibility.

The [HTTP API](docs/HTTP_API.md) is a trusted local control plane on port 8101, without
authentication. Keep it on loopback. The [runbook](docs/OPERATIONS.md) covers workers,
schedulers, diagnosis and checksummed backup/restore. Review [architecture](docs/ARCHITECTURE.md),
[decisions](docs/DECISIONS.md), [acceptance](docs/ACCEPTANCE.md),
[benchmarks](docs/BENCHMARKS.md), [case study](docs/CASE_STUDY.md) and
[verification records](docs/VERIFICATION.md) for contracts and measured limits.

For code review, start with `persistence/engine.py::_append` for atomic history and
projection updates, `replay/reducer.py::decide` for deterministic commands, and
`tests/integration/test_process_fencing.py` for a real resumed stale process.

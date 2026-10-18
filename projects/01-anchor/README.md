# Anchor

Anchor coordinates declarative export workflows across process failures. Its original
core is a deterministic DAG reducer and a PostgreSQL transaction adapter: history,
logical scheduling, lease epochs, and terminal transitions commit together. Psycopg
supplies the driver, asyncio supplies bounded workers, and FastAPI supplies the local
control plane. It does not serialize suspended Python call stacks.

```bash
uv sync --locked --python 3.13.16
# Supply ANCHOR_DATABASE_URL for an owned PostgreSQL database.
uv run --locked python -m pp_anchor.cli demo --output /tmp/anchor-demo --seed 1729
uv run --locked python -m pp_anchor.cli clean-demo --output /tmp/anchor-demo
```

The demo generates CSV partitions, joins them into a deterministic ZIP, consumes early
approval, persists a timer, and kills a worker after publication but before its durable
acknowledgement. Another worker reclaims the epoch and finishes. `history.json` and
`timeline.txt` show one logical provider publication and verified replay.

```python
import asyncio
from pp_anchor import Definition, Engine, Step, drain

# dsn is supplied by the caller, never embedded in definitions or history.
with Engine(dsn, schema="anchor_local") as engine:
    definition = Definition("hello", 1, (Step("first"), Step("last", after=("first",))))
    run_id = engine.submit(definition, {"message": "hello"}, "request-1")
    asyncio.run(drain(engine))
    assert engine.replay(run_id).status == "completed"
```

Custom async activities register through `ActivityRegistry.register(name, handler)`.
Their `ActivityContext` exposes a stable `business_key`, task payload, attempt, and
lease epoch. External effects must honor their own stable business idempotency key.
The included provider demonstrates this contract and a persistent cleanup fence.

Run `uv run --locked python -m pp_anchor.cli --help` for submit, inspect, replay,
worker, scheduler, serve, demo, benchmark and owned cleanup commands. The control API
binds to loopback at port 8101; it has no authentication and assumes trusted local users.

See [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md),
[operations](docs/OPERATIONS.md), [acceptance](docs/ACCEPTANCE.md),
[benchmarks](docs/BENCHMARKS.md), and the [case study](docs/CASE_STUDY.md).
PostgreSQL process-failure tests require Linux and a real service; pure reducer and
packaging checks do not require a database. The supported interpreter floor is 3.13.

For source review, start at `persistence/engine.py::_append` (atomic history/projection),
`replay/reducer.py::decide` (command replay), and `tests/integration/test_process_fencing.py`
(real resumed stale process). Local verification: 54 tests pass on both 3.13.16 and 3.14.8;
final committed portfolio checks and standard benchmark remain coordinator-owned gates.

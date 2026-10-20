# Current

Current is an event-time stream processor for device readings and metadata. It implements watermarks, late corrections, tumbling and sliding aggregates, and interval joins. A SQLite journal preserves the order of events and control records so a restart reproduces the same admission decisions and output revisions.

The runtime runs in one process with one state owner. Keyed asyncio workers prepare records; the state machine applies them in durable order. SQLite commits the processing prefix, operator state, local results, and external delivery outbox together. No broker, daemon, database server, or credentials are required.

## Run the demonstration

From this project directory, on Linux with uv 0.12.23:

```sh
uv sync --locked --python 3.14.8
uv run --locked --python 3.14.8 python -m pp_current.cli demo --output /tmp/current-demo --seed 1729
uv run --locked --python 3.14.8 python -m pp_current.cli inspect --output /tmp/current-demo
uv run --locked --python 3.14.8 python -m pp_current.cli clean-demo --output /tmp/current-demo
```

Use a fresh absolute output directory. The demo processes 10,000 events from four source partitions, pauses and resumes a source, introduces late records, and terminates a child immediately before checkpoint publication. The deliberate child exit is 73; the parent must finish successfully and report `oracle_matches: true`.

`report.json` contains disposition and recovery metrics; `results.json` retains logical output keys and revisions for downstream upserts. Cleanup removes only the selected directory bearing Current's ownership marker. Before repeating a demo, clean its owned output or choose a fresh path.

## Embed the runtime

```python
import asyncio
from pathlib import Path

from pp_current import Config, Journal, Record, Runtime, canonical

journal = Journal(Path("/tmp/current-example.sqlite"))
try:
    journal.admit(
        [
            Record("sensor", 0, 0, 100, "room", 12),
            Record("sensor", 0, 1, kind="end"),
        ]
    )
    config = Config((canonical(["sensor", 0]),))
    asyncio.run(Runtime(journal, journal.recover(config)).run())
    print(journal.export())
finally:
    journal.close()
```

Admission identity is `(source_id, partition, source_offset)`: an identical retry returns the same ordinal, and conflicting reuse fails atomically. Event IDs do not deduplicate distinct offsets. Times are integer milliseconds; negative timestamps are supported. Windows are half open, join bounds are inclusive, and an event exactly at `watermark - lateness` is accepted. Idle inputs must explicitly resume; end-of-input is terminal. If every unfinished input is idle, progress freezes until one resumes or all end.

External delivery uses `Journal.pending(limit)`, `IdempotentSink.put(delivery)`, then `Journal.acknowledge(delivery)`. Acknowledgement follows the sink commit. Immutable payload identities detect conflicting retries, and an older revision never overwrites a newer result. Publication is atomic within the journal; delivery between databases is at least once with idempotent effects in the supplied sink. A stale Engine cannot overwrite another committed checkpoint. Cancellation waits for submitted database work to settle before returning; recover after any failed/cancelled run.

## Validate and operate

```sh
uv run --locked --python 3.14.8 ruff format --check .
uv run --locked --python 3.14.8 ruff check .
uv run --locked --python 3.14.8 mypy src
uv run --locked --python 3.14.8 pytest
uv build --python 3.14.8
```

Python 3.13.16 is also supported; use a separate `UV_PROJECT_ENVIRONMENT` as described in [operations](docs/OPERATIONS.md). The [verification record](docs/VERIFICATION.md) separates current checks from historical benchmark evidence.

Checkpoint `current-3` requires rebuilding older checkpoints from retained ingress. The [runbook](docs/OPERATIONS.md#rebuild-a-current-1current-2-checkpoint) provides configuration-preserving export/replay commands and downstream reconciliation requirements.

See [architecture](docs/ARCHITECTURE.md) for transaction boundaries, [decisions](docs/DECISIONS.md) for persisted contracts, [acceptance](docs/ACCEPTANCE.md) for invariant-to-test mappings, and [benchmarks](docs/BENCHMARKS.md) for measured costs. Current retains ingress and delivery history and has finite admission, outbox, state, and database-page budgets. It does not provide distributed ownership, dynamic rescaling, or a bounded-memory batch exporter. The [case study](docs/CASE_STUDY.md) explains the replay and measurement tradeoffs.

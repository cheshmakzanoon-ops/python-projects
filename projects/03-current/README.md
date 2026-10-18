# Current

Current computes event-time device aggregates and bounded metadata joins from delayed records. It journals the exact event/control interleaving, then publishes a consistent processing prefix, operator state, local results, and an external-sink outbox in one SQLite transaction.

The original Python core implements monotonic minimum-input watermarks, explicit idle/resume, negative-time half-open tumbling/sliding windows, late revisions, interval-join expiration, stable routing, and bounded asyncio preparation. SQLite supplies durable transactions; Typer supplies CLI parsing. This is a single-machine runtime with a fixed worker count, not a distributed broker.

```bash
uv sync --locked --python 3.13.16
uv run --locked python -m pp_current.cli demo --output /tmp/current-demo --seed 1729
uv run --locked python -m pp_current.cli inspect --output /tmp/current-demo
uv run --locked python -m pp_current.cli benchmark --profile ci --output /tmp/current-bench --seed 1729
uv run --locked python -m pp_current.cli clean-demo --output /tmp/current-demo
```

Choose fresh absolute output directories. The demo processes 10,000 events across four source partitions, pauses a source, journals watermarks and late records, exits a child process immediately before checkpoint publication, recovers, and compares final windows/joins and event dispositions with an independent batch oracle. A nonzero child exit of 73 is the deliberate failure. `results.json` preserves the complete logical output identity and revision for downstream upserts.

```python
from pathlib import Path
import asyncio
from pp_current import Config, Journal, Record, Runtime, canonical

journal = Journal(Path("/tmp/current-example.sqlite"))
journal.admit(
    [
        Record("sensor", 0, 0, 100, "room", 12),
        Record("sensor", 0, 1, kind="end"),
    ]
)
config = Config((canonical(["sensor", 0]),))
asyncio.run(Runtime(journal, journal.recover(config)).run())
print(journal.export())
journal.close()
```

Admission identity is `(source_id, partition, source_offset)`. Event IDs do not deduplicate distinct offsets. Times use integer milliseconds, including negative timestamps. An event at exactly `watermark - lateness` is accepted. Join bounds are inclusive. An idle source must explicitly resume before producing another event.

Read [architecture](docs/ARCHITECTURE.md), [contracts and decisions](docs/DECISIONS.md), [operations](docs/OPERATIONS.md), [acceptance mapping](docs/ACCEPTANCE.md), [benchmark methodology](docs/BENCHMARKS.md), and the [case study](docs/CASE_STUDY.md). [Current verification state](docs/AGENT_STATUS.md) distinguishes local validation from coordinator review.

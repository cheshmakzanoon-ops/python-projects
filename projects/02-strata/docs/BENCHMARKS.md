# Measurements

The CI profile run passed on CPython 3.14.8, Linux x86-64, seed 1729,
using 2,000 initial 16-byte keys / 256-byte values, 2,000 mixed operations, and
a separate 2,000-operation churn phase. This is a development snapshot, with
the actual source digest and dirty flag in
[`artifacts/benchmark-ci.json`](../artifacts/benchmark-ci.json).
It ran on the shared cloud machine after the preliminary extended run stopped. These are reproducible smoke-workload measurements, not capacity claims
or a reliable engine ranking.

```sh
uv run --locked python -m pp_strata.cli benchmark --profile ci --output /absolute/new-output --seed 1729
```

| Metric | Actual development run |
| --- | --- |
| Initial durable batches of 100 | 2,000 records / 0.05554 s |
| Mixed point-read latency, median / p95 | 14.15 µs / 32.45 µs |
| Write-or-batch latency, median / p95 | 0.5214 ms / 2.172 ms |
| Full compaction stall | 0.06822 s |
| Reopen and validated recovery | 0.01793 s |
| Peak process RSS including independent oracle | 25,010,176 bytes |
| Final disk size / live-byte space amplification | 527,782 bytes / 1.066× |
| WAL + table bytes / logical mutation bytes | 2.723× |
| Whole-workload block-read bytes / requested read-value bytes | 2.488× |
| Churn disk bytes before / after compaction | 427,301 / 19,640 |

The mixed workload and churn each run once. Durable-commit comparisons use one
warmup plus five measured repetitions for each engine/batch size; each timed
repetition writes the same 200 records. Strata uses `durability="sync"`; SQLite
uses one connection, `journal_mode=WAL`, `synchronous=FULL`, and the same
transaction batch sizes. Directory initialization and schema creation are
outside timed sections. The SQLite connection closes after each repetition;
Strata also closes. Neither benchmark disables synchronization or TLS/checksum
verification. The kernels and metadata differ; equality of selected durability
settings does not make the implementations identical.

| Configuration | Median seconds for 200 records | Range over five runs |
| --- | --- | --- |
| Strata, durable single writes | 0.1024 | 0.09032–0.1132 |
| Strata, durable batches of 100 | 0.002210 | 0.002068–0.002502 |
| SQLite, durable single writes | 0.08776 | 0.08728–0.1083 |
| SQLite, durable batches of 100 | 0.001628 | 0.001289–0.002232 |

An earlier run during active extended testing varied much more widely; its
[retained initial report](../artifacts/benchmark-ci-initial.json) shows why a
shared-host smoke sample cannot establish a stable comparative ranking. Batching amortizes synchronization cost in both engines.
The source implements a larger standard profile: 250,000 initial records,
200,000 mixed operations, a separate 50,000-operation hot-key churn phase, and
2,000-record commit comparisons. Its required measured run is reserved for the
coordinator's exclusive resource lease and immutable committed source. It is
not claimed completed here until its report is added.

Profiling one 5,000-operation extended correctness seed under shared load took
29.684 s: 3,176 `fsync` calls consumed 15.650 s, and 1,067 snapshot/range scans
9.315 s. The run includes real synchronization and repeated historical/recovery
checks. It is a correctness workload, not a throughput test. Full compaction and
materialized scans are the main algorithmic limits; a measured future improvement
would use version-pinned streaming iterators and a bounded leveled compactor.

Counter limits: read amplification includes maintenance reads and is a
whole-workload ratio; the OS cache is warm and never forcibly dropped. RSS
includes the dictionary oracle. Block caches are 32 blocks per table, and the
default memtable threshold is 8 MiB. Table bytes written include flush and
compaction output; filesystem journaling/controller writes are not measured.
CPU, memory cgroup, interpreter, source/lock/contract hashes, raw repetitions,
and correctness checks are in the JSON artifact. Final immutable verification
must supersede these provisional dirty-source measurements.

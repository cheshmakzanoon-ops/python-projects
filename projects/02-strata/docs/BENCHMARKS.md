# Measurements

## Accepted committed standard run

The standard workload passed on CPython 3.14.8, Linux x86-64, seed 1729, at
source `59443e2bcdfc6a1dd81f8334c108474eef2d3030`. It generated **250,000
initial 16-byte keys / 256-byte values, 200,000 mixed operations, and a separate
50,000-operation hot-key churn phase**. The [raw report](../../../docs/evidence/final/standard/strata-3.14.8-benchmark-benchmark.json)
contains exact parameters, repetitions, environment, hashes and correctness
checks; its [outer verification wrapper](../../../docs/evidence/final/standard/strata-3.14.8.json)
confirms clean committed source, unchanged hashes and successful command exits.
The [public demo report](../../../docs/evidence/final/standard/strata-3.14.8-demo-demo.json)
also passed at that source.

```sh
uv run --locked python -m pp_strata.cli benchmark --profile standard --output /absolute/new-output --seed 1729
```

| Metric | Accepted standard run |
| --- | --- |
| Initial durable batches of 100 | 250,000 records / 6.108 s; 40,927 records/s |
| Mixed point-read latency, median / p95 | 0.4527 ms / 1.143 ms |
| Write-or-batch latency, median / p95 | 0.5131 ms / 1.615 ms |
| Full compaction stall | 2.231 s |
| Reopen and validated recovery | 1.682 s |
| Peak process RSS including independent oracle | 316,174,336 bytes |
| Final disk size / live-byte space amplification | 67,490,354 bytes / 1.066× |
| WAL + table bytes / logical mutation bytes | 2.774× |
| Whole-workload block-read bytes / requested read-value bytes | 216.55× |
| Churn disk bytes before / after compaction | 10,196,594 / 19,641 |

Durable-commit comparisons below use 2,000 records per repetition, one warmup
and five measured repetitions per engine/batch size. Both use one process and
one thread: Strata syncs the WAL per commit, while SQLite uses WAL mode and
`synchronous=FULL` with the same records and transaction batch sizes.

| Configuration | Median seconds for 2,000 records | Range over five runs | Median records/s |
| --- | --- | --- | --- |
| Strata, durable single writes | 0.9188 | 0.8459–1.1383 | 2,177 |
| Strata, durable batches of 100 | 0.03127 | 0.02874–0.06790 | 63,963 |
| SQLite, durable single writes | 0.9872 | 0.6778–1.5516 | 2,026 |
| SQLite, durable batches of 100 | 0.02859 | 0.01771–0.03525 | 69,959 |

All independent mixed point-read, full-scan before/after compaction, recovered
scan, comparison-count and unchanged-source checks passed. The larger read
amplification reflects block-granularity reads and maintenance in the numerator;
it is a whole-workload byte ratio rather than an isolated per-request I/O count.
The OS page cache was not dropped. These variable local synthetic measurements
show the synchronization/batching tradeoff and the cost of larger tables; they
do not establish a general ranking against SQLite or production capacity.

The separate full extended correctness workload passed **100 seeds × 5,000
operations = 500,000 operations**, using independent dictionary and historical
snapshot oracles at source `9218b77769cef807700d67f8a0c2b97512b9cc0e`. Its
[raw results](../../../docs/evidence/final/strata-extended/strata-extended.json)
and [verification wrapper](../../../docs/evidence/final/strata-extended/strata-3.14.8.json)
record every seed, clean source and unchanged hashes. Compatibility also passed
on both [3.13.16](../../../docs/evidence/final/python313/strata-3.13.16.json) and
[3.14.8](../../../docs/evidence/final/python314/strata-3.14.8.json); the default is
3.14.8.

## Historical development CI measurements

The earlier CI profile run passed on CPython 3.14.8, Linux x86-64, seed 1729,
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
The accepted larger standard profile and 2,000-record commit comparisons are
reported above. These earlier dirty-source captures remain historical context
and are superseded by the committed standard and compatibility evidence.

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
and correctness checks are in the respective JSON artifacts. The accepted
committed-source wrappers above supersede these provisional development
measurements without changing their historical meaning.

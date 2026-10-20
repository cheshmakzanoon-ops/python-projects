# Benchmarks

## Focused join comparison

The [October 20 core comparison](evidence/core-join-2026-10-20.json) runs immutable baseline `39d3a8d4be3e8e2e7de85379790d68f5367d6825` and the reviewed working tree in separate CPython 3.14.8 subprocesses. It applies 12,000 same-key readings without intervening watermarks, one sparse metadata probe, then end-of-input. Each version runs three repetitions, with no warmup. Every repetition verifies the same five exact pair identities, two window aggregates with count/sum 12,000, delivery order and complete final expiration.

| Measurement | Baseline full scan | Indexed lazy merge |
| --- | ---: | ---: |
| Median apply time, seconds | 1.408118 | 0.169456 |
| Candidate examinations | 72,006,000 | 6 |
| Process RSS high-water mark, bytes | 22,282,240 | 23,396,352 |

The old count is the exact full-scan formula `n*(n-1)/2 + n`; the new count is the engine's consumed-candidate diagnostic. Eliminating same-stream scans reduced apply time by about 8.3 times in this particular retention-heavy sparse-probe workload. The derived index adds references and bucket/list overhead; this measurement does not establish a memory improvement. RSS includes all allocations in the isolated probe process, including its prepared record list, imports and staged outputs. It is not an engine-only byte budget.

Reproduce from this project directory with a fresh report filename:

```sh
uv run --locked --python 3.14.8 python benchmarks/join_density.py \
  --baseline 39d3a8d --output /tmp/current-join-comparison.json
```

The driver reads trusted historical Git objects into a temporary source tree without changing the checkout, uses the same interpreter for both versions, checks unchanged current source before/after, and refuses to overwrite evidence. The report records the full baseline commit, current source/test/config digest, driver/probe hashes, exact samples and scope. The current digest is `91924a0db27061e07bd36c72669dfb4f5fedb014334b2d19ac89dc7fd82f812f`; the report explicitly marks that source as an uncommitted working tree. There is no random generator in this probe. Shared-machine timing and one synthetic shape do not establish general throughput or production capacity. Dense opposite-stream matches still cost one delivery per matching pair, and watermark pruning still examines retained state.

## Historical standard workload

The accepted standard measurement uses clean committed source [ec1d0106df086a48923016c33199cfbda0aebbc0](https://github.com/cheshmakzanoon-ops/python-projects/tree/ec1d0106df086a48923016c33199cfbda0aebbc0/projects/03-current), CPython 3.14.8 and seed 1729. The [raw benchmark](../../../docs/evidence/final/standard/current-3.14.8-benchmark-benchmark.json) contains all checkpoint samples and parameters; the [execution record](../../../docs/evidence/final/standard/current-3.14.8.json) records the exact command, immutable source inputs, hashes, exit status and unchanged-source check.

| Measurement | Ordinary | Separate 50%-hot-key run |
|---|---:|---:|
| Events / journal records including controls | 1,000,000 / 1,004,006 | 1,000,000 / 1,004,006 |
| Durable admission seconds | 52.4883 | 49.1270 |
| Processing/checkpoint seconds | 242.7666 | 289.8364 |
| Processing throughput, events/s | 4,119.1834 | 3,450.2228 |
| Latest logical result rows | 2,531,862 | 4,389,302 |
| On-time / accepted-late / rejected-late | 989,398 / 7,155 / 3,447 | 989,401 / 7,212 / 3,387 |
| Runtime buffer peak, records | 53 | 95 |
| Retained operator-state peak, entries | 4,584 | 2,905 |
| Observed SQLite main/WAL bytes | 1,679,376,416 | 2,739,242,104 |
| Full raw-control oracle reconciliation | passed | passed |

Every event is accounted for in the three disposition categories. Rejected-late inputs follow the explicit lateness policy and remain in the journal; they are not silent losses. There are 4,006 additional control records per workload. Queue peaks stay within the configured 128-record cap, and the observed SQLite main/WAL totals stay below the 4 GiB run budget. The SQLite page budget itself limits the main database, rather than providing a whole-filesystem quota.

The process RSS high-water mark after both workloads and hot cleanup was **12,177,899,520 bytes (approximately 11.34 GiB)**. This is one serial process-wide maximum including warmup, ordinary and hot execution, the full raw trace, millions of exported/reference result objects, Python and native SQLite allocations. It measures the complete benchmark/validation process; it does not isolate engine memory or add independent worker RSS. Four keyed workers are asyncio tasks in this process. Low retained operator-state counts therefore do not establish low total benchmark memory. A bounded streaming exporter and independent external-state validator are justified future work; they are not implemented performance improvements.

Throughput divides event count by runtime processing/checkpoint time. It excludes durable admission, final-checkpoint restore, result export and independent batch-oracle reconciliation. The full benchmark command, including warmup and both validated runs, took **896.7549 seconds**. Reported restore times reopen the final checkpoint after end-of-input has expired operator state; they do not measure restoration of a large midstream checkpoint. Maximum watermark lag was 101,900 ms and finalization lag 113,000 ms in both workloads. These are event-time measurements; the final end-of-input sentinel is excluded, and finalization lag is watermark minus window end rather than wall-clock latency.

`benchmark --profile ci|standard --output FRESH_PATH --seed 1729` writes `benchmark.json`. CI uses 10,000 generated events per measured repetition across four partitions. Standard uses 1,000,000 events, 10,000 key choices, approximately 256-byte envelopes, 10% delayed timestamps, an explicit idle/resume interval, 30-second windows, 10-second allowed lateness, inclusive 5-second joins, four workers and checkpoints every 10,000 journal records. Inputs are generated locally. Both profiles run one bounded 10,000-event warmup and a separate 50%-hot-key workload. CI has five ordinary repetitions. Standard has one full ordinary and one full hot measurement under the documented run-cost exception: repeated durable admission, millions of output publications and complete independent reconciliation make five large repetitions costly. Its `measurement_runs=1` and reason are explicit; these single-run timings are not a latency distribution or controlled optimization comparison.

Both profiles compare full finalized results and dispositions with the independent oracle. Accepted CI evidence is in the clean [3.13 record](../../../docs/evidence/final/python313/current-3.13.16.json) and [3.14 record](../../../docs/evidence/final/python314/current-3.14.8.json), including their linked five-repetition benchmark reports. Source `b3caa0e4594034ee8edf9ca05c3fd879d6fe18a2` passed 32 tests on each interpreter, including the regression proving RSS is sampled after the hot workload and cleanup.

Provenance has two explicit scopes. The raw benchmark digest covers sorted package Python files, Python tests, pyproject.toml, uv.lock and .python-version, with each relative path followed by file bytes; documentation/results are excluded. Its standard source digest is `903fc1bb243389940ce9f4b53c392fa962e08d08d2de1406c92880b6f90b62eb`. The execution wrapper records its own complete `source_inputs` and broader root-contract inputs; its project digest `c8f3435c518bd48e45805db9a11c8d91d08108d59471f10e776735d7f3106eca` agrees between the accepted compatibility and standard records. These digest definitions are distinct. The shared lock hash is `baf15ac83a35752ad671410a6466a49a8b6f5b43d6210beed3cb3bd6982239a3`.

The raw portable runner reports CPU as unknown because `platform.processor()` was empty and container memory limit as null because it has no portable limit probe. Neither field changes the measured RSS scope. Historical development artifacts and [pre-fix/canceled attempts](../../../docs/evidence/final/attempts/current-rss-before-hot/) remain available for provenance. Their pre-hot RSS values are superseded and are not accepted whole-process memory evidence. No result establishes production capacity or a throughput target; hot-key join cardinality and full oracle/export cost are part of the measured workload.

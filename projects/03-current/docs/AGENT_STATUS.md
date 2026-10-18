# Current agent status

Status: complete for Current's required project behavior and accepted local verification. Owner A03. Source, tests, dependencies and runtime writes are paused. The coordinator owns final portfolio publication, remote synchronization and remote CI claims.

## Implemented and verified

Public interfaces are `Record`, `Config`, `Journal`, `Engine`, `Runtime`, `Delivery`, `IdempotentSink`, stable `partition_for` and canonical JSON; CLI commands are `demo`, `benchmark`, `clean-demo`, `inspect` and `replay`. The implementation covers durable ordered event/control admission, watermarks/idleness, tumbling/sliding aggregates, bounded interval joins, late revisions and rejection, atomic checkpoint/local-sink/outbox publication, independent greatest-revision sink behavior and explicit resource budgets. [ACCEPTANCE.md](ACCEPTANCE.md) maps CU-01–CU-08 to executable evidence.

Accepted clean compatibility verification at `b3caa0e4594034ee8edf9ca05c3fd879d6fe18a2`:

- [CPython 3.13.16](../../../docs/evidence/final/python313/current-3.13.16.json): full check, demo and five-repetition CI benchmark passed; **32 tests passed in 18.26 seconds**.
- [CPython 3.14.8](../../../docs/evidence/final/python314/current-3.14.8.json): full check, demo and five-repetition CI benchmark passed; **32 tests passed in 14.77 seconds**.
- The linked check logs record Ruff format/lint, strict mypy for 21 source files, tests, wheel/source builds and installed-wheel smoke validation. Default Python is 3.14.8; 3.13.16 remains required and supported. Both records have `source_dirty=false` and `source_unchanged_after=true`.
- New RSS regression cases deliberately increase a mocked high-water mark only in the hot workload and assert sampling after its execution/cleanup. Both failed before the ordering fix and pass after it. Earlier local 30-test/98%-core-coverage logs in artifacts are historical development evidence, rather than the final 32-test records.

## Accepted full standard evidence

The [standard execution record](../../../docs/evidence/final/standard/current-3.14.8.json) passed on immutable committed source [ec1d0106df086a48923016c33199cfbda0aebbc0](https://github.com/cheshmakzanoon-ops/python-projects/tree/ec1d0106df086a48923016c33199cfbda0aebbc0/projects/03-current), CPython 3.14.8. The [raw metrics](../../../docs/evidence/final/standard/current-3.14.8-benchmark-benchmark.json) record seed 1729, SQLite WAL/FULL durability, one bounded 10,000-event warmup, one ordinary million-event measurement and a separate million-event 50%-hot-key measurement. The explicit run-cost repetition exception applies to standard; CI retains five ordinary measurements.

Both workloads contain 1,004,006 journal records including controls, and both match the full independent raw event/control oracle. Ordinary/hot processing rates were **4,119.1834 / 3,450.2228 events/s**, from **242.7666 / 289.8364 processing seconds**. Admission took **52.4883 / 49.1270 seconds**. Latest output counts were **2,531,862 / 4,389,302**. Ordinary dispositions were 989,398 on-time, 7,155 accepted-late and 3,447 rejected-late; hot dispositions were 989,401, 7,212 and 3,387. Each set sums to one million events, with no silent discard.

Corrected process RSS after both workloads and hot cleanup was **12,177,899,520 bytes (approximately 11.34 GiB)**. It includes full trace/export/reference objects and native SQLite in one serial benchmark process, so it cannot be attributed to isolated engine state or summed independent worker RSS. Ordinary/hot runtime buffer peaks were **53 / 95**, retained operator-state peaks **4,584 / 2,905**, and observed main/WAL disk bytes **1,679,376,416 / 2,739,242,104**, below the 4 GiB run budget. Processing throughput excludes admission, final-checkpoint restore and full export/oracle bookkeeping; the complete benchmark command took 896.7549 seconds. Maximum watermark/finalization lags **101,900 / 113,000 ms** are event-time values with the final sentinel excluded.

The raw benchmark source digest is `903fc1bb243389940ce9f4b53c392fa962e08d08d2de1406c92880b6f90b62eb`. The execution-wrapper project digest is `c8f3435c518bd48e45805db9a11c8d91d08108d59471f10e776735d7f3106eca`, matching the accepted compatibility records under that wrapper's recorded input scope. The lock hash is `baf15ac83a35752ad671410a6466a49a8b6f5b43d6210beed3cb3bd6982239a3`. These evidence scopes have different digest definitions; [BENCHMARKS.md](BENCHMARKS.md) explains them. Earlier pre-hot RSS/canceled runs remain in [attempts](../../../docs/evidence/final/attempts/current-rss-before-hot/) and do not supply the accepted standard result.

The recorded [Current→Quarry integration](../../../docs/evidence/final/python314/stream-lake/integration.json) passed at its stated source `7114e39c7e9e8af177e84fe8cd990fe5a09bde63`, preserving delivery identity, late revisions, retries and historical snapshots. Its source scope remains explicit; this documentation update does not relabel that run.

## Limits and handoff

No required Current gate or external dependency remains open in the accepted local evidence. Single owner/fixed topology, integer-millisecond timestamps, explicit late policy, retained ingress/delivery history and finite logical budgets remain operational limits. The main-database page cap is not a filesystem quota, and process-exit tests do not simulate power failure. Full batch validation/export requires substantial memory; a bounded streaming exporter and independent validator are justified future work, not a completed optimization.

This update changes only CASE_STUDY.md, BENCHMARKS.md, AGENT_STATUS.md and ACCEPTANCE.md. No source, tests or locks changed; no validation commands, benchmarks or Git mutations were run for it. Active edits: none after this handoff; all writes paused for coordinator review/commit. Resume only on coordinator followup and inspect the accepted evidence/source before changing anything.

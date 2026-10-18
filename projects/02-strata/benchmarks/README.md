# Workloads

The installed CLI implements `benchmark --profile ci|standard --output ABS
--seed 1729`. CI uses 2,000 initial rows and 2,000 mixed operations; standard uses
250,000 rows and 200,000 mixed operations, plus separate hot-key churn. Both
measure durable batch-1 and batch-100 workloads against SQLite WAL/FULL using
one warmup plus five timed repetitions per configuration. Generated state is
kept in the caller's marked output directory.

`extended_stateful.py` is the required 100 × 5,000 mixed-operation correctness
suite. Its independent dictionary oracle includes copied historical states,
conflict histories, aborts, bounded range reads, periodic flush/compaction, and
recovery. It writes per-seed summaries with source and environment provenance.
Pass `--jobs 2` for two independent spawn workers, with deterministic seed-order
aggregation and atomic checkpoints. `--resume` continues a matching partial
report; changed source or workload settings are rejected. The default remains
one worker. Example: `uv run --locked python benchmarks/extended_stateful.py
--jobs 2 --output /tmp/strata-extended.json`.

No benchmark result is claimed by the existence of a runner. See
`../docs/BENCHMARKS.md` for actual results and limitations.

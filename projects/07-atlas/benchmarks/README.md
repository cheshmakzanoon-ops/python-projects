# Benchmark entry point

## Bounded query allocation diagnostic

```sh
uv run --locked python benchmarks/query_memory.py --output /absolute/fresh-report.json
```

This separate probe uses 1,000 and 5,000 ID-ordered documents containing the same
eight query terms. It loads the generation before measuring, then checks exact
top-ten IDs, total, eight-term explanations and cached-result equality. Each size
has one uncached and one cached sample under `tracemalloc`; measurements include
query allocations, not index loading, process RSS, concurrency or capacity.

[Before](../artifacts/query-memory-before.json) and
[after](../artifacts/query-memory-after.json) retain their actual dirty-checkout
source/input digests. The before capture used the baseline retrieval implementation
with the new diagnostic/regression files; it is not a pristine committed-snapshot
benchmark. A separate [baseline reproduction record](../artifacts/core-baseline-reproductions.json)
ran 17 deliberately failing regressions with source extracted from `39d3a8d`.

The changes bound retained explanation dictionaries to the returned page and skip
an ACL scan on a valid cache hit. Visibility/candidate sets, full-match facets,
per-tenant loaded generations and O(segment count) stat checks remain. The source
contains a deterministic rare-phrase probe: a 100,000-position common list and a
single rare anchor require fewer than 32 common-list reads, versus 100,000 in the
baseline. Exhaustive sliding-window tests establish its phrase semantics.

These probes do not update the historical standard-workload evidence below.

## Standard workload

The installed implementation is `pp_atlas.benchmarks.run_benchmark`, reached through
`python -m pp_atlas.cli benchmark --profile ci|standard --output ABS --seed 1729`.
The workload schema, distributions and actual development measurements are in
[docs/BENCHMARKS.md](../docs/BENCHMARKS.md). Use five measurements after warmup.

Only the coordinator runs standard under an exclusive resource lease on an
immutable committed source snapshot. Pin OMP_NUM_THREADS, OPENBLAS_NUM_THREADS and
MKL_NUM_THREADS to1. Keep large runtime outputs outside tracked source.

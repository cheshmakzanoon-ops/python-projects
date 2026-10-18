# Benchmark evidence

The checked-in [CI result](../artifacts/ci-benchmark.json) is an actual development run on CPython 3.14.8, Linux x86-64, Intel Xeon Platinum 8573C, a 32 GiB cgroup limit and seed 1729. Its source is explicitly dirty; source, root-contract, lock and dataset SHA-256 values identify the tested development snapshot. It is not final clean-commit evidence.

| Measurement | Actual result |
| --- | --- |
| Workload | 50 reviewed fixture files, 5,600 source lines, plus ten graph files/19 lines |
| Cold analysis, five runs | 3.742, 4.014, 3.191, 3.609, 3.621 seconds; median 3.621 s |
| Unchanged cached analysis, five runs | 0.169, 0.105, 0.137, 0.176, 0.121 seconds; median 0.137 s |
| Changed graph root | 0.376 seconds; exactly ten dependent files invalidated |
| Parse failures | 0 |
| Reviewed positive labels | 350; exact rule/line matches, precision 1.0 and recall 1.0 on these fixtures only |
| Peak Python traced allocation | 67,979,081 bytes |
| Analyzer process peak RSS | 55,812,096 bytes |
| Maximum child peak RSS | 55,369,728 bytes; max over children, not sum or simultaneous peak |
| Correctness | Cold/cache equivalence, incremental/clean equivalence, dependency closure and all labels passed |

These contextual variants are correlated and authored with known outcomes. Perfect scores establish the fixture contract, not broad security accuracy. SQL protocol conservatism, unknown calls and unsupported language constructs remain explicit limitations. Shared-host scheduling affects timings; no production throughput claim or cross-machine speed comparison is made. Tracemalloc and OS RSS account for different allocation scopes; neither child RSS nor the reported values establish a summed peak across the machine.

The standard generator is implemented: 2,240 reviewed-template replicas grouped ten per file produce 250,880 source lines, plus the graph. It records a content-pinned original synthetic corpus without third-party downloads. It reports throughput/invalidation; precision and recall are null for this larger workload. One cold measurement bounds subprocess cost and five warm measurements are retained. **Standard execution is pending the coordinator's exclusive run on an immutable committed source export.** No standard measurements are invented.

Run:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run --locked python -m pp_pytrace.cli benchmark --profile ci --output /tmp/pytrace-ci --seed 1729
# Run alone under the coordinator resource lease:
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run --locked python -m pp_pytrace.cli benchmark --profile standard --output /tmp/pytrace-standard --seed 1729
```

The versioned result schema requires `schema_version=1`, project, source_commit (nullable if unavailable), source_dirty, source_scope, source_content_sha256, root_contract_sha256, lockfile_sha256, python, os, cpu, memory_limit_bytes, seed, profile, dataset_id, parameters, warmup_runs, measurement_runs, metrics, correctness_checks and status. Metrics contain finite durations, counts, memory observations and fixture accuracy when defined; null means deliberately unavailable, with its limitation stated. Status is passed only when all domain correctness checks succeed. `source_digest_unchanged` confirms the source scope before/after execution. Exact source input paths are emitted and exclude generated reports/artifacts, avoiding a self-reference.

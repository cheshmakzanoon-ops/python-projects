# Benchmark evidence

The standard benchmark ran from immutable source commit `59443e2bcdfc6a1dd81f8334c108474eef2d3030`, with `source_dirty: false`. The [raw benchmark report](../../../docs/evidence/final/standard/pytrace-3.14.8-benchmark-benchmark.json) records the workload and measurements; the [verification wrapper](../../../docs/evidence/final/standard/pytrace-3.14.8.json) records the exact dispatcher commands, successful exit codes and unchanged source scope. Their hashes cover explicitly different input lists; use each report's declared scope rather than treating their digests as interchangeable.

| Final standard measurement | Actual result |
| --- | --- |
| Workload | 234 files; 2,240 synthetic fixture variants grouped ten per file, 250,880 fixture lines plus 19 graph lines: 250,899 total |
| Cold analysis | One measured run: 72.576544 seconds |
| Unchanged cached analysis, five runs | 2.784376, 3.254818, 3.497081, 3.184808, 3.308253 seconds; median 3.254818 s |
| Changed graph root | 1.085980 seconds; exactly ten dependent files invalidated |
| Parse failures | 0 |
| Peak Python traced allocation | 339,695,450 bytes |
| Analyzer process peak RSS | 960,466,944 bytes |
| Maximum child peak RSS | 960,466,944 bytes; neither summed nor a simultaneous machine peak |
| Correctness | Cache/clean equivalence and dependency-closure checks passed; source digest unchanged |
| Accuracy | Precision/recall null, zero labeled cases in the scale report; no accuracy claim for this generated workload |

The content-pinned standard corpus is original synthetic source with correlated contextual variants, not an independently labeled accuracy dataset. The documented cost exception uses one cold run to bound parser subprocess cost and five measured warm runs. Cold versus warm is descriptive, not a comparison of two five-run distributions. The raw report's `labels_exact` check verifies replicated expected positions; it does not make the scale corpus an independent accuracy evaluation.

The following CI capture remains historical development evidence.

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

The standard generator deterministically groups 2,240 reviewed-template replicas ten per file and records a content-pinned corpus without third-party downloads. Its accepted immutable run is reported above. Historical dirty development captures are preserved under artifacts rather than relabeled as clean-commit evidence.

Run:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run --locked python -m pp_pytrace.cli benchmark --profile ci --output /tmp/pytrace-ci --seed 1729
# Run the standard profile without other benchmarks:
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run --locked python -m pp_pytrace.cli benchmark --profile standard --output /tmp/pytrace-standard --seed 1729
```

The versioned result schema requires `schema_version=1`, project, source_commit (nullable if unavailable), source_dirty, source_scope, source_content_sha256, root_contract_sha256, lockfile_sha256, python, os, cpu, memory_limit_bytes, seed, profile, dataset_id, parameters, warmup_runs, measurement_runs, metrics, correctness_checks and status. Metrics contain finite durations, counts, memory observations and fixture accuracy when defined; null means deliberately unavailable, with its limitation stated. Status is passed only when all domain correctness checks succeed. `source_digest_unchanged` confirms the source scope before/after execution. Exact source input paths are emitted and exclude generated reports/artifacts, avoiding a self-reference.

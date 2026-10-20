# Workloads

`semantic_scaling.py` is a focused 100/300/900-function analysis-only exercise.
It excludes parsing, caching and I/O from timing, records three repeats and
requires one shell finding per generated function. The imported package path,
Python-file hash and identical source hashes make historical exports comparable.
See [the core review](../docs/CORE_REVIEW.md) for the measured scope and limits.

`generate_corpus.py` materializes the reviewed deterministic scenarios and their declared line/rule labels without importing the analyzer. Committed `tests/fixtures/labeled` files are the accuracy oracle, not dynamically generated expected answers.

Run `uv run --locked python -m pp_pytrace.cli benchmark --profile ci --output /tmp/pytrace-ci --seed 1729`. The CI profile analyzes all 50 files/5,600 source lines and a separate ten-module dependency graph, with one warmup, five cold measurements, five cached measurements, and a changed graph dependency compared to a clean analysis.

The standard profile deterministically materializes 2,240 reviewed-template contextual replicas (250,880 source lines) plus the dependency graph. It pins corpus bytes by SHA-256 in each report. This original synthetic corpus needs no external download or third-party license. Contextual variants and replicas are correlated; accuracy is reported only as performance on the original reviewed scenarios. Standard performs one cold timing and five warm timings to bound subprocess cost; that exception and its statistical limit are explicit in the JSON. Run the standard profile without other benchmarks to limit resource contention.

Peak Python allocation is measured with tracemalloc; it does not include parser-process RSS or all native allocations. Reports identify the limitation rather than claim full machine memory usage. Source/lock/config fingerprints are captured before and after execution. Results belong outside tracked source; small measured examples can be copied to `artifacts` after review.

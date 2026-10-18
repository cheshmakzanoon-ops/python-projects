# Benchmark entry point

The shipped `pp_meridian.workloads.benchmark` is the workload implementation, shared by the installed CLI. It is not a separate benchmark-only accounting path: all measured journals use the production transaction service and PostgreSQL constraints. See docs/BENCHMARKS.md for exact sizes, sampling limits, repetitions, source provenance, and the exclusive standard-run policy.

# Benchmark entry point

The installed implementation is `pp_atlas.benchmarks.run_benchmark`, reached through
`python -m pp_atlas.cli benchmark --profile ci|standard --output ABS --seed 1729`.
The workload schema, distributions and actual development measurements are in
[docs/BENCHMARKS.md](../docs/BENCHMARKS.md). Use five measurements after warmup.

Only the coordinator runs standard under an exclusive resource lease on an
immutable committed source snapshot. Pin OMP_NUM_THREADS, OPENBLAS_NUM_THREADS and
MKL_NUM_THREADS to1. Keep large runtime outputs outside tracked source.

# Seeded benchmark entry point

The installed runner is `python -m pp_quarry.cli benchmark --profile ci|standard --output ABSOLUTE_PATH --seed 1729`. Generator and independent SQL complete-rebuild reference are installed in `pp_quarry.workloads`; provenance is in `pp_quarry.evidence`. Keeping these in the wheel makes benchmarks reproducible from a clean installation outside the repository.

See docs/BENCHMARKS.md for workload sizes, repetitions, fsync/cache settings and metrics. Heavy standard runs require the repository coordinator's exclusive resource slot.

`uv run --locked --python 3.14.8 python benchmarks/verify_incremental.py --output /tmp/quarry-correctness-50000 --rows 50000 --buckets 8 --seed 1729` runs the separate seven-publication correctness exercise. Set OPENBLAS_NUM_THREADS, OMP_NUM_THREADS and MKL_NUM_THREADS to 1. It checks independent facts/daily rebuilds after each phase, pinned results, exact identities, retention/restart and historical conflicts; it retains reproducible inputs and report under a fresh owned output directory. The [retained report](../artifacts/deep-correctness-2026-10-20.json) and [limitations](../docs/BENCHMARKS.md#focused-incremental-correctness-exercise-2026-10-20) describe the actual 50,000-original run. This source-tree diagnostic is not installed as a CLI and is not a performance benchmark.

# Seeded benchmark entry point

The installed runner is `python -m pp_quarry.cli benchmark --profile ci|standard --output ABSOLUTE_PATH --seed 1729`. Generator and independent SQL complete-rebuild reference are installed in `pp_quarry.workloads`; provenance is in `pp_quarry.evidence`. Keeping these in the wheel makes benchmarks reproducible from a clean installation outside the repository.

See docs/BENCHMARKS.md for workload sizes, repetitions, fsync/cache settings and metrics. Heavy standard runs require the repository coordinator's exclusive resource slot.

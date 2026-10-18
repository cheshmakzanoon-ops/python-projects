# Workload generation

The executable runner is the installed `pp_anchor.benchmark` module, exposed through
`anchor benchmark --profile ci|standard --output ABS --seed 1729`. It generates independent
five-activity workflow DAGs, injects a first-attempt failure at step s2 for every twentieth
input identity, uses two schedulers and bounded workers, then independently counts SQL
attempts, completed runs and orphan tasks. A separate 100,000-row timer projection fixture
measures idle queue behavior; it is not misrepresented as 100,000 complete workflows.
A lease-abandonment probe measures retry recovery and idempotent publication. The demo's
separate true process-kill scenario supplies the stronger process-boundary failure evidence.

See docs/BENCHMARKS.md for profile sizes, repetitions and actual provenance. BLAS/OpenMP
threads must be pinned to one in shared comparisons. Standard workloads require an
exclusive resource lease from the coordinator. Reports are written outside tracked source.

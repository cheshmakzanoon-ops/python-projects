# Development evidence

Small records here identify actual dirty development snapshots. They are excluded
from the measured source digest to avoid self-reference. They do not replace the
final immutable-commit checks or serial standard benchmark.

`development-summary.json` records the dual-interpreter commands, installed-wheel
smoke and CI measurement summary. Full generated outputs remain outside tracked
source in `/workspace/.results/routecraft-*`. Small authentic tiny-instance sample
JSON and SVG artifacts live in `../../artifacts/` with a snapshot manifest.

`core-insertion-2026-10-20.json` preserves a bounded dirty-snapshot comparison
against the exact insertion source from `39d3a8d`. It records three paired sizes,
raw timings, complete route-scheduling work, plan equality, an independent verifier
check and a regret-path control. Its source digest covers code/tests/configuration,
not this evidence directory or later documentation. The reproducible driver is
documented in [benchmarks](../../benchmarks/README.md); this diagnostic does not
replace the historical standard workload or final committed-source checks.

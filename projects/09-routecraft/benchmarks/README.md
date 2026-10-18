# Benchmark entry point

The installed entry point is `python -m pp_routecraft.cli benchmark --profile
ci|standard --output ABS --seed 1729`. Implementation and schema live in
`pp_routecraft.benchmark`; all actual fixtures come from `pp_routecraft.fixtures`.
The standard profile requires the coordinator's exclusive measurement lease.
See `docs/BENCHMARKS.md` for measurement counts, caps, interpretation and provenance.

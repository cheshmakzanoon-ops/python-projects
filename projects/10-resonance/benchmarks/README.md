# Workload entry point

`python -m pp_resonance.cli benchmark --profile ci|standard --output ABS --seed 1729` executes `pp_resonance.benchmark.benchmark`. Generator source lives in synthesis/tones.py; result JSON schema and exact denominator are documented in docs/BENCHMARKS.md and docs/FIXTURES.md. No external dataset download is needed. Standard duration is exactly 600 seconds; sample chunks are at most 8,192 and retained overlap at most 2,047 samples.

`uv run --locked python benchmarks/core_review.py --output /tmp/resonance-core.json`
is a separate bounded core exercise: three 100/300/600-reference-note alignment
sizes, three repetitions each, and one 12-second dynamic-amplitude phrase. It
also records mathematical/ownership/denominator witnesses. Thread settings,
historical snapshot reproduction and raw comparisons are documented in
[CORE_REVIEW.md](../docs/CORE_REVIEW.md). Workload and dataset hashes must match
before comparing reports. Its shared-host timings do not replace the historical
exclusive standard workload or establish real-recording accuracy.

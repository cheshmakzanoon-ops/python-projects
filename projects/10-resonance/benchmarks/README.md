# Workload entry point

`python -m pp_resonance.cli benchmark --profile ci|standard --output ABS --seed 1729` executes `pp_resonance.benchmark.benchmark`. Generator source lives in synthesis/tones.py; result JSON schema and exact denominator are documented in docs/BENCHMARKS.md and docs/FIXTURES.md. No external dataset download is needed. Standard duration is exactly 600 seconds; sample chunks are at most 8,192 and retained overlap at most 2,047 samples.

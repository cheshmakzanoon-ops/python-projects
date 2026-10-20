# Benchmark entry point

The installed entry point is `python -m pp_routecraft.cli benchmark --profile
ci|standard --output ABS --seed 1729`. Implementation and schema live in
`pp_routecraft.benchmark`; all actual fixtures come from `pp_routecraft.fixtures`.
The standard profile requires the coordinator's exclusive measurement lease.
See `docs/BENCHMARKS.md` for measurement counts, caps, interpretation and provenance.

The focused insertion diagnostic compares exact plans and complete route-scheduling
work with the historical insertion implementation. From this project directory:

```sh
git show 39d3a8d4be3e8e2e7de85379790d68f5367d6825:projects/09-routecraft/src/pp_routecraft/construction/insertion.py > /tmp/routecraft-baseline-insertion.py
uv run --locked --python 3.14.8 python benchmarks/insertion_work.py \
  --baseline-file /tmp/routecraft-baseline-insertion.py \
  --output /tmp/routecraft-insertion-work.json
```

The driver checks the baseline file's exact SHA-256 before importing it, alternates
pair order, verifies all plans, compares complete plans and rejects source changes.
It uses 40/80/160 broad-window stops on one vehicle, three pairs per size and a
40-stop regret control. The report path must be fresh. Recorded work counters
exclude certificate arithmetic, profile construction and verification; timings
are development diagnostics and do not establish standard-workload capacity.

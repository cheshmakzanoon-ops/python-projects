# Benchmarks

The ci profile admits 100 workflows of five short activities; standard admits 5,000.
Both use two independent schedulers and configurable bounded worker concurrency. One
warmup precedes five measured ci repetitions. The full standard workload uses one measured
repetition because five full durable runs would take over an hour on this development
host; its report records measurement_runs=1 and this cost justification. Throughput includes admission and completion,
with offered/completed counts separately recorded and independently counted attempt/task
correctness. Persistence retains PostgreSQL synchronous commit and ordinary durability.
A separate isolated projection probe loads 100,000 future timer rows and measures idle
scheduler memory/latency without allocating one suspended coroutine per timer.

Commands: `uv run --locked python -m pp_anchor.cli benchmark --profile ci --output
/absolute/empty/path --seed 1729`; replace profile with standard under the coordinator's
exclusive resource lease. Runtime reports are outside tracked source; small authentic
samples will be copied under artifacts after source validation. Current measurements
are in progress; no performance claim is made from a scaffold or synthetic target.

Reports carry exact source/lock/root-contract hashes, actual commit and dirty flag,
interpreter/OS/CPU/cgroup memory, generator identity, profile, parameters and repetitions.
Generated reports and docs are excluded from their own source digest. This development
host is shared; standard results require serialized workload and still do not establish
production capacity. The current implementation replays short histories on each mutation;
long histories are an explicit scalability boundary.

Development baseline before queue index refinements: five ci repetitions (100 workflows,
500 logical activities) completed in 18.05, 17.98, 39.47, 25.31 and 48.85 seconds. Median
throughput was 3.95 workflows/s on a contended shared host. The 100,000 future-timer idle
probe took 0.059 seconds with 0 KiB additional peak RSS. Source digest and environment
are in the actual development report outside tracked source. These results predate the
final source, are not a controlled optimization comparison, and do not establish capacity.
Queue inspection motivated partial active-run and per-run readiness indexes, avoiding
scanning old terminal runs during admission/claim. Final immutable verification remains.

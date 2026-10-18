# Benchmarks

The ci profile admits 100 workflows of five activities; standard admits 5,000. Both use
two schedulers, eight worker slots in the accepted runs, one numerical-library thread,
PostgreSQL synchronous_commit=on and fsync=on. Every twentieth workflow fails step s2 on
its first attempt, then retries. Throughput includes admission and execution; accepted and
completed load and SQL activity/attempt counts are recorded separately.

One bounded warmup precedes five measured ci repetitions. Standard uses one full measured
repetition under the explicitly recorded costly-workload exception, chosen from earlier
contended-host estimates. The actual serialized result below was faster than those estimates;
this single full measurement does not estimate run-to-run variance. A separate isolated
projection probe loads 100,000 future timers without allocating suspended timer coroutines.
The lease recovery probe abandons a lease after its provider effect; the separate demo
supplies the real process-kill failure evidence.

## Accepted immutable results

The [compatibility matrix](../../../docs/evidence/README.md) records both required
interpreters. These ci results tested clean source
`7114e39c7e9e8af177e84fe8cd990fe5a09bde63`:

| Profile / interpreter | Measured runs | Median workflows/s | Evidence |
| --- | ---: | ---: | --- |
| ci / 3.13.16 | 5 | 16.0532 | [wrapper](../../../docs/evidence/final/python313/anchor-3.13.16.json), [raw](../../../docs/evidence/final/python313/anchor-3.13.16-benchmark-benchmark.json) |
| ci / 3.14.8 | 5 | 15.7232 | [wrapper](../../../docs/evidence/final/python314/anchor-3.14.8.json), [raw](../../../docs/evidence/final/python314/anchor-3.14.8-benchmark-benchmark.json) |
| standard / 3.14.8 | 1 | 21.4381 | [wrapper](../../../docs/evidence/final/standard/anchor-3.14.8.json), [raw](../../../docs/evidence/final/standard/anchor-3.14.8-benchmark-benchmark.json) |

The full standard source was `59443e2bcdfc6a1dd81f8334c108474eef2d3030`. Its wrapper
confirms clean source, unchanged inputs afterward and the same project/lock digest as the
compatibility checks. Every wrapper lists its source inputs and shared-contract digest;
raw reports retain their own narrower hashing scope. Do not equate differently scoped hashes.
The default interpreter is now 3.14.8; compatibility with 3.13.16 remains required.

The standard workload completed **5,000 offered / 5,000 completed workflows**, **25,000
logical activities**, **25,250 attempts** and **250 retries**, with **zero orphan tasks**:

| Measurement | Actual result |
| --- | ---: |
| Admission + completion time | 233.229274 s |
| Admission time | 34.996824 s |
| Workflow throughput | 21.438132 workflows/s |
| Admitted queue depth | 5,000 |
| Created-to-start p95 | 189.675463 s |
| Ready-to-start p95 | 153.450591 s |
| Expired leases during main workload | 0 |
| Owned database size after completion | 66,019,328 bytes |
| Process peak RSS | 42,652 KiB |
| Future-timer projection rows | 100,000 |
| Future-timer idle tick | 0.024154 s |
| Future timers fired / added peak RSS | 0 / 0 KiB |
| Separate lease-recovery probe | 0.144759 s |

This is a burst workload: all runs are admitted before workers execute the backlog.
The large queue delays follow that offered-load pattern; 21.44 workflows/s is not a
low-latency service guarantee. The timer probe measures an isolated future-timer projection,
not 100,000 complete workflows. The recovery figure includes the probe's deliberately short
lease wait; it does not establish recovery time under every deployment or provider failure.
The host reported an Intel Xeon Platinum 8573C and a 32 GiB cgroup memory limit. Serialized
synthetic measurements do not establish production capacity or universal power-loss safety.

## Reproduction and provenance

```bash
uv run --locked python -m pp_anchor.cli benchmark --profile ci --output /absolute/empty/path --seed 1729
```

Use `--profile standard` for the full workload under an exclusive resource lease. Reports
include source commit/dirty flag, scoped source/lock/root-contract hashes, interpreter,
OS/CPU/memory, generator identity, parameters and repetitions. Generated outputs stay outside
tracked source, and reports/docs are excluded from their own source digest. Standard and
ci cleanup passed in the accepted wrappers. The engine replays short histories on every
mutation; very long histories remain a documented scalability limit.

## Historical development baseline

[The first development capture](../artifacts/development-baseline-ci.json) predates the
final queue indexes. Its five ci repetitions took 18.05, 17.98, 39.47, 25.31 and 48.85 s,
with median 3.95 workflows/s on a contended shared host. Its 100,000-timer idle probe took
0.059 s and added 0 KiB peak RSS. These values remain historical evidence with their actual
dirty-source provenance. They are not a controlled before/after optimization comparison.
Queue inspection motivated partial active-run and per-run readiness indexes; the accepted
immutable results above close the final ci and full standard workload gates.

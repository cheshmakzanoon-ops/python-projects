# Workload and interpretation

The generator uses only synthetic accounting/statement data. `--seed 1729` controls amounts and workload construction; UUIDs, commit scheduling, clocks, and timings naturally differ. The server durability mode is default synchronous_commit=on; each journal is a real acknowledged PostgreSQL transaction.

| Profile | Journals | Postings | Accounts | Tenants | Statement rows | Clients |
|---|---:|---:|---:|---:|---:|---:|
| ci | 1000 | 4000 | 200 | 4 | 500 | 8 |
| standard | 250000 | 1000000 | 10000 | 100 | 100000 | 8 |

There is one extra two-posting warmup journal. Half the measured journals target one tenant and half spread across tenants. Four postings per measured journal exercise conservation and independent replay. Accounts are currency-specific. Controlled duplicate statement amounts/references introduce ambiguous components; repeated import reuses stable source identities without adding rows. Every statement is accounted for as matched or unmatched; tied optima remain explicitly ambiguous.

The ci profile runs five measured batches in each contention mode. The standard profile runs one full workload per contention mode (250000 journals total), retaining per-journal latency distributions. Repeating one million durable postings five times would materially increase database/time cost; this is the documented costly-run repetition exception. Do not compare batch repetition counts without this qualification.

Reports contain batch throughput, p50/p95/max posting latency, sampled lock waits, observed whole-transaction retries, independent replay time, normalization rate, candidate graph row/edge sizes, ambiguity and unmatched counts, solver time, peak process RSS, and the exact source/lock/root-input hashes. Lock-wait samples taken at batch boundaries can miss transient contention; they are not cumulative server wait time. PostgreSQL shared-buffer memory is not included in Python RSS. No synthetic result implies production capacity.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --locked python -m pp_meridian.cli benchmark --profile ci --output /tmp/meridian-ci --seed 1729
# Run standard alone under the coordinator's exclusive resource lease.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --locked python -m pp_meridian.cli benchmark --profile standard --output /tmp/meridian-standard --seed 1729
```

First development ci run succeeded at `/workspace/.results/meridian-benchmark-ci-dev/benchmark.json`. It preceded the controlled-ambiguity generator improvement and is not final evidence for that source version. Final committed-snapshot measurements are intentionally produced by the coordinator after writers pause. No standard measurement is invented here.

The first development run showed substantial connection setup and ORM round-trip cost (approximately 22–37 journals/second under concurrent shared-machine load). The workload now models eight persistent clients, closing each client's connection at its batch boundary; the production posting service updates all projection rows in one parameterized UPDATE and derives the returned sequence from its already locked tenant counter. This preserves the same database triggers and atomic transaction semantics. A component adjacency index also avoids rescanning every candidate edge once per disconnected graph component. Measurements after those changes must be treated as a new source version, not substituted into the older report.

The subsequent controlled-ambiguity development run at `/workspace/.results/meridian-benchmark-ci-v2/benchmark.json` passed all checks: 63.2 same-tenant journals/s, 132.4 many-tenant journals/s, 0.319 s independent replay, 0.022 s solver time, five ambiguous components/five unmatched rows among 500 statements. These values refer to that file's exact dirty-source digest and shared-machine context; later source metadata/test changes are not silently relabeled as the measured snapshot.

Demo and benchmark reports derive their status from the recorded mandatory correctness checks. A false check writes status `failed`, named `failed_checks`, and audit/reimport diagnostics, then the public CLI exits 1. Reimport verification compares returned identities and unique identity counts against the first import, and verifies persisted row counts before and after every repeat. A throughput result with failed accounting or import checks cannot be reported as passed. Public ci/standard dimensions remain fixed; targeted regression fixtures reduce only a private in-process test mapping and record those actual dimensions explicitly.

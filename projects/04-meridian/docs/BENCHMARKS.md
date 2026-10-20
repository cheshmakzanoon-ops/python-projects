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
# Run the standard profile alone on a dedicated machine.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --locked python -m pp_meridian.cli benchmark --profile standard --output /tmp/meridian-standard --seed 1729
```

First development ci run succeeded at `/workspace/.results/meridian-benchmark-ci-dev/benchmark.json`. It preceded the controlled-ambiguity generator improvement and is not final evidence for that source version. The later accepted immutable standard measurement is recorded below; development results remain historical snapshots.

The first development run showed substantial connection setup and ORM round-trip cost (approximately 22–37 journals/second under concurrent shared-machine load). The workload now models eight persistent clients, closing each client's connection at its batch boundary; the production posting service updates all projection rows in one parameterized UPDATE and derives the returned sequence from its already locked tenant counter. This preserves the same database triggers and atomic transaction semantics. A component adjacency index also avoids rescanning every candidate edge once per disconnected graph component. Measurements after those changes must be treated as a new source version, not substituted into the older report.

The subsequent controlled-ambiguity development run at `/workspace/.results/meridian-benchmark-ci-v2/benchmark.json` passed all checks: 63.2 same-tenant journals/s, 132.4 many-tenant journals/s, 0.319 s independent replay, 0.022 s solver time, five ambiguous components/five unmatched rows among 500 statements. These values refer to that file's exact dirty-source digest and shared-machine context; later source metadata/test changes are not silently relabeled as the measured snapshot.

Demo and benchmark reports derive their status from the recorded mandatory correctness checks. A false check writes status `failed`, named `failed_checks`, and audit/reimport diagnostics, then the public CLI exits 1. Reimport verification compares returned identities and unique identity counts against the first import, and verifies persisted row counts before and after every repeat. A throughput result with failed accounting or import checks cannot be reported as passed. Public ci/standard dimensions remain fixed; targeted regression fixtures reduce only a private in-process test mapping and record those actual dimensions explicitly.

## Accepted standard measurement

The [raw standard report](../../../docs/evidence/final/standard/meridian-3.14.8-benchmark-benchmark.json) and [verification wrapper](../../../docs/evidence/final/standard/meridian-3.14.8.json) passed at clean immutable source `59443e2bcdfc6a1dd81f8334c108474eef2d3030` on CPython 3.14.8, seed 1729. This was one full measurement with eight persistent clients and one warmup, using the documented costly-run repetition exception. The benchmark command took 3252.0091 seconds, including setup, posting, replay, normalization, matching, and reimport verification.

| Phase | Measured journals | Journals/second | p95 posting latency (seconds) |
|---|---:|---:|---:|
| Same tenant | 125000 | 83.5906 | 0.168624 |
| Many tenants | 125000 | 108.9654 | 0.126260 |

The measured workload committed 250000 journals and 1000000 postings across 100 tenants; the additional warmup contributed one journal and two postings. Independent replay took 23.4057 seconds. Statement normalization measured 40465.2 rows/second, and solver time totaled 2.6923 seconds. All 100000 statement rows were accounted for: 99000 matched, 1000 unmatched, and 1000 ambiguous components. Reimport returned the same 100000 identities and preserved the stored row count at 100000. All four mandatory correctness checks passed, with no failed audits, reimport discrepancies, or observed retry events.

Account cardinality requires care: the generator provisioned 10000 accounts, but the [completed write-population observation](../../../docs/evidence/final/meridian-account-distribution.json) found only 496 accounts with postings. The generator's cycles selected a hot subset. These measurements do not establish write performance with all 10000 accounts active, nor a production capacity estimate.

The two batch-boundary lock-wait samples were zero. A separate [same-tenant observation](../../../docs/evidence/final/meridian-lock-observation.json) captured seven waiting sessions: six waiting on tuple locks and one on a transaction ID. Boundary samples therefore cannot support a claim of no contention. The observation is a single snapshot, not cumulative lock-wait time or an additional acceptance run. Python peak RSS was 442532 KiB; PostgreSQL shared buffers are outside that process measurement. One full timing run supplies no across-run variance estimate.

Exact raw-report provenance:

- Source commit: `59443e2bcdfc6a1dd81f8334c108474eef2d3030`; `source_dirty=false`.
- Source-content SHA-256: `530ea3216de80d90015a655209261085f6f6b2d1ec1fde92e5dce8cfd22dcd51`.
- Lockfile SHA-256: `278057ae9b5d37f8ac2d66073891b25e2d51b15d13f7f753129aea59e01bb54d`.
- Root-contract SHA-256: `3d49d75f3224a6934d9b2bad749de92ac6e9fae92a2e5a4f29cd7d6ee69c3bcd`.

The wrapper records its own broader source/root input lists and corresponding hashes; those distinct digest scopes are explicit in each JSON file. This documentation update does not relabel the tested source revision or change its evidence.

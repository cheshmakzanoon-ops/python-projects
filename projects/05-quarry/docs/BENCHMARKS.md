# Benchmark protocol and results

Run `uv run --locked python -m pp_quarry.cli benchmark --profile ci --output /tmp/quarry-ci --seed 1729` with OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1 and MKL_NUM_THREADS=1. The runner sets DuckDB threads=1 and memory_limit=128MB. Arrow batch size=1,024, maximum source record=65,536 bytes. It generates input files as streams, stores historical versions on disk and compares facts and daily totals against independent SQLite window-rank complete rebuilds. The daily reference groups winning arrivals directly, without production buckets. No complete dataset is materialized as a Python list. Current query timing includes facts and daily digests; historical timing below covers facts only and is not directly comparable.

CI uses 20,000 originals, 2,000 corrections, 400 deletes and 100 schema additions over eight buckets. One fresh-catalog warmup precedes five fresh-catalog measured runs. OS file cache is warm; SQLite journal_mode=WAL and synchronous=FULL, Parquet files/directories are fsynced. Standard uses five million originals, 500,000 late corrections, 100,000 deletes and 100 schema additions over 128 buckets. Standard uses a bounded 20,000-original/eight-bucket warmup and one measured 5,000,000-original/128-bucket run, explicitly reported because repeating full historical catalogs is costly. The report separates warmup_parameters from measured parameters and preserves all measured correction/delete/schema phases.

JSON records originals rows/second, original and incremental times, incremental/full-build ratios, independent oracle time, source bytes read (three full hash passes plus the parse pass), logical Parquet input bytes for transformations, output bytes written, rewritten buckets, reused nodes, query time, recovery time and process peak RSS. RSS is a process high-water mark including runtime/Arrow/DuckDB overhead; memory_mb is the engine budget, not an OS process cap. An update set spanning every bucket can legitimately rewrite every bucket; the demo's targeted one-key correction demonstrates locality separately.

Source provenance includes exact project source and lock hashes plus relevant root-contract hashes, source commit and project dirty flag. Source scope comprises src/tests/examples/benchmarks code/data files, pyproject.toml, uv.lock and .python-version; generated outputs and evidence are excluded. New reports hash CONTRIBUTING.md, ruff.toml, portfolio.toml, the dispatcher and docs/REQUIREMENTS.md. Historical reports retain their own explicitly declared input lists. The benchmark confirms unchanged source hash after execution.

The accepted standard result below comes from an immutable committed tree. Historical dirty-checkout development captures remain labeled separately and are not substitutes for that evidence.

## Accepted standard result

The full standard workload passed on CPython 3.14.8 from clean source commit `59443e2bcdfc6a1dd81f8334c108474eef2d3030`. See the [raw measured report](../../../docs/evidence/final/standard/quarry-3.14.8-benchmark-benchmark.json) and [verification wrapper](../../../docs/evidence/final/standard/quarry-3.14.8.json). The wrapper records successful demo/standard commands and unchanged source after execution. This was one costly measured run, preceded by a separate 20,000-original/eight-bucket warmup; it does not provide a repeated-run latency distribution.

The measured run ingested 5,000,000 originals over 128 buckets, followed by separate batches of 500,000 corrections, 100,000 deletes and 100 nullable schema-addition upserts. Its final analytical state contained 4,900,100 live rows and its exact historical registry contained 5,600,100 accepted identities. The schema batch uses newer versions and restores 100 previously deleted keys. Both the independent complete-rebuild comparison and the forced full current-state Parquet rebuild matched digest `eb4449629d8ea89c9ecff3457aa3f49a6c0ace83ceb0c302fdc3df61c1375bb3`.

| Measured operation or quantity | Result |
| --- | ---: |
| Original ingestion and publication | 453.668268 s |
| Original-event throughput | 11,021.27 rows/s |
| Three subsequent ingestion/publication phases, combined | 470.169370 s |
| One forced full current-state Parquet graph rebuild | 121.066512 s |
| Subsequent phases / forced rebuild time | 3.883563 |
| Sorted facts query and streaming result digest | 36.047760 s |
| Orphan reconciliation, with zero orphans | 0.055222 s |
| Independent complete-rebuild oracle | 91.197882 s |
| Peak process RSS | 312,631,296 bytes |
| Parquet bytes written, original plus three update publications | 719,045,175 bytes |
| Logical Parquet transform input bytes, including forced rebuild | 897,480,399 bytes |
| Logical source bytes read across ingestion hash/parse passes | 3,303,426,868 bytes |

This result demonstrates correct processing at the required size, not an incremental speedup. The three subsequent phases include event ingestion, identity-registry updates and three publications; the comparator is one graph rebuild from already materialized current state. Broad correction/delete batches reach every bucket, and the global schema change invalidates all 128 buckets. The final update publication therefore rebuilt 128 buckets and reused zero nodes. The separate targeted correction demo proves locality; it must not be used to imply that this broad standard workload avoided full bucket rewrites.

The raw report records source digest `c2d532eb22b507168c771d915203437b50cc985e7f4fdf0db9397078a1e15af3`, lock digest `71898d3b0636bd6d3ed606a933766b7c6849d8da3766504686d8599fd5fbe00f`, exact identities for all four source files and five checksummed publication summaries. The verification wrapper uses its explicitly listed, broader source/root input sets and therefore records different scope hashes; consult each report's declared inputs rather than treating their hash values as interchangeable. DuckDB used one thread and a 128 MB engine memory limit, with 1,024-row Arrow batches and a 65,536-byte source-record bound. RSS includes Python, Arrow, DuckDB and evaluation overhead; it is not capped by the engine limit. The source read cache was primed by the oracle, engines had a bounded warmup, and measurement used a fresh catalog. Hardware CPU metadata is reported as unknown; these synthetic local results do not establish production capacity.

The accepted compatibility wrappers also passed all 37 tests on [CPython 3.13.16](../../../docs/evidence/final/python313/quarry-3.13.16.json) and [CPython 3.14.8](../../../docs/evidence/final/python314/quarry-3.14.8.json), with clean immutable source at their recorded commit `7114e39c7e9e8af177e84fe8cd990fe5a09bde63`.

## Development baseline (not final committed evidence)

A 3.13.16 run at dirty source digest `d6bfb001b269e27d7751e5203b107e47f16f45bed0e3c0c896d1ab6990f52695` completed one warmup and five measurements. Median original ingestion throughput was 6,671.61 rows/s; the individual measured runs ranged 4,850.31–15,226.15 rows/s under a shared development host. Peak process RSS was 151,871,488 bytes. Original builds took 1.31–4.12 s; subsequent three batches took 1.63–2.97 s; a forced full current-state Parquet rebuild took 0.50–1.04 s. Incremental/full ratios of 1.95–5.15 reflect three separate publications spanning all buckets and the schema-global rebuild; this workload is not evidence of a speedup. Targeted demo correction separately proves one bucket rebuilt and 21 nodes reused. Every run matched the independent rebuild digest. Source records totaled 9,799,974 logical read bytes per run across hash/parse passes.

That earlier exact development report is in `artifacts/ci-313-development.json`. Subsequent fixes and default-interpreter selection changed source identity. This historical CI capture does not establish standard completion; the accepted committed-source standard result above supplies that evidence.

## Python 3.14.8 development baseline

The finalized development source `c2d532eb22b507168c771d915203437b50cc985e7f4fdf0db9397078a1e15af3` completed all five CI measurements and the 20,000-row warmup on Python 3.14.8. Median original throughput was 18,088.47 rows/s; peak process RSS was 131,145,728 bytes. Original builds took 1.085–1.362s, the three incremental publications 1.192–1.424s, and full current-state graph rebuilds 0.366–0.449s. Incremental/full ratios were 2.923–3.881; all five results matched the independent full-rebuild digest. The report now records exact source identities for all four files, historical registry cardinality and checksummed manifest summaries, along with separate warmup_parameters. See `artifacts/ci-development.json`. This remains dirty-checkout development evidence. The committed-source runs above now provide committed-source compatibility and standard verification.

## Integrity checks in the current implementation

Pinned queries now verify the SHA-256, size, schema and row count of each selected Parquet file before execution. Publication verifies the same properties before reusing a file. These checks add read I/O, including for bounded queries; the historical timings above predate them. No standard workload was rerun for this maintenance change, so those timings must not be treated as current-performance measurements.

## Focused incremental correctness exercise, 2026-10-20

From the project directory, choose a fresh output directory:

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
uv run --locked --python 3.14.8 python benchmarks/verify_incremental.py \
  --output /tmp/quarry-correctness-50000 --rows 50000 --buckets 8 --seed 1729
```

The [executable workload](../benchmarks/verify_incremental.py) retains generated inputs, a lake and report under the owned output path. It performs seven publications: 50,000 originals; 10,000 corrections/day moves; 5,000 obsolete versions plus 20 exact replays; 4,546 tombstones; 100 nullable-schema upserts; one targeted day move; and a quality-only repeated source. Two namespaces deliberately share key strings. Each publication independently rebuilds facts/daily from all arrivals in SQLite and checks exact historical/source cardinality and old pinned results. Retention with/without the old pin, restart, frozen history and equal-version conflict rejection complete the exercise.

The [raw report](../artifacts/deep-correctness-2026-10-20.json) records one successful run: 69,647 historical identities, 45,464 live facts, 22.327328 seconds and 145,219,584 bytes peak process RSS. Obsolete/replayed and quality-only phases reuse all 24 nodes and write zero bytes. The targeted move rebuilds one bucket and reuses 21 nodes. A separate schema-only test isolates normalized reuse; this workload's schema phase also changes events.

Actual project source/test/lock hash: `460e8c57895390f5fa61366bf361582abe5129dd1691ea09424eba51d5d336e9`; root-contract hash: `cdd3d19d53efcd337bc0a3b104ed1ee20e631dc6c53e993791e3b25e53627909`; lock hash: `71898d3b0636bd6d3ed606a933766b7c6849d8da3766504686d8599fd5fbe00f`. The report truthfully identifies a dirty checkout based on `39d3a8d4be3e8e2e7de85379790d68f5367d6825`, CPython 3.14.8 and a shared Linux host. Source content was unchanged across execution. Documentation/artifacts are outside the declared source digest scope; root files may subsequently change and do not retroactively alter this record.

This was a deterministic correctness diagnostic with one run, no warmup or repeated timing distribution, unknown CPU metadata and no inferred cgroup maximum. DuckDB used one thread and 128 MB; RSS includes runtime/reference overhead and is not that engine limit. It does not replace or update the five-million-event standard run and establishes no production capacity claim.

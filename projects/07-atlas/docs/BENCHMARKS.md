# Benchmarks and relevance

Workloads are implemented in `src/pp_atlas/benchmarks.py` and invoked through the
installed CLI. Default seed1729; pin OMP_NUM_THREADS, OPENBLAS_NUM_THREADS and
MKL_NUM_THREADS to1. Reports include code/lock/root-contract hashes, dirty status,
source input lists, Python/OS/CPU/memory limit, workload ID and distributions.
Checks capture hashes before and after execution. Source scope is src, tests,
benchmarks, examples, pyproject, lock and interpreter pin; generated outputs,
artifacts, documentation and caches are excluded. Root contract includes AGENTS,
master brief, Ruff configuration, manifest and dispatcher.

| Profile | Documents | Tokens/document | Queries | Timing |
|---|---:|---:|---:|---|
| ci |200|80|30|one warmup, five measured repetitions|
| standard |100000|400|2000|one warmup, five measured repetitions|

The scale generator draws50% of tokens from20 common terms,40% from100 topic
vocabularies of16 terms each, and10% from N rare identities. Queries alternate
between topic-selective, common and rare terms. Ten disjoint ACL groups divide
documents; the measured principal sees group0. Scale data demonstrates correctness
and cost, not semantic relevance. Batch size1000 bounds ingestion working state;
normal query readers materialize the current generation. SQLite WAL uses
synchronous FULL; segment contents and directory are fsynced before publication.

Cold query includes a new reader, integrity validation and index construction.
Warm timings include the128 entry result LRU; its state and query mix are recorded.
Authorization snapshot timing includes catalog snapshot, visibility construction
and sorted visible IDs. Authorization-plus-query is reported separately. Peak RSS
is process-lifetime maximum, so launch the benchmark in its own process. Retained
obsolete files count toward reported disk bytes. No throughput target is invented.

## Measured development CI run

`artifacts/development-ci.json` is a real dirty-source development measurement on
CPython3.14.8; it is not final committed release evidence. Exact source hashes and
machine details are in that report. Results:200 docs indexed in0.2303 s (868.4 docs/s),
111912 disk bytes,37.09 MB peak RSS; cold query17.41 ms; warm p50/p95/p99
0.598/6.704/7.987 ms. Median authorization snapshot0.528 ms. Authorization,
visible count and source-stability checks passed. This tiny workload cannot
predict100k document cost and ran while other development workers existed.

The standard run is deliberately reserved for the coordinator's serialized lease
on an immutable committed snapshot. No standard performance result is claimed
until that run exists. Command:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run --locked python -m pp_atlas.cli benchmark --profile standard \
  --output /tmp/atlas-standard --seed 1729
```

## Independently labeled quality collection

The250 original technical documents and60 graded queries are separate from scale
data. Query intents/labels were written before scoring; the frozen seeded split
contains30 development and30 heldout queries. Grade3 means primary current procedure,
2 useful design rationale,1 incident context. Omitted documents are unjudged and
treated as0. Restricted operations notes are not visible. Recall uses the authored
relevant pool, not an exhaustive judgment of every possible text relationship.
The coordinator performs an independent semantic audit without scorer access.

The documented weakness was short archival distractors containing the same words
in a different order. A bag-of-words baseline strips query quotes; the improvement
honors explicit phrase positions. Selection used development judgments only;
BM25 defaults1.2/.75 were not tuned on heldout. This is an improvement to lexical
query semantics, not a claim of solved semantic search.

| Mode/split | nDCG@10 | MRR | pooled Recall@10 |
|---|---:|---:|---:|
| baseline/development |0.72263|0.59444|1.00000|
| phrases/development |0.96462|0.98333|1.00000|
| baseline/heldout |0.69740|0.56111|1.00000|
| phrases/heldout |0.95150|0.98333|1.00000|

All60 per-query lists, intents, judgments, unjudged hits and ranking failures are
in `artifacts/development-quality.json`. Fifty queries still have imperfect graded
ordering after the change: design and incident lengths can rank contextual material
above a higher judged grade. No heldout-based fix was applied. The collection has
repeated document structures and narrow technical vocabulary; it does not estimate
relevance for arbitrary users or language domains.

```sh
uv run --locked python -m pp_atlas.cli evaluate --root /tmp/atlas-quality \
  --corpus examples/quality_corpus.json --judgments examples/quality_judgments.json \
  --output /tmp/atlas-quality-report.json
```

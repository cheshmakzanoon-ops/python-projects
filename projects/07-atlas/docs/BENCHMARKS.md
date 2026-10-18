# Benchmarks and relevance

Workloads are implemented in `src/pp_atlas/benchmarks.py` and invoked through the
installed CLI. Seed 1729 fixes generated inputs. Pin OMP_NUM_THREADS,
OPENBLAS_NUM_THREADS and MKL_NUM_THREADS to 1. Reports record source, lock and
root-contract hashes, dirty status, exact input lists, interpreter, operating
system, CPU, memory limit and workload distributions. Hashes are captured before
and after execution; generated reports and project documentation are excluded
from the measured code scope.

| Profile | Documents | Tokens per document | Queries | Timing |
|---|---:|---:|---:|---|
| ci | 200 | 80 | 30 | One warmup, five measured repetitions |
| standard | 100,000 | 400 | 2,000 | One warmup, five measured repetitions |

The scale generator draws 50% of tokens from 20 common terms, 40% from 100 topic
vocabularies of 16 terms each, and 10% from N rare identities. Queries alternate
between topic-selective, common and rare terms. Ten disjoint ACL groups divide
documents; the measured reader sees group 0. Scale data establishes retrieval
correctness and cost, not relevance quality. Batch size 1,000 bounds ingestion
working state; the query reader materializes the current generation. SQLite WAL
uses synchronous FULL; segments and their directory are fsynced before publication.

## Final committed standard measurement

The coordinator ran the standard profile serially from a clean immutable clone of
commit `59443e2bcdfc6a1dd81f8334c108474eef2d3030`, using CPython 3.14.8 on Linux
with an Intel Xeon Platinum 8573C, a 32 GiB memory limit, one process and thread
limits of 1. The run indexed **100,000 documents / 40,000,000 tokens** and measured
**2,000 queries over five repetitions**.

| Metric | Actual result |
|---|---:|
| Indexing time | 543.2294 s |
| Indexing throughput | 184.084 documents/s |
| Cold query, including index loading | 36.1966 s |
| Warm query p50 / p95 / p99 | 21.6806 / 57.1996 / 83.9298 ms |
| Warm query throughput | 32.8779 queries/s |
| Disk size | 155,283,633 bytes |
| Peak process RSS | 2,778,984,448 bytes |
| Authorization plus search median | 398.615 ms |
| Authorized snapshot median | 59.3983 ms |

Authorization, expected cold-query visible count and unchanged-source checks all
passed. The [benchmark record](../../../docs/evidence/final/standard/atlas-3.14.8-benchmark-benchmark.json)
contains exact inputs, environment, measurements and source provenance. The
[verification record](../../../docs/evidence/final/standard/atlas-3.14.8.json)
records successful commands and source stability. The benchmark's project digest
is `57a00efa3b263d8e9d5baf31e921b259fadb12f62d036627291c453a34aa64fb`;
its lock digest is
`afadf806fdbb623044aa563e65234d12d3a49b57e907308cab46198ecad717f8`.
The surrounding verification record declares its own broader input list and digest.

Cold timing includes a new reader, integrity checks and index construction. Warm
timing includes the 128-entry result LRU and its recorded query mix. Authorization
snapshot timing includes the catalog snapshot, visibility construction and sorted
visible IDs. The separate authorization-plus-search sample alternates restricted
and all-group readers; it cannot be subtracted from warm-query timing to estimate
an isolated authorization cost. Peak RSS is the process-lifetime maximum. Disk
size includes all files retained by the benchmark's index root.

The scaling limit is explicit: visibility construction scans O(N) current
catalog documents, including before a result-cache lookup. The materialized Python
postings also consume approximately 2.78 GB of peak RSS at this workload. These
measurements motivate an indexed ACL visibility representation and compact
positional storage. Neither optimization is claimed to be implemented. This
single-machine synthetic run does not establish production capacity or a latency
service guarantee.

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run --locked python -m pp_atlas.cli benchmark --profile standard \
  --output /tmp/atlas-standard --seed 1729
```

## Historical development CI measurement

`artifacts/development-ci.json` preserves a real dirty-source CPython 3.14.8 run:
200 documents indexed in 0.2303 s, 111,912 disk bytes, 37.09 MB peak RSS, 17.41 ms
cold query and 0.598 / 6.704 / 7.987 ms warm p50 / p95 / p99. Authorization,
visible-count and source-stability checks passed. This small concurrent-development
capture is historical evidence; its exact tested hashes remain in the artifact.
It is not the final committed standard measurement above.

## Independently reviewed quality collection

The 250 original technical documents and 60 graded queries are separate from
scale data. Query intents and labels were written before scoring; a fixed seeded
split contains 30 development and 30 heldout queries. Grade 3 means the primary
current procedure, 2 useful rationale and 1 incident context. Omitted documents
are unjudged and treated as 0. Restricted operations notes are invisible to the
public evaluation principal. Recall is over the authored relevant pool.

The coordinator completed a separate semantic review without consulting
per-query scorer output or changing judgments. The [judgment review](../../../docs/evidence/atlas-judgment-review.md)
records corpus and judgment hashes, rubric agreement, semantic spot checks and
limitations. This review does not establish agreement among human assessors or
relevance for natural queries outside the authored collection.

The documented weakness was short archival distractors containing the query's
words in a different order. The baseline strips query quotes; the improvement
honors exact phrase positions. Selection used development judgments only; BM25
parameters 1.2 / 0.75 were not tuned on heldout queries.

| Mode / split | nDCG@10 | MRR | Pooled Recall@10 |
|---|---:|---:|---:|
| Baseline / development | 0.72263 | 0.59444 | 1.00000 |
| Phrases / development | 0.96462 | 0.98333 | 1.00000 |
| Baseline / heldout | 0.69740 | 0.56111 | 1.00000 |
| Phrases / heldout | 0.95150 | 0.98333 | 1.00000 |

`artifacts/development-quality.json` preserves all 60 per-query rankings, intents,
judgments, unjudged hits and failures. Fifty queries retain imperfect graded
ordering: document length can favor contextual material over a higher judged
grade. No heldout-based correction was applied. The collection uses repeated
technical templates and narrow vocabulary; the phrase experiment demonstrates
this authored lexical weakness, not broad ranking superiority.

```sh
uv run --locked python -m pp_atlas.cli evaluate --root /tmp/atlas-quality \
  --corpus examples/quality_corpus.json --judgments examples/quality_judgments.json \
  --output /tmp/atlas-quality-report.json
```

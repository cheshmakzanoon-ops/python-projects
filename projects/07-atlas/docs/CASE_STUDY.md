# Atlas case study

The challenge was making search ranking respect permissions. Filtering only the
final top-k is insufficient: private documents can change global term frequency
and average length, revealing information through public score changes. Atlas
intersects current revisions, ACLs and explicit filters before statistics,
matching, ranking, snippets, counts and facets. Its mutable catalog and immutable
segment reader share one SQLite snapshot per request.

SQLite provides transaction isolation and crash rollback. The original engineering
core is the tokenizer, positional postings, query planner, visible-statistics
BM25, top-k heap, external merge and publication protocol. A global FTS query
followed by filtering was rejected because its statistics would violate the
visibility contract. Keeping old files makes pinned-reader safety straightforward;
online garbage collection needs a separate lifetime protocol and is outside this
reference implementation.

## A Unicode defect with an independent regression

The initial tokenizer normalized a base character with nonzero combining-class
marks. This handled accents and ligatures, but Hangul Jamo are class-zero starters.
`가`, `ㄱㅏ` and `가` therefore produced different terms despite NFKC equivalence.
The failure could hide a relevant document. Normalizing the complete string without
retaining offsets would introduce a different defect in snippet highlighting.

That correction recognized Hangul L/V/T composition. The later v2 tokenizer
generalizes the boundary rule: compatibility characters can themselves normalize
into marks, as with Japanese `ｶﾞ` and `ガ`. It joins normalization-safe source spans
and compares term sequences with an independent whole-string NFKC/casefold oracle.
The persisted identity also includes the Unicode database, since the supported
interpreters classify newly assigned characters differently. An offline rebuild
retokenizes current text and preserves permissions; old postings are never relabeled.

Adversarial review also found that nested mutable result dictionaries could poison
an LRU entry when a library caller modified a prior result. Cache insertion and
retrieval now copy values. A regression mutates facets, statistics and term
contributions and proves subsequent searches retain authentic results.

## Verification and measured limits

The original acceptance snapshot passed 40 tests on each of Python 3.13.16 and
3.14.8. Later regression suites are recorded in [VERIFICATION.md](VERIFICATION.md). Whole-package
branch-inclusive coverage is 97%. Failure scenarios include concurrent writers,
stale merges, process death before publication, SQLite rollback, hidden-document
updates, next-request revocation and cached-file corruption. The
code-search integration passes through real PyTrace findings and public Atlas
interfaces, including deletion, merge, tenant isolation and permission changes.

The recorded run executed the full standard workload serially from clean immutable
commit `59443e2bcdfc6a1dd81f8334c108474eef2d3030`. It indexed 100,000 documents
of 400 tokens each in **543.2294 s**, or **184.084 documents/s**, then measured
2,000 queries over five repetitions. Warm p50/p95/p99 were
**21.6806 / 57.1996 / 83.9298 ms**, at **32.8779 queries/s**. Cold loading and
query took **36.1966 s**. Disk size was **155,283,633 bytes** and peak process
RSS **2,778,984,448 bytes**. All three correctness/source-stability flags passed.
The [benchmark](../../../docs/evidence/final/standard/atlas-3.14.8-benchmark-benchmark.json)
and [verification record](../../../docs/evidence/final/standard/atlas-3.14.8.json)
preserve exact provenance and environment details.

In that historical implementation, O(N) visibility construction ran before cache
lookup, and materialized Python postings used approximately 2.78 GB at this workload.
Authorized-snapshot median cost was 59.3983 ms; the
separate mixed-principal authorization-plus-search sample had a 398.615 ms median.
Those samples use different scopes and cannot be subtracted from ordinary query
timing. Indexed ACL visibility and compact positional arrays are justified next
steps. The current reader avoids the visibility scan on a valid result-cache hit,
after pinning the current ACL revision and checking compatibility/file signatures.
It also retains explanations only for the returned page and uses rare phrase
anchors. The bounded [allocation diagnostic](../benchmarks/README.md) establishes
those narrower changes; the historical standard workload has not been rerun.

The separate judged collection improves heldout nDCG@10 from 0.69740 to 0.95150
by honoring explicit phrase positions, without heldout parameter tuning. An independent reviewer completed an independent [semantic judgment audit](../../../docs/evidence/atlas-judgment-review.md)
without consulting per-query scorer output. Fifty queries still have imperfect
graded ordering, and all failures remain in the historical quality report.
Repeated technical templates and pooled labels limit the relevance claim to this
authored collection. New independently labeled development data is needed before
testing stemming or field weighting.

Historical dirty-source CI and quality captures remain in `artifacts/`, with the
source hashes they actually tested. The final standard result above replaces the
earlier pending-workload status; it does not turn the small development capture
into release evidence. A single-machine synthetic benchmark does not establish
production capacity, arbitrary language relevance or a latency service guarantee.
Dense reranking, OCR and external crawling were optional or excluded.

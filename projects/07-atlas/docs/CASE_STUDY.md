# Atlas case study

The challenge was making search ranking itself respect permissions. Filtering
only the final top-k is insufficient: private documents would change global term
frequency and average length, revealing information through public score changes.
Atlas intersects current revisions, ACLs and explicit filters before statistics,
matching, ranking, snippets, counts and facets. Its mutable catalog and immutable
segment reader share one SQLite snapshot per request.

SQLite provides transaction isolation and crash rollback; the original engineering
core is the tokenizer, positional posting construction, query planner, visible
BM25 calculation, top-k heap, external merge and coherent publication protocol.
A global FTS query followed by result filtering was rejected because its statistics
would violate this contract. Another tradeoff is deliberately keeping old files:
reader safety is straightforward, while online garbage collection needs a separate
lifetime protocol and remains outside this reference implementation.

A concrete defect emerged while checking Unicode boundaries. The initial tokenizer
normalized a base character together with nonzero combining-class marks. This
handled accents and ligatures, but Hangul Jamo are class-zero starters. The strings
`가`, `ㄱㅏ` and `가` therefore produced different terms despite NFKC equivalence.
The failure could hide a relevant document and move highlighting into the wrong
source range if fixed by normalizing the string without offset mapping.

The correction recognizes Hangul L/V/T composition while forming normalization
clusters, including compatibility Jamo. Each normalized expansion retains the
original cluster's character span. Regression tests compare all three spellings
and assert `<mark>가</mark>` highlights the original decomposed text. A generated
Unicode normalization-equivalence property supplements these explicit cases.
This tests an independent Unicode invariant rather than reproducing the tokenizer.

A second adversarial review found nested mutable result dictionaries could poison
an LRU entry when a trusted library caller modified a prior result. Cache insertion
and retrieval now copy result values. A regression mutates facets, statistics and
term contributions and proves subsequent searches retain the authentic values.

Local Python3.13.16/3.14.8 runs pass40 tests. A preceding38 test whole-package run
measured97% branch-inclusive coverage; named failures include concurrent writers,
stale merges, process death before publication, SQLite rollback, hidden-document
updates, next-request revocation and cached-file corruption. Coverage is supporting
evidence; final committed verification and independent judgment review belong to
the coordinator's handoff.

A real200 document development run indexed in0.2303 s with17.41 ms cold and0.598 ms
median warm query latency. Those numbers establish a small local baseline only.
The separate judged collection improved heldout nDCG@10 from0.69740 to0.95150 by
honoring explicit phrase positions, with no heldout parameter tuning. Remaining
graded-order failures are included per query. Standard100k document timing is
reserved for serialized immutable-snapshot execution.

The next justified performance work is measuring current-generation Python-object
memory at100k documents and replacing positional tuples with compact arrays if
needed. Relevance next steps require new independently labeled development data
before testing stemming or field weighting. Dense reranking, OCR and external
crawling were not implemented because they are optional or excluded.

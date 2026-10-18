# Design decisions

1. **Visible statistics instead of global statistics.** Hidden documents cannot
change a user's BM25 score. This costs per-principal set intersections and means
scores from different principals are not directly comparable. Filtering after
ranking was rejected: it can leak counts, suppress authorized top-k results,
and change scores through private document frequency.
2. **SQLite metadata and original lexical segments.** SQLite implements catalog
transactions, not full-text search. Every posting, phrase match, BM25 contribution,
and top-k decision is original Python. An FTS wrapper was rejected because it
would hide the required retrieval and visibility contract.
3. **Immutable files plus atomic metadata.** Files precede publication; stale
merges fail instead of overriding newer revisions. Online garbage collection is
outside this first reference implementation. Disk consumption includes retained
obsolete segments until an exclusive offline migration rebuilds the index.
4. **Conjunction grammar.** Supported syntax is unquoted terms, quoted exact
phrases, and `type:`, `tag:`, `source:`, `id:` equality filters. No boolean nesting,
regexes, wildcards, escaping, ranking expressions, or arbitrary field evaluation.
Limits are 4096 UTF-8 bytes, 32 lexical occurrences, 16 tokens per phrase, eight
filters, 100 returned hits, offset <=10000; documents <=2 MB UTF-8. Rejecting an
unsupported expression is preferable to silently interpreting a different query.
5. **Body-only indexing.** Titles identify hits; body tokens determine positions
and length. Metadata is exact-filtered. Field boosts, stemming, synonym expansion
and title weighting need separate relevance work; they are not implicit features.
6. **Local bearer binding.** FastAPI HTTPBearer resolves an opaque credential to
a server-configured tenant/subject/admin record. Group membership comes only from
the catalog. No homegrown signatures, client-selected principals or URL secrets.
External identity providers and online token lifecycle management are deployment
extensions. The library and CLI are trusted administrative interfaces.
7. **Reference reader versus compressed query execution.** Gzip reduces disk cost;
current-generation postings are loaded into Python memory. Standard workload
measurement includes cold loading and peak RSS. Memory mapping and compressed
in-memory integer arrays are justified next steps if the measured budget demands
them. An external merge bounds the merge's per-stream record working set but the
normal reader is intentionally materialized.

Linux ingestion/durability tests are required. Other platforms may reject directory
fsync and are not claimed to provide the Linux durability contract. Query timing
side channels, disk tampering by privileged users, distributed replication, PDF,
OCR, crawling and dense/LLM retrieval are outside scope.

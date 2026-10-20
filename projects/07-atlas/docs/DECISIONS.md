# Design decisions

## Permission-filtered reference collection

Ranking, totals and facets operate on the same authorized, explicitly filtered
current revisions. BM25 uses that collection's N, average body length and document
frequencies. Ranking globally and removing forbidden hits afterward can suppress
valid top-k results and reveal private corpus changes through public scores.
Global-statistics scoring was therefore rejected. The cost is per-query visibility
work on cache misses, and scores that cannot be compared across principals/filters.
Tenant publication counters and timing remain observable; the invariant concerns
content and derived search statistics. [Architecture](ARCHITECTURE.md) gives the
formula and exact snapshot sequence.

## Immutable files and a transactional pointer

SQLite implements metadata publication, not retrieval. Files are durable before
the manifest references them; the manifest and active revision rows commit together.
Preparing segments outside the writer transaction avoids holding the SQLite lock
during compression. Reading the manifest only after `BEGIN IMMEDIATE` prevents
concurrent prepared batches from replacing one another.

Keeping obsolete segments is deliberate: an old reader can finish after a merge
without a cross-process lease registry. Orphans consume disk but never become
visible merely because they exist. Reclamation uses an offline rebuild into a new
root. Online deletion, replication and multi-host filesystems need separate lifetime
and consistency protocols and are outside the implemented contract.

A successful commit with a lost response is an ambiguous submission, not a lost
write. Random revision IDs prevent an old segment's identity from becoming current
again. They are not client idempotency keys. Retrying the same document ID replaces
one current record; it can advance revisions twice. Applications needing exactly-once
submission must own request identity above this API.

## Compatibility checks belong inside transactions

A long-lived Engine can outlive a catalog upgrade by another process. Validating
only at construction lets it read cached results and publish into an unsupported
format. A check before acquiring the transaction is also insufficient: a different
writer can change the header between check and write.

All catalog transactions now validate format/tokenizer after BEGIN and before
operation-specific SQL. Read transactions pin header, revisions, documents and
groups together; write transactions hold the SQLite lock during the check and
mutation. The raw connection helper remains internal to initialization and
maintenance tests. Unsupported catalogs raise `IncompatibleCatalog`; HTTP presents
503 without corpus detail. A stale merge is a separate, expected concurrency
outcome (`StaleGeneration`, HTTP 409), for which retry uses a fresh snapshot.

Construction must recognize a catalog before preparing its schema or changing
its journal mode. Otherwise even a correctly rejected future version can acquire
legacy tables or be checkpointed by the writable connection on close. Existing
catalog recognition now uses a read-only transaction. Only empty databases and
recognized format-1 catalogs can enter initialization; partial schemas require
recovery, not `CREATE IF NOT EXISTS` repair. New-table creation is atomic. An
exclusive SQLite initialization lock spans the separate journal-mode transition,
while normal valid WAL opens remain read-only and preserve reader/writer concurrency.
Catalog/WAL content preservation excludes SQLite's read-coordination sidecars.

## Normalization is persisted semantics

A tokenization fix changes the meaning of stored postings. V1 grouped source
Unicode marks and special-cased Hangul, but halfwidth Japanese voiced marks have
an original non-mark category and become marks under NFKC. For example, it indexed
`ｶﾞ` as decomposed `ガ` while querying `ガ` used the composed token. V2 groups
normalization-safe boundaries and retains the original spans for snippets.

The Unicode database is part of that algorithm. CPython 3.13.16 (UCD15.1.0) treats
Cyrillic Tje U+1C89 as unassigned; 3.14.8 (UCD16.0.0) recognizes/casefolds it.
One version string across both runtimes would falsely promise compatible indexes.
V2 therefore includes the UCD version in catalog and segment headers. A corrected
reader refuses v1 or another UCD's postings before mutation; it does not guess.

The offline maintenance module reads known format-1 source versions, verifies their
segments and rebuilds **from current source text**, preserving permissions and
metadata. It never relabels an old posting list. Revisions/generation counters are
fresh in the destination. No source documents are lost when the older runtime
cannot tokenize a newly assigned character, but that character is not searchable
under its older Unicode rules. Upgrade and downgrade procedures are explicit in
the [runbook](OPERATIONS.md#tokenizer-upgrade-or-interpreter-switch).

## Bounded ranking state rather than all-candidate explanations

A top-k heap does not bound memory if an explanation dictionary has already been
built for every matching document. The current scorer streams scalar scores,
retains the requested prefix and materializes explanations for the returned page.
This trades a second score calculation for at most 100 returned hits for removing
O(candidates * query terms) retained explanation entries. Stable ID ties and the
term summation order remain unchanged.

The result cache is checked only after current format, ACL revision, generation
and file signatures are established. Its key already contains both revisions,
principal, query, ranking parameters and page. Rebuilding the same visible set
before a valid hit added O(documents) work without strengthening authorization.
Removing that scan preserves next-request revocation. Returned nested dictionaries
are still copied so callers cannot poison the cache.

Phrase matching uses the rarest phrase-position list as an anchor and binary
searches the rest. This avoids allocating large shifted position sets for phrases
with one selective term. O(m) additional storage and selective probes were chosen
over linear set intersection; equally common nonmatching terms can take more CPU.
The exhaustive sliding-window oracle checks the result independently of that tradeoff.

These changes do not compress the materialized index or bound the per-Engine tenant
working set. Current memory/latency claims come from the scoped
[diagnostic](../benchmarks/README.md); historical standard-workload results retain
their original source identity. No current production capacity claim follows.

## Explicitly limited query and identity surfaces

The grammar supports conjunctions, quoted adjacent phrases and equality filters
`type:`, `tag:`, `source:` and `id:`. Limits are 4096 query bytes, 32 lexical
occurrences, 16 phrase tokens, eight filters, 100 hits and offset <=10000. Titles
identify results; bodies determine token positions and length. No stemming,
field weighting, boolean nesting, arbitrary expressions or implicit semantic search
is hidden behind the syntax. Relevance changes require independently labeled data.

The HTTP adapter binds opaque bearer credentials to server-configured tenant,
subject and an actual boolean administrator role. Groups come from the catalog;
clients cannot submit their own. TLS, identity-provider integration and token
lifecycle management are deployment work. The library/CLI are trusted interfaces.
Filesystem owners are trusted as well: size/mtime invalidation and SHA-256 detect
ordinary damage, not an attacker who can modify the catalog and its files.

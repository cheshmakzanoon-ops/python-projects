# Architecture and invariants

Atlas has two persistent layers: SQLite owns current document identities and
permissions; immutable gzip segments own text and positional postings. A request
combines one catalog snapshot with exactly the revisions named by that snapshot.
Segment order never selects a winner. `Engine` is the trusted administrative/library
boundary; HTTP first binds a bearer to a server-selected tenant and subject.

## Catalog state and publication

Each tenant has a SHA-256-named directory, a SQLite catalog and a segment directory.
The original tenant string never becomes a path component. The singleton state row
contains format, tokenizer identity, data generation, ACL revision and the manifest
of `(filename, SHA-256)` pairs. Document rows hold active random revision identities,
ACL subjects and exact metadata; group rows hold server-side memberships.

| Operation | Data generation | ACL revision | Publication |
| --- | --- | --- | --- |
| Upsert/batch | +1 | +1 | All batch revisions and the new segment manifest commit together |
| Delete existing ID | +1 | +1 | Remove the current metadata row; retained segment text becomes unreachable |
| Replace ACL or groups | unchanged | +1 | Replace the complete permission value |
| Merge | +1 | unchanged | Replace the manifest only if the pinned data generation is still current |
| Delete absent ID | unchanged | unchanged | No state change |

`Catalog.transaction` owns BEGIN, compatibility validation and commit/rollback.
Writers use `BEGIN IMMEDIATE`, then validate format/tokenizer **under the writer
lock**, then mutate. Readers use `BEGIN`; their first compatibility SELECT pins
the WAL snapshot before any cache reuse or document/group reads. Every operation
checks compatibility, including already-warmed Engine instances. A constructor
check alone cannot protect a process from a later incompatible publisher.

Upsert's sequence is:

1. Validate documents and tokenize body text; create new random revisions.
2. Write a sorted segment to a fresh temporary filename. Close gzip, flush and
   fsync the file, rename it, then fsync its containing directory.
3. Acquire the SQLite writer lock and check compatibility. Read the **current**
   manifest, append the segment and publish every new active revision in one
   transaction. Commit with WAL and `synchronous=FULL`.

The SQLite commit is the logical publication point. Two independent writers may
prepare files concurrently, but each appends to the manifest read after acquiring
the lock; neither can discard the other's committed segment. An exception or
process death before commit leaves the preceding catalog state and possibly an
ignored file. A death after commit but before the response leaves a committed write
with an ambiguous acknowledgment. Atlas supplies no request-id deduplication or
exactly-once submission promise: inspect/fetch the ID before deciding whether to
retry. A repeated upsert replaces that ID with another revision.

Merge pins a snapshot, streams its sorted segments with `heapq.merge`, retains only
active revision identities and verifies completeness/uniqueness. It prepares a new
file before reacquiring the writer lock. A changed data generation raises
`StaleGeneration` (HTTP 409); retry starts with a fresh snapshot. ACL-only changes
do not conflict, because merge never replaces documents or group rows. Old files
remain present for requests that already pinned them. Online garbage collection
would need a cross-process reader lifetime protocol; it is not implemented.

## Reader and cache sequence

Within one Engine, an RLock serializes requests and mutation of its caches. It is
not the cross-process lock; SQLite supplies that boundary. Distinct Engine objects
can execute concurrently.

1. Open a short catalog read transaction; validate its format/tokenizer, read both
   revisions and the manifest, then read documents and groups from the same snapshot.
   An unchanged revision pair permits reuse of the previous in-memory catalog view.
2. Stat every referenced file. Load/checksum segments on a new generation or changed
   `(name, size, mtime_ns)` signature, retaining only catalog-selected revisions.
   Reject missing files, missing current revisions or duplicate active revisions.
3. With the coherent snapshot established and file checks complete, look up the
   result LRU using tenant, subject, data generation, ACL revision, normalized query,
   ranking settings and pagination. A hit returns a deep copy **without rescanning
   document ACLs**. A miss constructs visibility and executes the query.

The read transaction can close before file loading: published files are immutable
and retained. A request pinned before a revocation commits may finish under that
snapshot. Any request pinning after the commit sees the newer ACL revision and
cannot hit the former result. Replacing a catalog in place or editing SQL without
advancing revisions violates this publication protocol; restore into a new root
and restart readers. See the [runbook](OPERATIONS.md).

The result LRU holds at most 128 entries; nested dictionaries are copied on insertion
and retrieval. Catalogs and loaded generations remain cached for each accessed tenant
for the Engine lifetime. The tenant working set therefore needs an operational
bound or separate processes. A warm request still performs SQLite header reads and
O(segment count) stat calls. Stat signatures detect ordinary changes, not a privileged
attacker preserving metadata. Checksums are integrity checks, not authentication.

## Query semantics and statistical isolation

For a principal, let `V` contain current documents allowed by `*`, `user:SUBJECT` or
current `group:NAME` memberships, intersected with every explicit equality filter.
Authorization and filters precede term selection, phrases, statistics and facets.
For unique query terms `T`:

- `N = |V|`, including empty documents.
- `avg = sum(body_token_count(d) for d in V) / N`, or zero when N is zero.
- `df(t) = count(d in V where t occurs)`.
- Candidates must contain every term and every exact positional phrase.

For candidate d and term t, with frequency f and length L:

```text
idf = log(1 + (N - df(t) + 0.5) / (df(t) + 0.5))
part(t,d) = idf * f * (k1 + 1) / (f + k1 * (1 - b + b * L / avg))
score(d) = sum(part(t,d) for t in sorted(unique terms))
```

The implementation defaults to k1=1.2, b=0.75. Repeated unquoted terms contribute
once. Repeated terms inside phrases still require separate adjacent positions.
Empty queries browse V with zero scores. All ties break by ascending document ID;
o traversal, set iteration or segment order can change the selected page.

`Scorer` owns the fixed visible statistics. Ranking streams scalar scores through
a heap of at most `offset + limit` entries; only returned hits receive explanation
dictionaries and snippets. For C candidates, T unique terms and prefix P, ranking
costs O(C*T + C*log(P)) with O(P + limit*T) retained ranking state. Visibility and
candidate sets still use O(N) memory, and facets still visit all matches. This is
not compressed or streaming index execution.

Phrase matching chooses the shortest positional list as its anchor, derives a
possible phrase start and binary-searches other sorted lists. For m phrase terms,
r anchor positions and maximum list length f, it uses O(m) auxiliary memory and
O(r*m*log(f)) probes. A rare term avoids copying a long common-term posting.
Equally frequent nonmatches can use more CPU than linear intersection; exhaustive
sliding-window tests establish semantics independently of that planning choice.

Changing only hidden documents cannot change visible hit contents, scores,
explanations, N/df/average length, totals or facets. This is statistical/content
isolation, not concealment of all activity: tenant-wide generation/ACL revisions,
timing and resource contention may still change. Scores across principals or
filters need not be comparable, since their reference collections differ.

## Unicode and representation compatibility

Bodies and query operands use whole-string NFKC semantics followed by casefold,
alphanumeric tokens and attached marks. Source-span clusters join both original
marks and compatibility characters that normalize into marks, and join boundaries
where normalization composes starters. Thus `ｶﾞ`, `カﾞ` and `ガ` match, as do composed,
decomposed and compatibility Hangul. Snippets retain original source spans and escape
text before inserting controlled `<mark>` elements.

The persisted tokenizer identity is `nfkc-casefold-alnum-v2-ucdVERSION`. CPython
3.13.16 uses Unicode 15.1.0 and 3.14.8 uses 16.0.0; they can classify/casefold new
characters differently. Their indexes are deliberately incompatible even though
the file layout is format 1. Neither old v1 postings nor another Unicode database
may be silently reused. The offline [text rebuild](OPERATIONS.md#tokenizer-upgrade-or-interpreter-switch)
retokenizes current text into a fresh root and preserves ACLs, metadata and groups.

## HTTP and browser boundary

Search/fetch/export authenticate before accessing a tenant. Forbidden and missing
IDs share 404. Export counts and its ID-ordered page come from one snapshot and
construct only selected records. Pagination across requests can shift after writes;
Atlas supplies no cross-request snapshot cursor.

Synchronous FastAPI handlers keep loading/scoring off the event loop. The browser
loads local assets under a restrictive CSP, renders document bodies as text, cancels
stale requests and clears in-memory credentials with connection changes/page exit.
Responses prohibit caching, framing and type sniffing. The adapter is a trusted
local static-bearer demonstration, not an identity lifecycle service.

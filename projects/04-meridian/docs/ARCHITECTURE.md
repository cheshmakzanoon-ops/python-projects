# Ledger, publication, and review transactions

Meridian separates accounting facts from derived state. Posted journals and their
postings are the authority. Account balances are rebuildable projections;
reconciliation proposals suggest associations without changing accounting history.
PostgreSQL enforces conservation and publication rules even for ordinary direct
SQL writers. End-user authorization belongs to the application; no RLS claim is made.

## Component boundaries

| Component | Responsibility |
| --- | --- |
| `domain/` | Integer money, immutable journal values, allocation, and independent history folding; no Django dependency. |
| `reconciliation/` | UTC/reference normalization, sparse candidate construction, min-cost assignment, and ambiguity proof; no Django dependency. |
| `application/ledger.py` | Authorization reservation, ordered locks, whole-transaction retry, posting, reversal, replay, and projection repair. |
| `application/reconcile.py` | Immutable imports, bounded account/row scopes, run publication, and terminal decisions. |
| `persistence/` | Models, incremental migrations, database guards, deferred constraints, and native backup/restore. |
| `api/` | Basic authentication, explicit tenant membership, bounded JSON, and HTTP errors. |

## Journal transaction

A posting owns its outer transaction. Calling it inside another `atomic()` block
fails: a returned journal must represent a committed result, and deferred failures
must reach the retry loop rather than escape through a caller's later commit.

1. Validate money, conservation, account uniqueness, and the canonical request key.
2. Acquire shared row locks on the active user and verified membership. Revocation,
   membership deletion, and deactivation cannot commit ahead of this write.
3. Lock the tenant sequencing row exclusively. This serializes that tenant's
   postings and projection rebuilds while other tenants remain independent.
4. Check the tenant/key cache. On a retry, recompute the digest from the referenced
   immutable journal, including postings and reversal target. A stored digest
   alone cannot prove that the cached result represents the request.
5. Lock posting accounts in UUID order and verify tenant/currency agreement.
6. Insert an unsealed journal. A database trigger increments the tenant counter
   and assigns its sequence while holding the counter row lock through commit.
7. Insert postings, update the derived balances with parameterized SQL, and insert
   the idempotent result. Missing projection rows abort the transaction.
8. Deferred database checks verify 2–256 nonzero postings, exact numeric zero sum,
   and the full inverse of an original journal when this is a reversal. The check
   seals the journal. Deferred counter checks require each allocated sequence to
   identify an inserted journal and the current counter to equal the final maximum.
   Commit publishes facts, counter, projections, and key together.

Isolation is READ COMMITTED with these explicit locks, not generic SERIALIZABLE
execution. SQLSTATE `40001` and `40P01` restart the entire operation, with at most
four retries and bounded jitter. A conflict or validation failure is not retried.
Rollback removes the counter increment and every partial fact/projection/key write.

## Sealing and historical order

`meridian_journal.sealed` is database-private publication state. Historical rows
receive `true` during migration. New journal inserts always start with `false`;
the deferred balance/reversal checker changes only that flag to `true`. The
journal guard permits only this monotonic transition with every other field
unchanged. Updates to business fields, reopening, deletion, and later posting
appends are rejected. Sealing early does not bypass the deferred accounting check.

A journal created inside a savepoint remains appendable by its own transaction
until publication. The previous implementation compared tuple `xmin` with a
truncated transaction ID; a savepoint assigns a different physical tuple XID and
incorrectly rejected that valid case. Publication state avoids tuple freezing,
transaction wraparound, and transaction-number collisions after cross-cluster
restore. It costs one additional journal update per successful posting.

The sequencing counter can change only through nested journal allocation. New
tenants start at zero. Ordinary SQL cannot reset or jump the counter and later
insert a lower sequence into an already observed historical prefix. Migration
rejects counters inconsistent with the exact `1..last_sequence` history, including
interior gaps whose maximum still matches the counter.

A PostgreSQL `BEFORE INSERT` trigger runs even when `ON CONFLICT DO NOTHING`
subsequently skips that row. The immediate counter guard therefore cannot by itself
prove publication. Each deferred counter-update event checks its allocated sequence
with an indexed journal lookup; another indexed lookup verifies the final current
counter against the maximum. Checking only the final maximum would miss an ignored
insert followed by a successful insert in the same transaction. Savepoint rollback
removes both its allocation and its queued deferred check. Multiple successful
journals in one transaction validate against final state without requiring a
full-history count on each post. An ignored journal insert is rejected at commit
rather than consuming a gap; application idempotent retries return the existing
journal before attempting another insert.

## Lock relationships

| Operation | Locks after shared user/membership authorization |
| --- | --- |
| Post or reverse | Tenant, then account rows in UUID order, then derived balance rows. |
| Audit or rebuild | Tenant, then projection writes in account UUID order. |
| Statement import | Account; the account guard retains tenant/currency identity. |
| Matching run | Account; statement/match availability remains stable while the graph is assembled. |
| Decision | Selected proposal; database proposal/match guards take a shared account lock. |

Shared authorization locks permit concurrent writes by the same user to independent
tenants. They conflict with revocation/deactivation updates, not with each other.
A revocation already holding its row causes a new writer to wait and recheck the
verified/active predicates after it commits. Read-only paths check membership at
request time; they do not reserve authority for a later independent operation.

Imports and matching helpers may participate in an explicitly supplied outer
transaction. Their locks and deferred checks then last until that outer commit;
returning from a nested helper is not an independent durability acknowledgement.
The HTTP configuration does not wrap requests in an additional transaction.

## Independent projections

Historical balance reads fold only the selected account and sequence prefix, never
trusting its stored projection. Public `history()` deliberately returns a list;
internal replay streams ordered postings in 4,096-row fetch batches. Rebuild memory
therefore depends on account totals and diagnostics rather than retaining every
posting object. The rebuild joins accounts to projections in one streamed query
and uses 512-row UPSERT batches to repair both missing and incorrect rows.

The tenant lock excludes concurrent journal publication during audit/rebuild. A
posting queued behind a rebuild increments the repaired projection afterward;
it cannot be overwritten by a stale repair. Stored sums must fit PostgreSQL bigint;
overflow rejects the whole transaction. Process-death tests cover rollback, not
all possible storage-device failures.

## Matching and decisions

Runs select one tenant-owned account and optionally explicit unmatched statement
UUIDs. At most 10,000 rows and 50,000 SQL-prefiltered postings enter a run; exceeding
either rejects the whole scope. Posting prefiltering preserves signed amount and
the envelope of the selected rows' seven-day UTC calendar windows. Exact candidate
construction still applies each row's own window and caps every connected component
at 32 rows and 256 edges. There is no candidate truncation or partial publication.
Selected row UUIDs are retained in the immutable run summary.

The solver uses unit-capacity min-cost flow. Every statement has an unmatched edge;
residual reverse arcs allow earlier choices to be reassigned. Bellman-Ford preserves
exact integer costs. For each selected pair, forbidding it and solving again detects
an equal-cost alternative. An extra check covers adding an equally priced edge between
an unmatched row and unused posting without removing an existing pair. Independent
complete enumeration verifies both cost and ambiguity on dense and sparse tiny graphs.

| Final proposal state | Approved match | Decision audit |
| --- | --- | --- |
| Pending | None | None |
| Approved | Exactly one matching row/posting identity | Exactly one `approve` event |
| Rejected | None | Exactly one `reject` event |

Deferred checks enforce this table at commit. Decisions are terminal; proposals
cannot be deleted, moved to a different primary UUID, or reopened. Approval consumes statement and posting
identities globally across runs through unique constraints. Concurrent approvals
cannot both commit. A later competing run may contain a now-stale proposal; its
approval fails rather than changing or consuming another match.

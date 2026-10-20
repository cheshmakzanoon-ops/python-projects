# Decisions

1. **Bounded integer money instead of binary floats.** Currency exponents are explicit (USD/CAD/EUR 2, JPY 0, KWD 3). Inputs are decimal strings without exponent/sign-plus/whitespace/leading-zero spellings. Negative allocation mirrors the positive largest-remainder result, preserving stable recipient ties and conservation without a surprising asymmetric rounding rule.
2. **Tenant serialization instead of claiming generic serializability from atomic().** A tenant lock is both the idempotency concurrency boundary and commit-prefix sequence allocator. It sacrifices same-tenant write throughput to make historical accounting meaning precise. Ordered account locks additionally prevent opposite-direction transfer deadlocks. SQLSTATE retries cover whole transactions.
3. **Deferred database constraints instead of serializer-only validation.** A per-row CHECK cannot enforce cross-row conservation. Reviewed PL/pgSQL constraint triggers check journal totals at commit, and immutable triggers prevent later invalidation. Insertion's journal-transaction identity guard prevents appending after posting. Database owners can still alter constraints; role separation is an operational requirement.
4. **Immutable facts and rebuildable projections.** Corrections are linked full reversals. Deleting history to repair a balance destroys auditability. The audit independently sums postings and compares stored balances; replay repairs only the derived projection.
5. **Original bounded matching instead of a black-box optimization package.** Unit-capacity min-cost flow with Bellman-Ford residual paths yields the minimum sum of costs including unmatched choices. Re-solving with selected edges forbidden proves ambiguity from changed matches; an equally priced edge between currently unmatched/unused vertices detects additive unmatched ambiguity. The exhaustive tiny oracle is independently enumerated. Limits apply during graph construction as well as solving. Large dense components fail visibly and require narrowing scope, rather than silently truncating candidates.
6. **Explicit approvals instead of automatic fuzzy repair.** Candidates require equal signed amount/currency within seven days. Reference equality costs zero versus 100 for a mismatch; each day adds 10, unmatched costs 250. Unique solutions are still reviewable proposals; tied solutions are marked ambiguous. Approval consumes identities through database uniqueness. Revocation and partial reversal are intentionally outside the required baseline.
7. **Django Basic authentication at the API boundary.** The existing password hasher verifies each explicit Authorization header; sessions provide no ambient API authority. Cookie-only authentication is rejected; every operation also requires the explicit tenant header, which ordinary cross-origin form submissions cannot set. Do not add permissive cross-origin credential handling. This avoids bespoke token cryptography. TLS is required beyond loopback. Membership is application-enforced; no RLS claim is made.
8. **Owned schema for demonstrations.** Immutable business data intentionally resists deletion. Each reproducible demo instead owns its own entire temporary PostgreSQL schema, with a marker that binds cleanup to the exact target database and schema. Normal database history is unaffected.

9. **One interpretation of request JSON.** Reject duplicate keys and non-finite numbers instead of allowing intermediaries and application code to disagree about a request. Bound nesting and validate Unicode at the HTTP boundary, where failures can return a useful validation response before a transaction starts.

## Publication and authority review

10. **Explicit journal sealing instead of physical tuple identity.** A transaction's
    savepoints have distinct tuple XIDs; physical `xmin` is also subject to freezing
    and wraparound. A database-private monotonic seal expresses the actual contract:
    all postings arrive before publication and never afterward. Deferred validation
    seals the journal only after conservation and reversal checks. The extra update
    is an explicit correctness cost. Restored sealed rows remain sealed in a new cluster.
11. **Authorization reserved through write commit.** A membership check before waiting
    on another lock leaves a revocation race. Shared user/membership locks permit
    concurrent authorized work while making revocation/deactivation wait for existing
    writes. Exclusive authority locks would unnecessarily serialize all tenants for
    the same operator. No database principal-to-end-user identity or RLS is implied.
12. **Cache results verified against facts.** A same-tenant idempotency row can still
    contain the digest of a different journal. Cached returns now hash the actual
    immutable postings and metadata, bounded by the 256-posting journal contract.
    Corruption becomes an explicit conflict, not a false successful response.
13. **Terminal review state enforced at commit.** A status field alone does not prove
    an approval or an audit. Deferred checks couple status, approved-match identity,
    and exactly one audit event while permitting their normal multi-statement
    transaction. Invalid legacy state blocks migration rather than being relabeled.
14. **Whole-scope matching budgets and selected rows.** Component limits alone do not
    bound materializing a large account. Explicit row UUID batches and SQL population
    limits bound preparation before graph construction. Overflow rejects the scope;
    silently dropping candidates would change the optimum and ambiguity result.
15. **Streaming replay and batched repair.** Independent folding remains the source
    of projection truth. Streaming fact reads and batched UPSERT replace a full
    posting list plus per-account reads and writes; the same tenant lock protects
    both approaches from lost increments. Rebuild does not alter posted history.

16. **Validate allocated sequence publication after conflict handling.** PostgreSQL
    runs `BEFORE INSERT` even for an `ON CONFLICT DO NOTHING` row that is never
    inserted. A deferred indexed existence check ties every allocated counter value
    to an immutable journal, and a final maximum check verifies the current counter.
    This catches an interior skipped allocation even when a later insert makes the
    maximum agree. Savepoint rollback discards its deferred events. Upgrade checks
    scan existing history once for the exact sequence prefix; ordinary posts use
    the existing tenant/sequence unique index instead of rescanning that history.

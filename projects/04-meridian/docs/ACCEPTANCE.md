# Required acceptance evidence

Run `MERIDIAN_DATABASE_URL=... [MERIDIAN_PG_CONTAINER=explicit-local-container] uv run --locked pytest`. PostgreSQL is mandatory. There are no service-dependent skips or xfails.

| Gate | Test/evidence |
|---|---|
| ME-01 | `tests/unit/test_domain.py`: strict precision/type/currency/bounds, journal conservation, positive/negative largest-remainder properties; PG direct mixed-currency rejection |
| ME-02 | `test_me02_concurrent_lost_response_canonical_idempotency`: eight concurrent identical requests, reordered replay after response loss, mismatched reuse, one journal/result/projection |
| ME-03 | `test_me03_opposite_transfers_commit_prefix`: eight clients/40 opposing transfers; `test_me03_retry_whole_aborted_transaction_real_sqlstate`: real PostgreSQL 40001 abort, full rollback and retry |
| ME-04 | `test_me04_atomic_fault_and_direct_database_constraints`, non-owner-role test, killed-process rollback: no partial fact/projection/idempotency acknowledgement, invalid sum/append/update/delete rejected |
| ME-05 | deterministic randomized posting/reversal history against independent Python totals at every sequence; explicit held-transaction test proves follower cannot publish a later sequence before first commit; corrupted projection audit/rebuild |
| ME-06 | every API/read/view/reconciliation path verifies tenant membership; foreign account references rejected in API and direct SQL; inactive/unverified membership cannot authorize reads |
| ME-07 | independent exhaustive tiny assignment oracle under Hypothesis; checked-in unmatched ambiguity regression; construction and solver limits; repeated imports/mismatched identities; cross-run concurrent match conflict, stale decisions, explicit review audit |
| ME-08 | previous-schema fixture migration, native PostgreSQL snapshot restore into fresh database, restored immutability, intentionally corrupted derived projection exposed and repaired |

The public CLI demo drives journal creation/retry/reversal through the JSON API and uses application services for concurrent transfers and reconciliation; root settlement integration exercises a live HTTP server with an independent Anchor process. This distinction is explicit: Django's test client is an in-process HTTP request adapter, not proof of network deployment.

Current checks and historical source-specific results are recorded in [verification](VERIFICATION.md). Generated reports include exact source/lock hashes and dirty-state metadata. A source edit invalidates earlier benchmark evidence, even when tests later pass.

Independent review regressions extend ME-06: raw SQL cannot bind tenant A's idempotency key to tenant B's journal; a previous-schema poisoned cache cannot leak its journal even before migration; invalid legacy cache/statement history blocks migration. Both direct SQL and application statement imports race account tenant/currency changes while holding real PostgreSQL locks; the history wins and mutation is rejected. Empty reconciliation runs freeze account identity too. Solver regression costs of 10^100 retain exact integer results without colliding with a finite unreachable-distance sentinel.

`tests/acceptance/test_workload_failure_reporting.py` drives the public CLI dispatch with real PostgreSQL and deliberately corrupts a derived projection, changes a repeated-import return identity, or adds an unexpected persisted statement row. The failed report remains reviewable and the command exits 1. Demo variants inject a bad rebuild or mismatched duplicate response identity and require the same failure propagation. A small normal fixture proves passing checks still succeed; these are correctness tests, not full-profile benchmark measurements.

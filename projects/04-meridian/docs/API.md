# HTTP contract

Bind to loopback with `python -m pp_meridian.cli serve --bind 127.0.0.1:8104`. Every endpoint and focused read view requires `Authorization: Basic ...` and `X-Tenant-ID: UUID`; a real active Django user must have a verified Membership in that tenant. A tenant body field never authorizes access. Use HTTPS before exposing this service outside loopback.

| Method | Route | Body/query and result |
|---|---|---|
| POST | /api/v1/accounts | `{name,currency}` → account UUID |
| POST | /api/v1/journals | `{currency,reference?,postings:[{account_id,amount:decimal-string}]}` + Idempotency-Key → immutable journal |
| POST | /api/v1/journals/{id}/reversal | empty object + Idempotency-Key → linked full reversal |
| GET | /api/v1/journals/{id} | journal/posting UUIDs, sequence, integer minor units |
| GET | /api/v1/accounts/{id}/balance | optional nonnegative `as_of_sequence` → independent replay balance |
| POST | /api/v1/statements/import | `{account_id,source,rows:[{id,amount,currency,timestamp,reference}]}` → stable row UUIDs |
| POST | /api/v1/reconciliation/runs | `{account_id,row_ids?:[UUID,...]}` → run UUID/graph summary |
| GET | /api/v1/reconciliation/runs/{id} | `offset=0..9223372036854775807`, `limit=1..100` → tenant-scoped proposal page/count |
| POST | /api/v1/reconciliation/proposals/{id}/decision | `{decision:"approve"|"reject"}` → audited status |

Errors are JSON `{error:...}` with 400 validation, 403 authentication/membership, 404 tenant-scoped missing identity, 409 idempotency/database/consumption conflict, or 405 wrong method. Request bodies are UTF-8 JSON objects limited to 1 MB and 32 container levels. Duplicate object members, non-finite numbers (including exponent overflow), null characters, and invalid Unicode are rejected before database writes; journal postings to 256; imports to 10000 rows per request. Imports may be chunked using the same source identity. Statement timestamps must include a timezone and normalize to UTC; positive/negative decimal amounts retain their signed direction. Currency must agree with the bank account.

Idempotency canonicalizes sorted `(account UUID, integer amount)` entries, tenant, currency, reference, and reversal target. Reordering postings or using equivalent decimal precision returns the same journal; semantic changes with the same key fail. Reversal permits one full reversal of an original journal. Reversing a reversal is rejected.

Views `/journals/{id}`, `/accounts/{id}`, `/reconciliation/{id}` render escaped, keyboard-accessible record tables with bounded pagination. Account history shows commit sequence, reference, journal identity, and signed minor units; reconciliation pages distinguish ambiguity from approval status. Pagination offers a next page only when more rows exist. These views require the same explicit authentication and tenant headers as the API; a plain browser navigation does not supply `X-Tenant-ID`. Use an authenticated client or a trusted local header-injection tool for viewing them. Validation errors are plain text; record pages disable scripts, forms, external resources, and embedding through CSP. Authenticated responses are marked `no-store`. Review decisions use the same explicit API. No unrestricted list/export routes exist. Native backups are operator-level full-database operations, not end-user tenant exports.

## Transaction and matching contracts

Posting/reversal responses acknowledge an outer committed transaction. Writes retain
shared active-user/membership locks through commit, so revocation/deactivation cannot
commit ahead of an in-flight authorized mutation. Read-only requests check membership
at request time. Historical account balances independently fold that account's posted
history up to `as_of_sequence`; stored projections are not their authority.

Journal inputs contain 2–256 distinct currency-specific accounts, each with a nonzero
signed amount and an exact zero sum. Currency exponents are USD/CAD/EUR 2, JPY 0, KWD 3.
Each posting is bounded to ±10^15 minor units; stored projection totals must fit bigint.
A correction creates one complete linked inverse journal; partial reversals and FX
conversion are outside this interface. Idempotent retries verify the referenced
immutable journal itself as well as the cached digest.

Matching accepts optional `row_ids` from import responses. Selections must be unique,
unmatched, and in the selected account. Omission selects all unmatched rows. Runs cap
the selected population at 10,000 rows and SQL-prefiltered postings at 50,000, then cap
each connected component at 32 rows/256 edges. An overflow rejects the entire run.
The immutable summary retains `selected_row_ids`; `postings` counts the prefiltered
eligible population. These budgets do not truncate the matching graph.

Candidate pairs require equal signed amount/currency within seven UTC calendar days.
Cost is 10 per day plus 100 for a non-exact normalized reference; unmatched costs 250.
The minimum total includes unmatched rows. Equal-cost alternatives are marked ambiguous;
a unique solution still requires review. Approval requires a pending proposal and
consumes the row/posting globally. Approval and rejection are terminal and each has
exactly one immutable decision audit. A competing consumed match returns 409.

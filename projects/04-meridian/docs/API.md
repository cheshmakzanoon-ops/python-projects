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
| POST | /api/v1/reconciliation/runs | `{account_id}` → run UUID/graph summary |
| GET | /api/v1/reconciliation/runs/{id} | `offset=0..9223372036854775807`, `limit=1..100` → tenant-scoped proposal page/count |
| POST | /api/v1/reconciliation/proposals/{id}/decision | `{decision:"approve"|"reject"}` → audited status |

Errors are JSON `{error:...}` with 400 validation, 403 authentication/membership, 404 tenant-scoped missing identity, 409 idempotency/database/consumption conflict, or 405 wrong method. Request bodies are UTF-8 JSON objects limited to 1 MB and 32 container levels. Duplicate object members, non-finite numbers (including exponent overflow), null characters, and invalid Unicode are rejected before database writes; journal postings to 256; imports to 10000 rows per request. Imports may be chunked using the same source identity. Statement timestamps must include a timezone and normalize to UTC; positive/negative decimal amounts retain their signed direction. Currency must agree with the bank account.

Idempotency canonicalizes sorted `(account UUID, integer amount)` entries, tenant, currency, reference, and reversal target. Reordering postings or using equivalent decimal precision returns the same journal; semantic changes with the same key fail. Reversal permits one full reversal of an original journal. Reversing a reversal is rejected.

Views `/journals/{id}`, `/accounts/{id}`, `/reconciliation/{id}` render escaped, keyboard-accessible record tables with bounded pagination. Account history shows commit sequence, reference, journal identity, and signed minor units; reconciliation pages distinguish ambiguity from approval status. Pagination offers a next page only when more rows exist. These views require the same explicit authentication and tenant headers as the API; a plain browser navigation does not supply `X-Tenant-ID`. Use an authenticated client or a trusted local header-injection tool for viewing them. Validation errors are plain text; record pages disable scripts, forms, external resources, and embedding through CSP. Authenticated responses are marked `no-store`. Review decisions use the same explicit API. No unrestricted list/export routes exist. Native backups are operator-level full-database operations, not end-user tenant exports.

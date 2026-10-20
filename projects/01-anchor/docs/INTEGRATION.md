# Integration contract

Anchor is installed and run independently of sibling packages. Integrations register
async activities through `ActivityRegistry`, submit a `Definition`, and exchange
versioned files or HTTP requests. They must not import another project's source tree.

## Service and isolation

Use a dedicated PostgreSQL database through `ANCHOR_DATABASE_URL` and a separate
engine schema for each integration run. Tests fail when their required database is
missing. The local control API binds to loopback port 8101. Linux is required for
process-termination tests; both CPython 3.13.16 and 3.14.8 are supported.

## External effects

An activity may execute more than once. Derive a stable downstream idempotency key
from `ActivityContext.business_key` and the logical business operation, retaining
that identity across retries. Do not put attempt numbers or lease epochs into the
key: those identify executions, not a new business operation.

The settlement demonstration uses Meridian's public HTTP interface. It kills a
worker after the ledger commit and retries the same journal key, then exercises
reversal compensation after a later failure. The integration does not claim that
Meridian supports cancelling an uncommitted future journal. Anchor's synthetic
provider separately demonstrates the terminal fence needed to reject a late effect
that resumes after cleanup.

For arbitrary external systems, document the downstream idempotency, query and
reversal contracts before choosing a recovery policy. A stale lease only rejects
engine updates; it cannot revoke an external request already in flight.

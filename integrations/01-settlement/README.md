# Recoverable simulated settlement

Run `python scripts/portfolio.py integration settlement` after setting up Anchor and Meridian and their local PostgreSQL services. The coordinator starts a loopback Django WSGI server in Meridian's environment, then drives it from an Anchor activity in Anchor's separate environment.

The worker posts a balanced CAD journal, receives a committed response, then is killed before acknowledging completion to Anchor. Its lease expires. Another worker retries the same business idempotency key and receives the same journal ID. A second workflow posts, deliberately fails a later step, and invokes a supported full reversal. The adapter verifies the completed/compensated histories, one logical posting per business operation, three total journals including the reversal, balanced postings, and independently replayed balances.

HTTP evidence excludes authentication headers. All accounts and credentials are synthetic and local. Owned PostgreSQL schemas and the HTTP server are cleaned in `finally` blocks. This does not claim arbitrary financial providers support cancellation-before-post or rollback; Anchor's fenced synthetic provider tests that separate race.

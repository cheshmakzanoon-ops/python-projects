# Shared changes

A04-R01 (coordinator acknowledged): root CI/immutable verification must supply MERIDIAN_DATABASE_URL and matching PostgreSQL native backup tools. Local execution uses MERIDIAN_PG_CONTAINER=pp-meridian-dev. CI binds it to its explicit PostgreSQL 17 service-container ID. This is required by ME-08; absent native tools fail rather than skip.

A04-R02 (coordinator-owned integration): settlement uses authenticated HTTP Basic, X-Tenant-ID, Idempotency-Key, and decimal-string journal postings. Responses expose id, journal_id, sequence, posting identities. Reversal is POST /api/v1/journals/{id}/reversal. No sibling import is required.

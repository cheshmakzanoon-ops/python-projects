# Repository architecture

The repository contains ten independent Python distributions and a standard-library task dispatcher. Each product owns its source layout, dependency lock, interpreter pin, tests, and documentation. There is no shared application framework or root uv workspace: installing an audio dependency must not change a storage engine's resolution.

## Boundaries

| Layer | Responsibility | Dependency direction |
| --- | --- | --- |
| Product domain core | State transitions, algorithms, invariants | Python and declared library dependencies |
| Product adapters | Persistence, HTTP, CLI, serialization | The owning domain core |
| Integration adapters | Demonstrate public exchange contracts | Installed CLIs, JSON files, HTTP |
| Repository tooling | Select tasks, bound processes, build docs, capture evidence | Manifest and subprocess interfaces |

Sibling source imports are prohibited. Integrations use separate environments and public interfaces, so packaging defects and contract mismatches remain visible. The dispatcher uses argument arrays, explicit working directories, timeouts, and POSIX process-group cleanup.

## State and services

Anchor stores history, timers, leases, and idempotency state in PostgreSQL. Meridian uses PostgreSQL transactions and constraints for ledger invariants. These products have separate development databases. Current, Quarry, Atlas, and Proving Ground use SQLite catalogs for local publication; Strata implements its own WAL and tables. Numerical libraries provide array kernels rather than the products' domain algorithms.

Generated state belongs under `.local/`. The service helper manages only containers with the expected ownership label and loopback binding. Demo cleanup checks product ownership before removing its state. Neither operation is a general database reset tool.

## Runtime and validation

All products pin CPython 3.14.8 and retain CPython 3.13.16 compatibility. Keep virtual environments separate when checking both interpreters. Build outputs are shared within a product, so those checks run sequentially. The dispatcher itself needs Python 3.11+ for `tomllib` and does not import product dependencies.

`portfolio.toml` declares commands, paths, services, and supported platforms. Normal CI validates changed products on both Python families and runs all three public integrations. Shared or unrecognized changes select the full matrix. The aggregate gate rejects failures, cancellations, and unexpected skipped jobs.

[Product requirements](../REQUIREMENTS.md) define scope; [CONTRIBUTING.md](../../CONTRIBUTING.md) defines development commands. [Verification status](../STATUS.md) names tested revisions. Filesystem, database, and external-effect guarantees remain specific to each product's documented boundary.

# Repository architecture

Ten independent distributions share development tooling, not an application runtime. Each owns its source, lockfile, interpreter declaration, persistence formats, tests, and operational documentation. Installing an audio dependency cannot change a storage engine's resolution. There is deliberately no root uv workspace and no shared domain framework.

## Dependency and ownership boundaries

| Layer | Owns | Depends on |
| --- | --- | --- |
| Product domain core | Algorithms, state transitions, semantic invariants | Python and its declared libraries |
| Product adapters | Persistence, HTTP, CLI, serialization | Its own domain core |
| Integration adapters | Public exchange mapping and end-to-end checks | Installed CLIs, JSON files, HTTP |
| Repository tooling | Catalog validation, task selection, process lifecycle, builds, evidence | Standard library, manifest, subprocess interfaces |

Production source cannot import a sibling package or alter the import path to reach it. [`check_architecture.py`](../../scripts/check_architecture.py) checks explicit imports, literal dynamic imports, and common path-mutation forms without importing applications. It is a development guard, not a sandbox or a complete analysis of arbitrary computed imports. The public integrations keep packaging and exchange mismatches observable by using separate product environments.

The root command catalog is parsed once through [`catalog.py`](../../scripts/catalog.py). Local dispatch and CI selection use the same validated identities, contained/nonoverlapping paths, command arrays, and exact interpreter versions. Packaging consistency checks compare distribution names, CLI entry points, and `.python-version` against those declarations. A file-presence check is never called an executed acceptance test.

## Persistence and concurrency boundaries

| Product | Durable authority | Coordination and publication | Owning design |
| --- | --- | --- | --- |
| Anchor | PostgreSQL event history plus transactional projections | Run-row lock; history and tasks/timers commit together; worker epochs fence stale completions | [Replay and compensation](../../projects/01-anchor/docs/ARCHITECTURE.md) |
| Strata | Its own WAL, SSTables, manifest | One owner; serialized commit publication; retained MVCC snapshots and file handles | [Storage and recovery](../../projects/02-strata/docs/ARCHITECTURE.md) |
| Current | SQLite ingress/checkpoint/outbox | Ordered durable ingress; checkpoint-prefix ownership; versioned output deliveries | [Event-time runtime](../../projects/03-current/docs/ARCHITECTURE.md) |
| Meridian | PostgreSQL immutable postings and constraints | Tenant commit-order lock, ordered account locks, atomic journal/projection/idempotency | [Ledger and reconciliation](../../projects/04-meridian/docs/ARCHITECTURE.md) |
| Quarry | SQLite catalog/checkpoints and immutable Parquet | Single writer; files precede catalog publication; retained reader pins | [Incremental publication](../../projects/05-quarry/docs/ARCHITECTURE.md) |
| PyTrace | Source/configuration identities and derived analysis cache | Bounded parsing and fixed-point analysis; hash-checked explicit edits | [Analysis and edits](../../projects/06-pytrace/docs/ARCHITECTURE.md) |
| Atlas | Tenant SQLite catalog and immutable index segments | Coherent generation/revision/ACL snapshot; atomic generation publication | [Search visibility](../../projects/07-atlas/docs/ARCHITECTURE.md) |
| Proving Ground | Dataset/split/artifact identities and SQLite registry | Staged content publication; registry generation comparison; immutable serving snapshots | [Model lifecycle](../../projects/08-proving-ground/docs/ARCHITECTURE.md) |
| Routecraft | Validated problem and verified solution records | Bounded seeded search; independent feasibility/objective verification | [Search and replanning](../../projects/09-routecraft/docs/ARCHITECTURE.md) |
| Resonance | Audio/configuration provenance and analysis outputs | Sample-based timing; bounded chunk state; explicit export/report publication | [Audio pipeline](../../projects/10-resonance/docs/ARCHITECTURE.md) |

These boundaries are intentionally different. A PostgreSQL transaction, a synchronized file/manifest sequence, and an in-memory serving snapshot solve different publication problems. Each product's runbook identifies uncertain outcomes, supported old formats, and repair procedures. Integrations add no distributed transaction guarantee across participants.

## Runtime and artifact isolation

The default interpreter is CPython 3.14.8; compatibility runs use 3.13.16. The dispatcher requires Python 3.11+ and does not import product dependencies. It launches argument arrays in an explicit project directory, strips inherited Python source selectors, bounds process execution, and cleans the POSIX process group on failure/timeout.

Default project environments live in their `.venv`. Compatibility environments live under `.local/venvs/PROJECT-PYTHON`; each check's JUnit and build outputs live under a fresh `.local/checks/PROJECT/PYTHON/RUN`. A global shared environment is refused for `verify-all`. Wheel smoke checks install exactly one wheel from that check's build directory into a fresh environment and run outside the source tree.

Generated state belongs under `.local/`. Anchor and Meridian have separate local PostgreSQL services. The service helper verifies an ownership label and loopback binding before managing a container; cleanup removes only selected product-owned state. These helpers are for synthetic local workflows, not production service administration.

## Validation and evolution

Normal CI checks changed products on both declared Python patches and runs all three public integrations. Shared or unrecognized changes select the complete matrix. The aggregate gate rejects failures, cancellations, and unexpected skipped jobs. Root checks enforce catalog/packaging consistency and source independence as well as dispatcher behavior.

Final verification uses an exact detached source commit. Reports bind actual JUnit outcomes, logs, locks, project/shared source hashes, and unchanged-source checks. Evidence added later retains the identity of the earlier source. [Verification method](VERIFICATION.md) explains independent models and controlled fault schedules; [status](../STATUS.md) distinguishes local execution, historical measurements, and hosted CI observations.

A semantic or persisted-format change belongs to the owning product and includes compatibility tests plus actionable operator instructions. A public exchange change also requires affected integration checks. See [product requirements](../REQUIREMENTS.md) for stable acceptance identifiers and [development commands](../../CONTRIBUTING.md) for execution details.

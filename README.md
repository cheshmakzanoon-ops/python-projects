# Python systems portfolio

Ten independent Python projects covering durable execution, storage, streaming, accounting, analytical data, language tooling, search, model operations, optimization, and audio analysis. Each package implements its own domain core and includes a locked environment, executable demonstrations, failure tests, and an operational runbook.

Start with **Current**. Its demonstration processes 10,000 events, interrupts a checkpointing process, recovers the durable input, and compares the result with an independent oracle. No database service or external account is needed.

```sh
# Prerequisites: Linux, Python 3.11+ for the dispatcher, and uv 0.12.23.
python scripts/portfolio.py doctor
python scripts/portfolio.py setup current
python scripts/portfolio.py demo current
python scripts/portfolio.py clean-demo current
```

`setup` installs the project's pinned interpreter and locked dependencies. Generated state stays under `.local/`; cleanup removes only the selected demonstration's owned state. See [development setup](CONTRIBUTING.md) for tests, Python compatibility, and PostgreSQL.

## Projects

| Project | Engineering focus | Start here |
| --- | --- | --- |
| [Anchor](projects/01-anchor/) | Deterministic replay, persisted timers, worker leases, fenced compensation | [Replay and failure boundaries](projects/01-anchor/docs/ARCHITECTURE.md) |
| [Strata](projects/02-strata/) | Framed WAL, MVCC snapshots, SSTables, compaction, crash recovery | [Storage format and tradeoffs](projects/02-strata/docs/DECISIONS.md) |
| [Current](projects/03-current/) | Event-time ordering, watermarks, late revisions, checkpoint/outbox recovery | [Run the streaming demo](projects/03-current/README.md) |
| [Meridian](projects/04-meridian/) | Double-entry constraints, tenant isolation, idempotency, reconciliation | [Ledger invariants](projects/04-meridian/docs/ARCHITECTURE.md) |
| [Quarry](projects/05-quarry/) | Incremental DAGs, versioned inputs, pinned Parquet snapshots, publication | [Incremental execution](projects/05-quarry/docs/ARCHITECTURE.md) |
| [PyTrace](projects/06-pytrace/) | Control-flow graphs, fixed-point dataflow, conservative source edits | [Analysis and abstention](projects/06-pytrace/docs/DECISIONS.md) |
| [Atlas](projects/07-atlas/) | Positional indexing, permission-aware BM25, generation publication | [Authorization and ranking](projects/07-atlas/docs/ARCHITECTURE.md) |
| [Proving Ground](projects/08-proving-ground/) | Data leakage controls, evaluation lineage, promotion, serving generations | [Experiment lifecycle](projects/08-proving-ground/docs/ARCHITECTURE.md) |
| [Routecraft](projects/09-routecraft/) | Routing heuristics, directed costs, independent feasibility checks | [Optimization constraints](projects/09-routecraft/docs/ARCHITECTURE.md) |
| [Resonance](projects/10-resonance/) | YIN pitch estimation, onset decoding, alignment, audio/MIDI reports | [Audio workbench](projects/10-resonance/README.md) |

Every product exposes the same `setup`, `check`, `demo`, and `benchmark` tasks through `scripts/portfolio.py`. Environments and dependencies remain independent. Cross-project examples use public JSON or HTTP contracts: [recoverable settlement](integrations/01-settlement/), [stream corrections into historical lake snapshots](integrations/02-stream-lake/), and [authorized search of code-analysis findings](integrations/03-code-search/).

## Reviewing the engineering

For a focused first review, follow [Anchor's event reducer](projects/01-anchor/src/pp_anchor/replay/reducer.py) into its PostgreSQL fencing tests; compare [Current's independent oracle](projects/03-current/tests/property/test_oracle.py) with recovery behavior; or examine [Quarry's publication-failure tests](projects/05-quarry/tests/integration/test_crash.py). The [reviewer guide](docs/PORTFOLIO_GUIDE.md) provides routes by discipline and links one difficult test to each system.

Architecture documents explain transaction and persistence boundaries. Case studies discuss reproduced defects and rejected alternatives. [Verification records](docs/STATUS.md) distinguish tested revisions, local checks, hosted CI observations, and historical performance measurements. The [evidence policy](docs/architecture/EVIDENCE.md) defines source hashes, isolated wheel checks, and benchmark interpretation.

The [latest reliability and interface review](docs/QUALITY_REVIEW.md) documents the persistence, validation, security, and usability changes across all ten products, with their committed-source verification results.

## Scope and limitations

The supported verification target is Linux with standard CPython 3.13.16 and 3.14.8. Anchor and Meridian require local PostgreSQL; other core workflows need no paid API, cloud account, GPU, or external dataset. Demonstration services are local tools and require additional deployment controls before use on a shared network; read [SECURITY.md](SECURITY.md).

Workloads are synthetic. Their measurements do not establish production capacity, and process termination does not simulate every power-loss failure. Individual runbooks describe narrower format, algorithm, and resource limits.

No code license has been selected. [Third-party notices](THIRD_PARTY_NOTICES.md) record dependency and asset provenance; dependency licenses do not grant a license to this repository's code.

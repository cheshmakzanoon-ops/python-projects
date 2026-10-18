# Reviewer guide

Start with the [verified status](STATUS.md), which separates local checks, required workloads and remote CI. All ten products are independent packages. The [master brief](../PYTHON_PORTFOLIO_MASTER_EXECUTION_BRIEF.md) is preserved unchanged as the specification; each product maps its eight acceptance IDs in `docs/ACCEPTANCE.md`.

For a five-minute first run, install uv 0.12.23, then run:

```sh
python scripts/portfolio.py setup current
python scripts/portfolio.py demo current
python scripts/portfolio.py clean-demo current
```

The Current demo processes actual event/control records, kills a checkpointing child, recovers the durable prefix and compares results with an independent batch oracle. It needs no external service. See [environment setup](ENVIRONMENT.md) for the two PostgreSQL products.

## Three detailed starting points

1. **Durable workflows:** read [Anchor's reducer](../projects/01-anchor/src/pp_anchor/replay/reducer.py), then its [acceptance map](../projects/01-anchor/docs/ACCEPTANCE.md). Follow lease epochs, replay diagnostics and stale-worker tests into the PostgreSQL adapter. The settlement integration demonstrates a real HTTP effect followed by worker death and a retry with one ledger identity.
2. **Event time and recovery:** read [Current's generated oracle tests](../projects/03-current/tests/property/test_oracle.py) and [persistence faults](../projects/03-current/tests/integration/test_persistence.py). Then inspect the stream-lake integration: a correction changes the latest aggregate while a pinned historical snapshot retains the earlier value.
3. **Incremental analytical data:** read [Quarry's execution engine](../projects/05-quarry/src/pp_quarry/execution/engine.py), [version registry](../projects/05-quarry/src/pp_quarry/storage/catalog.py) and [crash tests](../projects/05-quarry/tests/integration/test_crash.py). Examine exact historical fingerprints, partition invalidation and immutable publication before reading performance results.

## Routes by interest

| Interest | Products | Mechanisms |
| --- | --- | --- |
| Backend reliability | Meridian → Anchor → Current | Deferred ledger constraints, lease epochs, checkpoint/outbox |
| Data engineering | Quarry → Current → Proving Ground | Partition reuse, event-time revisions, leakage controls |
| Algorithms and systems | Strata → PyTrace → Routecraft | WAL/MVCC, fixed-point dataflow, independently verified routing |
| Search and applied ML | Atlas → Proving Ground → Resonance | Visible-set BM25, promotion CAS, numerical uncertainty |
| Music and numerical work | Resonance | Ground-truth synthesis, pitch/onset estimates, alignment and playable evidence |

Every product has a README, architecture, decisions, operations, acceptance, benchmarks and case study. Case studies discuss an invariant, rejected alternative, reproduced defect, measured bottleneck, limitation and justified next step. [Independent review notes](evidence/INDEPENDENT_REVIEW.md) describe adversarial findings and corrections. Synthetic fixtures do not establish customer adoption, production capacity or real-world model accuracy.

Use [repository architecture](architecture/REPOSITORY.md) to understand dependency isolation and [evidence policy](architecture/EVIDENCE.md) to interpret source hashes, clean clones and measurement limits. Linux is required for process-fault and storage suites. Windows/macOS results are not claimed.

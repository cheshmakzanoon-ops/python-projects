# Reviewer guide

Start with [verification status](STATUS.md), which separates local checks, measured workloads, and hosted CI. All ten products are independent packages. [Product requirements](REQUIREMENTS.md) define their scope; each product maps acceptance criteria to tests in `docs/ACCEPTANCE.md`.

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

## One module and one difficult test per route

| Route | Source | Challenge |
| --- | --- | --- |
| Backend | [Anchor reducer](../projects/01-anchor/src/pp_anchor/replay/reducer.py) | [PostgreSQL contracts](../projects/01-anchor/tests/integration/test_postgres_contract.py): stale workers, durable scheduling and compensation |
| Data | [Quarry execution](../projects/05-quarry/src/pp_quarry/execution/engine.py) | [Process-death publication](../projects/05-quarry/tests/integration/test_crash.py) |
| Algorithms | [Strata WAL](../projects/02-strata/src/pp_strata/wal/frames.py) | [Storage fault boundaries](../projects/02-strata/tests/acceptance/test_faults.py) |
| Search/ML | [Atlas engine](../projects/07-atlas/src/pp_atlas/engine.py) | [Persistence and authorization](../projects/07-atlas/tests/integration/test_persistence_auth.py): hidden documents and revocation |
| Music | [Resonance pitch difference](../projects/10-resonance/src/pp_resonance/pitch/difference.py) | [Independent numerical references](../projects/10-resonance/tests/unit/test_numerics.py) |

## Engineering decisions

Each case study connects an invariant to a rejected alternative, a reproduced failure, a measured workload, and a justified next step. A measured bottleneck is distinct from an optimization hypothesis. The linked studies retain their original source revisions and limits; verification status indexes subsequent checks.

| Product and case study | Design question |
| --- | --- |
| [Anchor](../projects/01-anchor/docs/CASE_STUDY.md) | Why an epoch check at acknowledgement cannot undo an already published effect; provider fencing and unresolved cleanup |
| [Strata](../projects/02-strata/docs/CASE_STUDY.md) | Why uncertain publication poisons a writer; snapshot-safe compaction and the cost of durable commits |
| [Current](../projects/03-current/docs/CASE_STUDY.md) | Why idle/resume controls belong to the durable input order; heap-driven expiration and bounded joins |
| [Meridian](../projects/04-meridian/docs/CASE_STUDY.md) | Why Python validation needs database constraints; tenant serialization, canonical retries and exact matching ambiguity |
| [Quarry](../projects/05-quarry/docs/CASE_STUDY.md) | Why a global snapshot identity defeats partition reuse; GC ordering and historical identity retention |
| [PyTrace](../projects/06-pytrace/docs/CASE_STUDY.md) | Why a literal rewrite can create a docstring; finite may-analysis, abstention and parser startup cost |
| [Atlas](../projects/07-atlas/docs/CASE_STUDY.md) | Why hidden documents must not alter visible BM25 statistics; authorization cost and narrow relevance labels |
| [Proving Ground](../projects/08-proving-ground/docs/CASE_STUDY.md) | Why semantic experiment identity differs from archive bytes; train-only transformations and applied generations |
| [Routecraft](../projects/09-routecraft/docs/CASE_STUDY.md) | Why directed reversal needs full schedule evaluation; honest heuristic misses and fixed physical cargo |
| [Resonance](../projects/10-resonance/docs/CASE_STUDY.md) | Why uncertain frames stay in the evaluation; fixed sample time, same-pitch attacks and real-recording limits |

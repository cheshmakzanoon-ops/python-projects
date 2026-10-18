# Reviewer guide

The portfolio is under active implementation. Consult [status](STATUS.md) before interpreting any project as complete. The [repository architecture](architecture/REPOSITORY.md) explains isolation and ownership; the [evidence policy](architecture/EVIDENCE.md) explains what verified results establish.

Choose a route based on your interests:

| Interest | Suggested products | Mechanisms to inspect |
| --- | --- | --- |
| Backend reliability | Meridian → Anchor → Current | Ledger constraints, lease epochs, checkpoints |
| Data engineering | Quarry → Current → Proving Ground | Incremental invalidation, event-time correction, leakage controls |
| Algorithms and systems | Strata → PyTrace → Routecraft | WAL/MVCC, fixed-point dataflow, independent feasibility |
| Search and applied ML | Atlas → Proving Ground → Resonance | ACL-aware BM25, promotion generations, pitch estimation |
| Music and numerical work | Resonance | Ground-truth audio generation, onset/pitch/alignment evidence |

Each product's case study should explain one invariant, one rejected alternative, a reproduced defect and regression, a measured bottleneck, a known limitation, and the next justified improvement. These are portfolio implementations, not claims of employment, customer adoption, or production operating history.

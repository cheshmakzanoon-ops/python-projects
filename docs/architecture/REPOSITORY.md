# Repository architecture

The ten products are independent Python distributions. Each has a src layout, pyproject, lock, interpreter declaration, tests, docs, and CLI. Root tooling dispatches subprocesses in the selected product directory. No sibling source imports or shared application framework are allowed. The dispatcher uses argument arrays, explicit timeouts, and process-group cleanup on supported POSIX hosts.

The coordinating agent owns shared files and Git. Each implementation agent owns only one product directory. Six worker slots are available alongside the coordinator; the first six assignments run concurrently, with Atlas, Proving Ground, Routecraft, and Resonance initially queued. This is a real runtime limit, not a ten-worker concurrency claim.

PostgreSQL is required for Anchor's lease/idempotency/history transactions and Meridian's ledger invariants. SQLite catalogs support local transactional publication in Current, Quarry, Atlas, and Proving Ground. Strata implements its own storage. NumPy/SciPy/scikit-learn supply numerical primitives; they do not replace the authored product algorithms.

The integration adapters exchange documented files or HTTP messages between independently installed products. The required demonstrations cover recoverable settlement, version-preserving stream-to-lake ingestion, and authorized search of code-analysis findings. Their implementation and verification status are reported separately from individual product tests.

The shared contract is described in the root AGENTS.md and master execution brief. All ten products default to CPython 3.14.8 after successful compatibility checks; CPython 3.13.16 remains a required matrix entry. Dependency resolution is explicit; CI uses locked installations and selects its interpreter explicitly. The image's Python 3.12 runs only the standard-library root dispatcher.

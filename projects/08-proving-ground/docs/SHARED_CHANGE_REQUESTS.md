# Coordinator requests

1. Register Proving Ground with default Python 3.14.8 (full local checks now passed); required compatibility remains Python 3.13.16. Linux is the tested durability/failure platform. Only Linux has been validated. Windows is currently unsupported by the CLI resource-metrics import; macOS durability/installation has not been verified.
2. Keep the root benchmark dispatch thread environment at OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=1, and use absolute owned result directories outside tracked source.
3. Standard benchmark lease is reserved for the coordinator's immutable committed-source verification. Do not treat CI's 5,000 rows as evidence for the required 250,000-row/40-feature full workload.
4. No sibling dependency or integration adapter is required for this project's runtime.

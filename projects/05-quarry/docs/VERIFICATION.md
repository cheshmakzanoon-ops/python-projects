# Verification

Quarry supports CPython 3.13.16 and 3.14.8 on Linux. Each interpreter uses its own environment and the committed dependency lock. Directory-fsync and process-death tests require a local POSIX filesystem; other platforms are unverified.

## Maintenance checks

The current integrity and input-validation changes passed **93 tests on each of CPython 3.13.16 and 3.14.8**, including process-death, historical-version, independent-rebuild, reader-pin, schema-evolution and source-mutation regressions. Ruff formatting/lint and strict mypy passed for all 20 source modules. Both interpreter checks also built the sdist and wheel, installed the wheel with locked runtime dependencies into an isolated temporary environment, and completed its public demo outside the source tree. The demo passed independent-rebuild, one-bucket-only and old-snapshot checks, then removed only its owned output.

The new cases cover incomplete or unknown manifest topology, modified valid Parquet, inconsistent manifest schemas/row counts, unsafe recovery references, fractional/boolean resource and row bounds, non-finite quality bounds, invalid SQL projection names, query limits and catalog cleanup after malformed stored configuration. Rejected publication leaves no additional snapshot, source checkpoint or event identity; snapshot pins are released on read failures. Nine malformed-manifest cases exercise empty/missing/extra buckets and nodes, swapped bucket files, unknown format and broken entries; query, validation, reuse and recovery refuse them without pruning snapshots, accepting checkpoints or changing any data-file bytes. A zero-row snapshot with the complete graph remains valid and queryable.

The current project source/test/lock digest is `0f327d83420bdba3572a216dfdfb3344b15b75b5a1ea296f6bbd997e0beae47d`, using the scope declared by `pp_quarry.evidence.provenance`. These are working-tree checks, not an immutable release or a hosted CI result.

Reproduce from this project directory:

```sh
uv sync --locked --python 3.14.8
uv run --locked --python 3.14.8 ruff format --check .
uv run --locked --python 3.14.8 ruff check .
uv run --locked --python 3.14.8 mypy src
uv run --locked --python 3.14.8 pytest -q -W error::ResourceWarning
uv build --no-sources --python 3.14.8
```

For compatibility, select Python 3.13.16 and set `UV_PROJECT_ENVIRONMENT` to a separate path under the repository's `.local/venvs/`. Run interpreters sequentially because they share package build outputs. The root `python scripts/portfolio.py check quarry` also installs the built wheel into an isolated environment and executes its public demo outside the source tree.

## Historical evidence

These measurements retain their original source revisions; they do not measure the current implementation's additional integrity checks.

| Record | Source and result |
| --- | --- |
| [Original 3.13 verification](../../../docs/evidence/final/python313/quarry-3.13.16.json) and [3.14 verification](../../../docs/evidence/final/python314/quarry-3.14.8.json) | Clean commit `7114e39c7e9e8af177e84fe8cd990fe5a09bde63`: 37 tests per interpreter, format/lint/types, packaging, installed-wheel demo and CI workload. |
| [Standard measured report](../../../docs/evidence/final/standard/quarry-3.14.8-benchmark-benchmark.json) and [verification wrapper](../../../docs/evidence/final/standard/quarry-3.14.8.json) | Clean commit `59443e2bcdfc6a1dd81f8334c108474eef2d3030`: five million originals, 500,000 corrections, 100,000 deletes and 100 schema additions; independent rebuild and forced Parquet rebuild agree. |
| [Correctness review](../../../docs/REVIEW.md) | Subsequent 51-test suites on both interpreters cover safe snapshot opening, manifest containment and wildcard rejection, nullable JSON projection, finite numeric range and SQL name collisions. |
| [Python 3.14 development workload](../artifacts/ci-development.json) and [3.13 development workload](../artifacts/ci-313-development.json) | Earlier dirty-checkout records retain source/lock hashes, warmup parameters, repetitions and their actual dirty flags. They are not committed-source acceptance records. |

The standard run produced 4,900,100 live rows and 5,600,100 historical identities. Its full interpretation, cache conditions, hashes and unfavorable incremental/full-rebuild comparison are in [benchmarks](BENCHMARKS.md). No costly workload was rerun for this maintenance change.

## Boundaries

One local writer owns publication; concurrent readers register persistent pins. Exact historical identities grow indefinitely. Stale pins require offline diagnosis and are never expired automatically. Engine memory settings are not process-RSS limits. Checksums detect content drift relative to a trusted catalog; they do not authenticate an attacker-controlled dataset. Distributed writers, object storage and full Iceberg/Delta compatibility are outside the supported contract.

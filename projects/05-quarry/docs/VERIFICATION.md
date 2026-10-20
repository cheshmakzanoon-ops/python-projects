# Verification

Quarry supports CPython 3.13.16 and 3.14.8 on Linux. Each interpreter uses its own environment and the committed dependency lock. Directory-fsync and process-death tests require a local POSIX filesystem; other platforms are unverified.

## Maintenance checks

The current implementation passed **107 tests on each of CPython 3.13.16 and 3.14.8**, with zero failures/errors/skips. Ruff formatting/lint passed (49 checked files), and strict mypy passed for all 21 source modules. Both full dispatcher checks built the sdist and wheel, installed the wheel with locked runtime dependencies into an isolated temporary environment, and completed its public demo outside the source tree. The demo passed independent facts/daily rebuilds, one-bucket-only and old-snapshot checks, then removed only its owned output. Root documentation validation also passed 566 local links and a strict MkDocs build.

The new cases cover incomplete or unknown manifest topology, modified valid Parquet, inconsistent manifest schemas/row counts, unsafe recovery references, fractional/boolean resource and row bounds, non-finite quality bounds, invalid SQL projection names, query limits and catalog cleanup after malformed stored configuration. Rejected publication leaves no additional snapshot, source checkpoint or event identity; snapshot pins are released on read failures. Nine malformed-manifest cases exercise empty/missing/extra buckets and nodes, swapped bucket files, unknown format and broken entries; query, validation, reuse and recovery refuse them without pruning snapshots, accepting checkpoints or changing any data-file bytes. A zero-row snapshot with the complete graph remains valid and queryable.

The execution-boundary review adds 14 test executions: within/across-bucket aggregate overflow; legacy nonfinite output under a limited read; immutable caller-supplied contract fields; quality-only and schema-only invalidation; bounded frozen lineage through obsolete arrivals/retention; CLI pagination; interleaved CSV limits; active/abandoned query cleanup; validation during concurrent GC; and publication between GC transactions. Ten of these new regression executions were demonstrated failing against the pre-change implementation based on `39d3a8d`: six initial numeric/CSV/reader/history cases, one validator/GC schedule, two invalidation cases and one contract-alias case. The final suite retains the assertions rather than weakening them to pass.

The project source/test/lock digest is `460e8c57895390f5fa61366bf361582abe5129dd1691ea09424eba51d5d336e9`, using the scope declared by `pp_quarry.evidence.provenance`. The final checks and [focused 50,000-original exercise](../artifacts/deep-correctness-2026-10-20.json) share that source identity; the report preserves its actual root/lock hashes and dirty flag. These are working-tree checks, not an immutable release or a hosted CI result. Documentation/artifact edits are outside the declared source hash scope.

The focused exercise independently verifies facts and daily totals after seven publications, two namespaces sharing key strings, exact history/source cardinality, pinned results, retention/restart and historical conflicts. It passed with 69,647 accepted identities and 45,464 live rows, one bucket rewritten for a targeted day move, and zero bytes written for obsolete/replayed and policy-only phases. Its executable workload, exact command, raw report and single-run limitations are documented in [benchmarks](BENCHMARKS.md#focused-incremental-correctness-exercise-2026-10-20).

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

The complete current checks were run from the repository root with `PORTFOLIO_PYTHON=3.14.8 python scripts/portfolio.py check quarry`, then `PORTFOLIO_PYTHON=3.13.16 UV_PROJECT_ENVIRONMENT="$PWD/.local/venvs/quarry-3.13.16" python scripts/portfolio.py check quarry`. Managed instances with a read-only home use UV_CACHE_DIR=/workspace/.cache/uv and UV_PYTHON_INSTALL_DIR=/workspace/.python; set UV_LINK_MODE=copy when needed across mounts. A separate full 3.14.8 test run also passed with ResourceWarning promoted to an error.

## Historical evidence

These measurements retain their original source revisions; they do not measure the current implementation's additional integrity checks.

| Record | Source and result |
| --- | --- |
| [Original 3.13 verification](../../../docs/evidence/final/python313/quarry-3.13.16.json) and [3.14 verification](../../../docs/evidence/final/python314/quarry-3.14.8.json) | Clean commit `7114e39c7e9e8af177e84fe8cd990fe5a09bde63`: 37 tests per interpreter, format/lint/types, packaging, installed-wheel demo and CI workload. |
| [Standard measured report](../../../docs/evidence/final/standard/quarry-3.14.8-benchmark-benchmark.json) and [verification wrapper](../../../docs/evidence/final/standard/quarry-3.14.8.json) | Clean commit `59443e2bcdfc6a1dd81f8334c108474eef2d3030`: five million originals, 500,000 corrections, 100,000 deletes and 100 schema additions; independent rebuild and forced Parquet rebuild agree. |
| [Correctness review](../../../docs/REVIEW.md) | Subsequent 51-test suites on both interpreters cover safe snapshot opening, manifest containment and wildcard rejection, nullable JSON projection, finite numeric range and SQL name collisions. |
| [Python 3.14 development workload](../artifacts/ci-development.json) and [3.13 development workload](../artifacts/ci-313-development.json) | Earlier dirty-checkout records retain source/lock hashes, warmup parameters, repetitions and their actual dirty flags. They are not committed-source acceptance records. |
| Integrity/input-validation maintenance | Source/test/lock digest `0f327d83420bdba3572a216dfdfb3344b15b75b5a1ea296f6bbd997e0beae47d`: 93 tests per interpreter, format/lint/types for 20 modules, packaging and installed-wheel demo. This precedes the execution-boundary changes above. |

The standard run produced 4,900,100 live rows and 5,600,100 historical identities. Its full interpretation, cache conditions, hashes and unfavorable incremental/full-rebuild comparison are in [benchmarks](BENCHMARKS.md). The five-million-event standard benchmark was not rerun for these changes; the focused 50,000-original exercise has a separate correctness scope.

## Boundaries

One local writer owns publication; concurrent readers register persistent pins. Exact historical identities grow indefinitely. Stale pins require offline diagnosis and are never expired automatically. Engine memory settings are not process-RSS limits. Checksums detect content drift relative to a trusted catalog; they do not authenticate an attacker-controlled dataset. Distributed writers, object storage and full Iceberg/Delta compatibility are outside the supported contract.

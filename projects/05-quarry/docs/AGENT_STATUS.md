# A05 Quarry — stable handoff

Status: verifying, implementation writes paused for coordinator review/commit. All local acceptance IDs QU-01–08 pass. Required standard 5,000,000-row/128-bucket workload and final immutable committed-source verification remain coordinator-owned; no unrun standard success is claimed.

Default Python 3.14.8; supported/tested CPython 3.13.16 and 3.14.8. Linux is required for directory-fsync/process-fault suites and Unix RSS accounting. Runtime lock: PyArrow 26.0.0, DuckDB 1.5.6. Source snapshot SHA-256: `c2d532eb22b507168c771d915203437b50cc985e7f4fdf0db9397078a1e15af3` (project scope, dirty working tree at source commit 6e857f4f226e30b7d25a261902fe1bde2e78a45f). Exact source/lock/root provenance is in artifacts/ci-development.json; docs/status/artifacts are excluded from self-referential source digests.

Verified commands (exit 0):

- `uv sync --locked --python 3.13.16`; separate environment `uv sync --locked --python 3.14.8`.
- `uv run --locked --python 3.13.16 ruff format --check .` and `ruff check .`: pass.
- `uv run --locked --python 3.13.16 mypy src`: strict, 19 source modules, no errors.
- `uv run --locked --python 3.13.16 pytest --cov=pp_quarry --cov-branch -q -W error::ResourceWarning`: 37 passed, 7.44s; own-core combined statement/branch coverage 97% (630 statements, 240 branches; CLI/provenance/workload wrappers excluded).
- Separate 3.14.8 environment, `pytest -q -W error::ResourceWarning`: 37 passed, 6.72s.
- `uv build`: sdist and wheel built successfully.
- Fresh noneditable wheel installed with exact pinned runtime dependencies into /tmp/quarry-wheel-check; isolated `python -I -m pp_quarry.cli demo` from /tmp passed all independent-rebuild, one-bucket and pinned-snapshot checks. Installed-package provenance honestly reports no checkout/lockfile instead of inventing Git metadata.
- Python 3.14.8 CI benchmark: 20,000 originals/eight buckets, 2,000 corrections, 400 deletes, 100 nullable schema updates; one warmup plus five measured runs, all independent rebuild and forced full-Parquet rebuild comparisons passed. Median 18,088.47 original rows/s; peak RSS 131,145,728 bytes. Full report: artifacts/ci-development.json; owned bulk state: /tmp/quarry-ci-stable.

Public SDK: Lakehouse(root,Config), ingest(source,Contract), plan, build(force=True), snapshots, manifest, validate, lineage; Snapshot(root,id).rows(node); recover(lake,retain=N). Public CLI implements demo/benchmark/clean-demo, ingest/plan/build/validate/query/snapshots/lineage/recover/explain/gc. Integration accepts arbitrary initial schemas and preserves exact canonical payload JSON. Nullable extensions become typed payload__FIELD Parquet columns. The supported named DAG is normalized→facts→daily; empty/incomplete/differently wired output configurations fail before staging.

Original core owns authoritative all-historical exact event fingerprints, highest-version/tombstone reduction, canonical stable buckets, semantic partition fingerprints, cached per-bucket quality summaries, immutable checksummed Parquet, transactional manifest/lineage/checkpoint publication, pinned readers and conservative pin-aware GC. Historical identities survive retention/full rebuild/restart. Both process-death and independent property/rebuild models exercise the persistence boundary.

Review corrections: total CSV header/physical-record byte bounds now precede parsing; multiline CSV is explicitly unsupported. Parsed-byte hashes defeat mutate-and-restore source rewrites, EOF and immediate prepublication hashes detect ordinary concurrent mutation. Regressions prove no checkpoint/identity/snapshot advance on mutation. Pinned query engines inherit publication memory/thread limits and owned spill path. GC commits catalog retention before unlinking orphan files, avoiding rollback to a manifest with removed files. Tightening dataset quality on a repeated source still validates current state.

Standard harness is implemented with measured 5,000,000 originals/128 buckets, separate 500,000 late corrections/100,000 deletes/100 schema additions. Warmup is intentionally bounded to 20,000 originals/eight buckets; report warmup_parameters distinguishes it. One costly measured standard run is documented. Required full phases have not been reduced. Reports retain source hashes and manifest summaries; bulky state may be removed only through explicitly owned output handling after independent correctness checks.

Known limits: one writer, trusted local filesystem, growing exact history registry, no automatic stale-reader expiry, no full Iceberg/Delta/cloud-object-store contract. Engine/batch memory settings do not cap total process RSS. No shared-file blocker; coordinator controls Git and final verification. Next action belongs to coordinator: commit this stable source, export it immutably, run full required matrix/integrations and serial standard benchmark, record final committed evidence.

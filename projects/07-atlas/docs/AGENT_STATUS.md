# Atlas checkpoint

Status: verifying. Phase P5/P6: stable implementation handed to coordinator for
independent review, integration and immutable committed measurements.

## Completed local gates

- AT-01–AT-07: hand-calculated BM25, bounded Unicode/phrase/snippet behavior,
  concurrent generation/merge publication, revision/delete exclusion, tenant/ACL
  isolation, hidden-statistics invariance, next-request revocation, corrupted
  segments and malformed input rejection. See docs/ACCEPTANCE.md for exact tests.
- AT-08 implementation: 250 original technical documents and 60 independently
  authored graded query intents; frozen 30 development / 30 heldout split;
  actual baseline/phrase evaluation with every per-query ranking failure reported.
  Independent coordinator semantic audit remains the review prerequisite.
- CPython 3.13.16: format/lint/strict mypy pass; pytest **40 passed**, 97% whole-package
  branch-inclusive coverage, measured via `uv run --locked --python 3.13.16 pytest
  -q --cov=pp_atlas --cov-branch --cov-report=term-missing`.
- CPython 3.14.8: same quality checks pass; pytest **40 passed**. Default interpreter
  is now 3.14.8; 3.13 remains required/supported.
- `uv build`: source distribution and wheel both built successfully.
- Clean wheel CPython 3.14.8 environment `/tmp/atlas-wheel314`: locked runtime
  dependencies installed with required hashes; package imported from site-packages
  with `-I` outside source; actual demo + cleanup and CI benchmark + cleanup pass.
  Installed distributions honestly report unavailable checkout provenance as null.
- Development CI benchmark: 200 documents / 30 queries / five repetitions; all
  correctness and source-stability checks pass. Actual dirty-source artifacts:
  `artifacts/development-ci.json`, `artifacts/development-quality.json`.

Latest coverage run: 40 passed in 12.26s; engine 97%, tokenizer/query/BM25 100%.
One upstream Starlette deprecation warning recommends httpx2 for TestClient;
this is not suppressed and no required test skips/xfails exist.

## Measured development evidence

Source commit at execution: a76e5a376333b501ccc91496f99e3c82a7c09f1b; dirty=true.
The artifact records exact source and root-contract hashes. It is a historical
working snapshot, not final committed-release evidence. CI indexing 0.2303s;
cold query 17.41ms; warm p50 0.598ms / p95 6.704ms; peak RSS 37.09MB. Heldout
nDCG@10 0.69740→0.95150; MRR 0.56111→0.98333; pooled Recall@10 1.0.
Fifty queries retain graded-order imperfections; they are preserved in reports.

## Remaining required work owned by coordinator

1. Complete independent semantic judgment audit and implementation review.
2. Run code-search integration through stable public API.
3. Commit stable Atlas source, then run final checks/evaluation from an immutable
   clean clone. Standard benchmark requires exclusive serialized lease:
   `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run --locked
   python -m pp_atlas.cli benchmark --profile standard --output ABS --seed 1729`.
   Workload is 100,000 documents × 400 tokens, 2,000 queries × five repetitions.
   Worker has not run or invented this required standard result.
4. Update root matrix to default 3.14.8, required 3.13.16 and 3.14.8; services none;
   Linux tested for ingestion/fsync durability. Coordinator owns Git and root files.

No external credential/service blocker. No worker Git mutations. No writes are
needed beyond review corrections and updating this checkpoint. Public API:
Engine, Document, Principal; upsert/upsert_many/delete/set_acl/set_groups;
search/fetch/export/authorized_ids/merge/inspect. CLI demo, benchmark, clean-demo,
ingest, search, fetch, delete, acl, groups, inspect, merge, evaluate, serve.

Known boundaries: trusted local bearer bindings; body-only lexical indexing;
conjunctive grammar; current-generation postings materialized in memory; old
segments/orphans retained; privileged filesystem tampering can defeat stat-based
cache invalidation; Linux fsync tested, not arbitrary power-loss hardware.

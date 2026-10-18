# Atlas checkpoint

## Code review addendum — 2026-10-18

The current working-tree review fixes three confirmed boundary defects:

- Authenticated readers could obtain tenant-wide document, term, segment and revision
  counts from `/ready`, including hidden documents. Readiness still validates the index
  and reports corruption, but now returns only `{"status":"ready"}`. Administrative
  corpus inspection remains available through the trusted CLI and Python API.
- Non-ASCII bearer credentials raised an exception during string comparison and returned
  HTTP 500. Constant-time byte comparison now produces the normal HTTP 401 response.
- NaN and positive infinity were accepted as BM25 `k1` values. Both engine configuration
  and the scalar scorer now reject non-finite values before scoring.

Five regression cases cover readiness before/after a hidden insertion and corruption,
non-ASCII bearer input, and non-finite ranking parameters. Four cases failed against
the previous implementation before the fixes. Full suites pass on Python 3.13.16
(**45 passed in 2.59 s**) and 3.14.8 (**45 passed in 3.15 s**), including concurrent
publication, revocation, process failure, CLI demonstrations and quality evaluation.
Ruff formatting/lint and strict mypy pass on both interpreters; wheel and sdist build
pass. Commands: `python -m pytest -q --tb=short`, `ruff format --check .`,
`ruff check .`, `mypy src`, and
`uv build --out-dir /workspace/python-projects/.local/review-builds/atlas`.

One upstream Starlette/httpx test-client deprecation warning remains. Heavy benchmarks
and the cross-project code-search integration were not rerun. The historical evidence
below describes its original revisions and does not verify these working-tree changes.
No dependency/lockfile or shared tracked files changed. Writes stop at coordinator handoff.

## Previous accepted verification

Status: complete for project acceptance, independent review, integration and
required local workloads. The coordinator owns final repository commits, push
and remote CI reporting. Project writes are paused after this documentation handoff.

## Verified gates

- **AT-01–AT-07:** hand-calculated BM25; bounded Unicode, phrase and snippet
  behavior; concurrent generation and merge publication; revision/delete exclusion;
  tenant and ACL isolation; hidden-statistics invariance; next-request revocation;
  corrupted-segment and malformed-input rejection. See [acceptance](ACCEPTANCE.md).
- **AT-08:** 250 original documents and 60 pre-authored graded query intents;
  frozen 30 development / 30 heldout split; actual baseline and phrase evaluations
  with every per-query failure retained. The independent coordinator semantic
  [judgment audit](../../../docs/evidence/atlas-judgment-review.md) is complete.
- CPython **3.13.16 and 3.14.8:** both compatibility runs pass **40 tests**, with
  formatting, lint, strict mypy, build and installed-wheel checks passing.
  Default is 3.14.8; 3.13 remains supported. Local whole-package branch-inclusive
  coverage is **97%**; tokenizer, query parser and BM25 coverage is 100%.
- Clean installed-wheel demo, cleanup and CI benchmark pass outside source, with
  locked runtime dependencies verified by hashes. Installed distributions report
  unavailable checkout provenance as null.
- Code-search integration passes through real PyTrace JSON findings and Atlas
  public interfaces: obsolete deletion, hidden-update score invariance, merge,
  cross-tenant direct fetch/export, caches and revocation are exercised.
- Final standard workload passes from clean immutable commit
  `59443e2bcdfc6a1dd81f8334c108474eef2d3030`: 100,000 documents, 400 tokens each,
  40,000,000 tokens total and 2,000 queries over five measured repetitions.
  Authorization, expected visible count and source-stability checks are all true.

One upstream Starlette TestClient deprecation warning remains visible. No required
test skips or xfails conceal missing behavior or services. No external credentials
or database server are needed, and the worker performed no Git mutations.

## Final standard evidence

- [Measured benchmark](../../../docs/evidence/final/standard/atlas-3.14.8-benchmark-benchmark.json)
- [Command and immutable-source verification](../../../docs/evidence/final/standard/atlas-3.14.8.json)

The benchmark records source_dirty=false, exact source and root-contract input
lists, and lock digest
`afadf806fdbb623044aa563e65234d12d3a49b57e907308cab46198ecad717f8`.
Indexing took **543.2294 s** at **184.084 documents/s**. Cold loading/query took
**36.1966 s**. Warm p50/p95/p99 were **21.6806 / 57.1996 / 83.9298 ms**, with
**32.8779 queries/s**. Disk size was **155,283,633 bytes** and peak RSS
**2,778,984,448 bytes**. Authorization-plus-search median was **398.615 ms**;
authorized-snapshot median was **59.3983 ms**. Visibility scans O(N) catalog
entries before cache lookup and remains a measured scaling limitation.

## Historical captures and quality limits

`artifacts/development-ci.json` and `artifacts/development-quality.json` preserve
their actual dirty working-snapshot provenance at source commit
`a76e5a376333b501ccc91496f99e3c82a7c09f1b`. They are historical captures, not
claims to test their later artifact commit. Heldout nDCG@10 improves
0.69740 → 0.95150 and MRR 0.56111 → 0.98333; pooled Recall@10 is 1.0.
Fifty queries retain graded-order imperfections. The authored technical templates
and pooled judgments do not establish broad natural-query relevance.

Public API: Engine, Document, Principal; upsert/upsert_many/delete/set_acl/set_groups;
search/fetch/export/authorized_ids/merge/inspect. CLI: demo, benchmark, clean-demo,
ingest, search, fetch, delete, acl, groups, inspect, merge, evaluate and serve.

Known boundaries: trusted local bearer bindings, body-only conjunctive lexical
retrieval, materialized current-generation postings, retained old segments and
orphans, stat-based cache invalidation on a trusted filesystem, and Linux fsync
failure tests rather than arbitrary power-loss hardware guarantees. No required
Atlas implementation, review, integration or workload gate remains pending.

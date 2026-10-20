# Verification records

## Core query and publication verification — 2026-10-20

The current implementation separates compatibility-checked catalog transactions
from file preparation, streams ranking scores without retaining every candidate's
explanation, anchors phrases on the rarest positional list, and uses a result-cache
hit only after pinning the current ACL/data revisions and checking file signatures.
Tokenizer v2 groups normalization-safe spans and includes the Unicode database in
its persisted identity. The installed maintenance module provides the tested offline
text rebuild; [architecture](ARCHITECTURE.md), [decisions](DECISIONS.md) and the
[runbook](OPERATIONS.md) describe state sequences, failure outcomes and upgrade limits.

**Pre-fix reproductions.** Seventeen selected cases were rerun with source extracted
from baseline `39d3a8d` using `git archive`; the subprocess import path was verified
to select that source rather than the editable package. All 17 failed as expected:
Japanese NFKC-equivalent phrase misses; warmed reads/writes accepting an unsupported
catalog; an incompatible publisher between segment preparation and commit; a repeated
ACL scan before a result-cache hit; copying 100,000 common phrase positions despite
one rare anchor; and HTTP 500 for an ordinary stale-merge conflict. Their case names
and exact baseline commit are in the [reproduction record](../artifacts/core-baseline-reproductions.json).
These intentional failures are separate from the passing acceptance suite.

**Additional invariants.** The new exhaustive oracle compares positional matching
with direct sliding windows and BM25 scores/explanations with direct mathematics
across tiny corpora, principals, metadata filters and pages. A whole-string
NFKC/casefold oracle checks normalization boundaries and source span bounds. Real
SQLite WAL schedules pause between header and document reads, and between merge
preparation and a group revocation. A real SIGKILL after catalog commit establishes
that the write survives a lost acknowledgment. Golden v1 data includes obsolete,
deleted and private revisions plus group memberships; the actual module CLI rebuilds
two tenants without changing source bytes. A UCD16 fixture runs under both supported
interpreters. These are new assertions of guarantees, not claims that every scenario
was broken in the baseline.

The [runtime exercise](../artifacts/runtime-rebuild.json) also creates real state
under 3.14.8, refuses its direct read under 3.13.16, rebuilds it there and rebuilds
back under 3.14.8. Text, ACLs and groups survive; newly assigned characters are
retokenized according to the destination's Unicode database. Indexes are not
silently shared across different Unicode identities.

**Final checks.** Root dispatcher checks passed on CPython **3.14.8: 92 tests in
3.29 s** and **3.13.16: 92 tests in 3.12 s**, with no failures, errors, skips or
expected failures. Both also passed Ruff formatting/lint, strict mypy over 20 source
files, fresh sdist/wheel builds and runtime-only installed-wheel demos outside source.
The demo's advertised phrase now matches the phrase actually scored and highlighted.
One upstream Starlette/httpx deprecation remains. Commands from the repository root:

```sh
python scripts/portfolio.py check atlas
PORTFOLIO_PYTHON=3.13 python scripts/portfolio.py check atlas
```

The compatibility environment is separate at `.local/venvs/atlas-3.13.16`; checks
ran sequentially. The optional real Chromium regression harness passed functional
checks and all four desktop/mobile axe states with no WCAG 2 A/AA or WCAG 2.1 A/AA
violations. Browser command from this directory, with externally installed tools:

```sh
NODE_PATH=/workspace/.tools/ui/node_modules uv run --locked python tests/browser/check_browser.py
```

**Bounded resource evidence.** The [before](../artifacts/query-memory-before.json)
and [after](../artifacts/query-memory-after.json) diagnostic uses 1,000/5,000 documents,
eight matching terms and top ten. At 5,000 documents uncached peak Python allocation
was 3,499,751 -> 1,708,843 bytes; the identical cached query was 659,764 -> 15,883
bytes with zero visibility scans. Every total, selected ID, explanation cardinality
and cached value check passed. A deterministic phrase probe reduces common-list
reads from 100,000 to fewer than 32. These are single allocation/work samples with
tracemalloc overhead, excluding index load/RSS/concurrency; they establish no new
standard-workload throughput or capacity claim.

Current source-scope digest for the corrected allocation and runtime exercises is
`e29c34a5e8717121bf2ebd39a8eb8a124e45831f3633c61026911959e721b98b`;
the reports retain their actual dirty checkout, lock and root-input provenance.
Historical standard/relevance evidence below is unchanged. Material boundaries remain
materialized current-generation indexes, per-Engine tenant cache lifetime, O(N)
visibility on cache misses, full-match facets, O(segment count) stat checks, retained
old/orphan files, trusted filesystem owners and no request-id deduplication. V1 or
cross-UCD index upgrades require an offline rebuild and a coordinated process restart.


## HTTP, security and browser review — 2026-10-20

This review makes export pagination bound the number of constructed document records,
while computing the authorized total from the same catalog snapshot. It also corrects
HTTP routing for encoded slash-containing document IDs, rejects nonboolean administrator
bindings, and validates numeric pagination types before executing a search or export.
A typed ASGI body limiter now rejects oversized chunked JSON before FastAPI parsing.
All HTTP responses disable caching, framing and content-type sniffing; the browser
workspace loads only local assets under a restrictive Content Security Policy.

The previous HTTP adapter at source `da094934b37a80e03b644ec4be8aa8e697da4c49`
was exercised independently: `admin="false"` incorrectly granted administration, an
encoded slash document ID returned 404 despite existing, and oversized chunked JSON
returned 400 after framework parsing instead of the body-limit 413. Regressions now
verify these boundaries along with page-limited export projection and revocation.

The view now includes explicit input labels, keyboard focus, query guidance, authorized
counts/facets, pagination, document reading, loading/error/empty states, connection
clearing and stale-request cancellation. Credentials have no form field name and cannot
fall back to URL submission when scripts fail. Document HTML is inert text. Browser
checks cover actual Chromium HTTP behavior and automated axe checks at desktop/mobile
widths; the optional reproducible harness is in `tests/browser/` and documented in
[HTTP_API.md](HTTP_API.md). No WCAG 2 A/AA or WCAG 2.1 A/AA violations were found in
initial, results, document-dialog and mobile-results states. This is an automated check,
not a complete accessibility certification.

The full Python suite passed **64 tests on CPython 3.14.8** (2.35 seconds) and
**64 on CPython 3.13.16** (3.22 seconds), with no skips or expected failures. Ruff
formatting/lint and strict mypy over 19 source files passed. Both interpreters built
wheel and source distributions, then passed runtime-only installed-wheel demos and
owned cleanup outside source. The wheel contains the local HTML, stylesheet and script.
One upstream Starlette/httpx test-client deprecation
warning remains. Historical performance/relevance records below keep their original
source identity; these checks do not claim new throughput measurements or hosted CI.

Commands from this directory: `uv sync --locked --python VERSION`, then locked
`ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, and `uv build`.
The 3.13 environment is separate at `.local/venvs/atlas-3.13.16` under the repository
root; compatibility checks and builds run sequentially. Browser checks use the optional
`uv run --locked python tests/browser/check_browser.py` harness with external Node tools.


## Code review addendum — 2026-10-18

This earlier review fixed three confirmed boundary defects:

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
No dependency or lockfile changes were required for that review.

## Previous accepted verification

The following records describe their source revisions. Hosted CI observations are
separate from local acceptance, integration and workload verification.

## Verified gates

- **AT-01–AT-07:** hand-calculated BM25; bounded Unicode, phrase and snippet
  behavior; concurrent generation and merge publication; revision/delete exclusion;
  tenant and ACL isolation; hidden-statistics invariance; next-request revocation;
  corrupted-segment and malformed-input rejection. See [acceptance](ACCEPTANCE.md).
- **AT-08:** 250 original documents and 60 pre-authored graded query intents;
  frozen 30 development / 30 heldout split; actual baseline and phrase evaluations
  with every per-query failure retained. The independent semantic
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
or database server are needed, and these checks did not require remote access.

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

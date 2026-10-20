# Verification record

Strata supports standard CPython 3.13.16 and 3.14.8 on Linux with a local POSIX
filesystem. This page distinguishes checks for the current revision from
historical performance and durability evidence. Files under `artifacts/` and
repository `docs/evidence/` retain the source revisions and input hashes recorded
when they ran.

## Recovery review — October 20, 2026

The recovery audit identified a file-loss case: normal open created a missing
WAL even when a manifest already existed. If committed records had not yet been
flushed to tables, the reopened database silently omitted those records. Open now
requires the WAL for every initialized database. New database creation syncs an
empty WAL before publishing its initial manifest, and a failed initialization
can resume only with an empty log and no table files.

Recovery also rejects gaps between complete WAL frames and between the manifest
checkpoint and the first replayed transaction. A missing complete prefix or
interior transaction can no longer masquerade as valid sparse commit sequences.
A WAL must be a regular file; special files are refused and their descriptors
are released. Eight regression cases cover these boundaries, including unchanged
files after rejection and a successful retry after failed initial publication.

The review workspace passed the following commands sequentially with
`PORTFOLIO_PYTHON=3.14.8`, then with `PORTFOLIO_PYTHON=3.13.16` and a separate
`UV_PROJECT_ENVIRONMENT`:

```sh
python scripts/portfolio.py setup strata
python scripts/portfolio.py check strata
```

Each interpreter passed formatting, lint, strict typing, **110 tests**, source
and wheel builds, and a runtime-only installed-wheel demo outside the checkout.
No tests were skipped or marked as expected failures. Against the original
`api.py` and WAL implementation at `da094934b37a80e03b644ec4be8aa8e697da4c49`,
the eight new cases produced **seven failures and one pass**; the pass checks
preservation of a nonempty orphan WAL, which the earlier implementation also
refused. The corrected implementation passed all eight cases.

No full standard benchmark or 500,000-operation extended run is claimed for this
revision. Format version remains 1; no dependency or lockfile changed.

## Earlier correctness review — October 18, 2026

The earlier review added 23 cases for descriptor ownership, cleanup after
errors, canonical manifest fields, symlink rejection in CLI outputs, and
benchmark isolation. Its complete suite passed **102 tests on each supported
interpreter**, along with formatting, lint, strict typing, builds, and public CLI
checks. The CI workload passed at source-content SHA-256
`190e1790dce666c5fdd566f13f3a8285b9fe5530e946e16d2f8bf65332b8d79a`.
Those counts describe that revision, before the current recovery changes.

## Historical accepted workloads

| Evidence | Source and scope |
| --- | --- |
| [Python 3.13 compatibility](../../../docs/evidence/final/python313/strata-3.13.16.json) and [Python 3.14 compatibility](../../../docs/evidence/final/python314/strata-3.14.8.json) | 79-test suites, locked installs, lint/types, builds, installed-wheel demos and CI workloads at `ec1d0106df086a48923016c33199cfbda0aebbc0`. |
| [Extended stateful results](../../../docs/evidence/final/strata-extended/strata-extended.json) and [execution wrapper](../../../docs/evidence/final/strata-extended/strata-3.14.8.json) | 100 seeds × 5,000 operations, independent dictionary/snapshot oracles, conflicts, aborts, compaction and recovery at `9218b77769cef807700d67f8a0c2b97512b9cc0e`. |
| [Standard measurements](../../../docs/evidence/final/standard/strata-3.14.8-benchmark-benchmark.json), [demo](../../../docs/evidence/final/standard/strata-3.14.8-demo-demo.json), and [execution wrapper](../../../docs/evidence/final/standard/strata-3.14.8.json) | 250,000 initial records, 200,000 mixed operations and 50,000 churn operations at `ec1d0106df086a48923016c33199cfbda0aebbc0`. |

The [reporter impact analysis](../../../docs/evidence/final/strata-extended/reporter-impact-analysis.json)
shows that the reporting-string correction following the extended run did not
change storage algorithms or the extended entry point. It does not establish
that the current recovery implementation has repeated that full workload.

The [counter-scope erratum](../../../docs/evidence/final/attempts/strata-counter-scope/coordinator-erratum.json)
and [superseded standard result](../../../docs/evidence/final/attempts/strata-counter-scope/standard/strata-3.14.8-benchmark-benchmark.json)
retain the original measurement wording. Read-amplification counters sample the
first owner through compaction and exclude later validation/recovery reads.

Development captures remain in `artifacts/`: a public demo, CI benchmark,
verification summary, and descriptor regression. An initial extended attempt
completed 11 seeds before termination; `extended-preliminary.json` labels it
partial. It is superseded by the complete accepted run above. The historical
79-test storage-core coverage was 96.82% statements and 91.43% branches, with
explicit scope in its recorded verification; it is not current coverage.

## Limits

Tests use real owning processes, local files, and injected I/O failures. They do
not prove behavior under every power loss, controller failure, network filesystem,
or malicious concurrent filesystem mutation. CRCs detect corruption, not hostile
authorship; backup hashes provide integrity, not encryption or authentication.
Truncating or removing a complete final WAL frame may be indistinguishable from
an earlier valid log state because no independent commit-end marker is retained.
Long snapshots, full compaction, materialized results, and process-lifetime
conflict heads impose the operating limits described in the runbook. No external
service or credential is required.

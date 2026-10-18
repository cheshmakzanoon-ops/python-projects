# Status: complete — accepted local verification, writers paused

Owner A02; edits confined to `projects/02-strata`. No Git mutations performed.

Implemented: original deterministic skip-list; bounded binary record/WAL codecs;
CRC transaction batches; immutable CRC blocks with sparse indexes, persistent
BLAKE2b Bloom filters and bounded LRU; snapshot/private-overlay transactions;
first-committer-wins including insert/delete; full compaction with pinned
versions, safe tombstone removal and durable manifest publication; process owner
locks; uncertain-I/O poisoned writer; consistent historical backup/restore;
operator CLI, two-process crash demo, CI/standard workload generators.

Historical development verification (retained for provenance):

- CPython 3.13.16: final 79-test full suite passed, 3.77 seconds.
- CPython 3.14.8: final 79-test full suite passed, 4.14 seconds. Default selected
  as 3.14.8. Storage-core coverage: 96.82% statements, 91.43% branches, 95.49%
  combined, over 850 statements / 280 branches, with no excluded core lines.
- `ruff format --check .`, `ruff check .`, `mypy src`: passed on current source.
- ST-01–08 default scenarios pass, including actual child `os._exit` boundaries,
  ENOSPC / short / zero write / failed-sync injection, poisoned-writer recovery,
  real second-process lock rejection, snapshot/write-skew/conflict histories,
  historical backup and restore, and public CLI subprocess demonstration.
- Actual cleanup-exception regression now checks descriptor count returns to
  baseline after a poisoned owner closes. A reconstructed former ordering in
  a separately built wheel reproduces two leaked descriptors (14 vs 12);
  `artifacts/descriptor-regression-before.txt` is the intentional failure output.
- `uv build`: sdist and wheel passed. Installed the wheel into a fresh venv,
  changed working directory to `/tmp`, ran the complete public CLI demo, and
  verified historical backup/restore plus child crash recovery successfully.
- Public development demo and CI benchmark passed; artifacts are
  `artifacts/demo.json`, `timeline.txt`, `benchmark-ci.json` and
  `verification-development.json`. They identify actual dirty-source snapshots,
  not an untested final release commit.
- Extended harness parallel smoke: two seeds × 100 operations at `--jobs 2`,
  plus a resumed one-seed partial checkpoint, both passed. The final 79-test matrices include both the bounded harness and a final fix
  that syncs every newly created parent directory entry before durable commits.
- Independent A01 review: reproduced and fixed a WAL-constructor descriptor leak
  on directory-sync failure, and restore accepting unsupported/malformed BACKUP
  schemas. Two constructor-context regressions and sixteen invalid-schema cases
  pass; restore rejects invalid metadata before opening the source or creating a
  destination. A separate valid-schema wrong-content-hash test still checks
  integrity. A01's independent snapshot/corruption/poison/manifest-loss script
  passes unchanged. The final 79-test matrices include these fixes.

The initial dirty-source serial extended run completed 11 seeds × 5,000
operations (55,000 operations), then was intentionally terminated with exit 143
at the coordinator's request. This is preliminary evidence, not the full gate;
`artifacts/extended-preliminary.json` records the distinction. No Strata worker
process remains running. Profiling one 5,000-operation seed measured 29.684 s,
with 15.650 s in fsync and 9.315 s in scans on the shared host.

Accepted committed-source closure:

- All ST-01–08 acceptance scenarios and the 79-test suite passed on both required
  interpreters. The immutable compatibility runs also passed formatting, lint,
  strict typing, sdist/wheel build, runtime-only installed-wheel demos, and CI
  benchmarks after the reporting-scope correction at source
  `ec1d0106df086a48923016c33199cfbda0aebbc0`:
  [CPython 3.13.16 wrapper](../../../docs/evidence/final/python313/strata-3.13.16.json)
  and [CPython 3.14.8 wrapper](../../../docs/evidence/final/python314/strata-3.14.8.json).
  The default remains 3.14.8; 3.13.16 remains required and verified.
- The complete extended suite passed **100 seeds × 5,000 operations = 500,000
  operations**, with two independent owning processes, dictionary/snapshot
  oracles, conflict and abort histories, compaction and recovery checks, at
  source `9218b77769cef807700d67f8a0c2b97512b9cc0e`:
  [raw per-seed results](../../../docs/evidence/final/strata-extended/strata-extended.json)
  and [clean/unchanged-source wrapper](../../../docs/evidence/final/strata-extended/strata-3.14.8.json).
  This accepted full run supersedes the intentionally stopped historical run.
  It was not executed again after the report-string correction. The
  [retained impact analysis](../../../docs/evidence/final/strata-extended/reporter-impact-analysis.json)
  proves that storage algorithms, tests, dependencies and extended entry point
  are unchanged, and the sole source change is an AST string constant in the
  benchmark reporter, which the extended runner does not execute. Its original
  revision and whole-project digest remain unchanged in the evidence.
- The standard workload and public demo passed at source
  `ec1d0106df086a48923016c33199cfbda0aebbc0`: **250,000 initial records,
  200,000 mixed operations, and 50,000 hot-set churn operations**. See the
  [raw standard measurements](../../../docs/evidence/final/standard/strata-3.14.8-benchmark-benchmark.json),
  [demo report](../../../docs/evidence/final/standard/strata-3.14.8-demo-demo.json),
  and [clean/unchanged-source wrapper](../../../docs/evidence/final/standard/strata-3.14.8.json).
  [BENCHMARKS.md](BENCHMARKS.md) interprets the measured limits.
- The new compatibility and standard wrappers report clean and unchanged
  source with project digest
  `1cdc88c267fb33729306baf20f97761fa8774e191f657d961f5c1f2777840efd`.
  The earlier extended run retains its different whole-project digest; the
  impact analysis supports its unchanged-storage-core relevance, not a new
  extended execution or a claim that the whole-project digests match.
- The counter-scope [erratum](../../../docs/evidence/final/attempts/strata-counter-scope/coordinator-erratum.json)
  and [original standard report](../../../docs/evidence/final/attempts/strata-counter-scope/standard/strata-3.14.8-benchmark-benchmark.json)
  preserve the former wording and measurements at their actual source. Read
  amplification samples the first owner through compaction, excluding later
  validation and reopened recovery reads. The corrected full standard run and
  both compatibility runs above execute the corrected reporter. Development
  captures and superseded reports remain historical evidence.

No Strata implementation or local required validation gate remains pending.
Repository-wide Git synchronization and hosted CI reporting remain coordinator
responsibilities and are separate from these accepted local results.

No essential service/credential blocker exists. Required low-level durability
platform is Linux/local POSIX filesystem. Process termination and simulated
unsynced-rename outcomes are not a universal power-loss proof. Full compaction,
materialized scans/backups, per-key conflict-head memory and snapshot retention
are documented operating limits.

## Code review follow-up — October 18, 2026

The review found and fixed five classes of defect in the current working tree:

- WAL rotation closed its old descriptor before reopening the replacement. A
  failed reopen left a stale descriptor, and closing the owner then raised
  `EBADF`. Rotation now keeps the replacement's writable descriptor through
  publication and releases it on every failed synchronization/rename path.
- Owner construction and shutdown could stop at the first cleanup error,
  leaking tables and the process-owner lock. Cleanup now attempts every release,
  including when WAL/table close or explicit owner unlock fails. A failed lock
  acquisition also closes its descriptor. Errors still reach the caller.
- Manifest validation accepted boolean/float format identifiers and checkpoint
  sequences outside the persisted unsigned 64-bit format. These inputs now fail
  as corruption before WAL recovery.
- Reusing a marked CLI output directory could follow a report-file symlink.
  Output setup now rejects symlinks at every directly owned child before writes.
- The commit benchmark opened predictable child names directly in the output
  directory and subsequently removed them. A regression reproduced deletion of
  a preexisting database. Measurements now use a newly created private temporary
  directory and preserve existing caller files byte for byte.

Twenty-three regression cases were added. Before the corresponding fixes, the
initial resource/schema checks reproduced five failures, and the output/benchmark
checks reproduced ten failures, including the deleted preexisting database.

Current verification on the uncommitted review source:

- CPython 3.14.8: complete suite **102 passed**.
- CPython 3.13.16, in a separate environment: complete suite **102 passed**.
- Both interpreters: `ruff format --check .`, `ruff check .`, and `mypy src`
  passed. `uv build --python 3.14.8` built the sdist and wheel.
- The public CLI demo, crash subprocesses, snapshot/recovery model tests, and
  descriptor fault tests ran as part of the complete suites.
- The public CI benchmark passed on 3.14.8 with all dictionary, compaction,
  recovery, comparison-count, and unchanged-source checks. Local report:
  `/tmp/strata-review-ci-w1908sfo/benchmark.json`; source content SHA-256:
  `190e1790dce666c5fdd566f13f3a8285b9fe5530e946e16d2f8bf65332b8d79a`.

The historical 500,000-operation extended run and standard benchmark above were
not repeated for this review and retain their original revision scope. Current
validation makes no new full extended-run or power-loss claim. No dependency or
lockfile changed, and no external services or credentials were required.

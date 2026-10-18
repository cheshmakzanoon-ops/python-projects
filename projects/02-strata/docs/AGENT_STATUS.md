# Status: verifying — stable handoff, writers paused

Owner A02; edits confined to `projects/02-strata`. No Git mutations performed.

Implemented: original deterministic skip-list; bounded binary record/WAL codecs;
CRC transaction batches; immutable CRC blocks with sparse indexes, persistent
BLAKE2b Bloom filters and bounded LRU; snapshot/private-overlay transactions;
first-committer-wins including insert/delete; full compaction with pinned
versions, safe tombstone removal and durable manifest publication; process owner
locks; uncertain-I/O poisoned writer; consistent historical backup/restore;
operator CLI, two-process crash demo, CI/standard workload generators.

Verified local results:

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

Remaining required gates, now coordinator-owned:

1. Commit/review this stable source, run the complete 100 seeds × 5,000 operation
   suite from its immutable exported copy:
   `uv run --locked python benchmarks/extended_stateful.py --jobs 2 --output ABS/strata-extended.json`.
   Default is one process; two is the explicit resource cap. Atomic per-seed
   checkpoints support `--resume` only with matching source/interpreter/workload.
2. Run `benchmark --profile standard` under the exclusive resource lease from
   the immutable committed tree; the implementation generates all required
   250,000 initial rows, 200,000 mixed operations and a separate churn workload.
3. Final committed-tree matrix/packaging checks and independent coordinator
   review; publish accurate final provenance. No complete status is claimed yet.

No essential service/credential blocker exists. Required low-level durability
platform is Linux/local POSIX filesystem. Process termination and simulated
unsynced-rename outcomes are not a universal power-loss proof. Full compaction,
materialized scans/backups, per-key conflict-head memory and snapshot retention
are documented operating limits.

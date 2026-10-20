# Acceptance mapping

| ID | Independent scenario | Executable evidence |
| --- | --- | --- |
| ST-01 | Seeded writes/deletes/ranges, private overlays, historical snapshots compared with independent dictionary copies | `tests/property/test_model.py`; `benchmarks/extended_stateful.py` (100 × 5,000) |
| ST-02 | Real child termination before/after append, sync, publication; retain prior acknowledgements and whole-or-absent pending batch | `tests/acceptance/test_faults.py::test_st02_real_process_crash_atomic_batch`; public CLI demo |
| ST-03 | Every torn-tail truncation boundary, interior CRC, corrupt length hiding later frame, invalid sequence/type/size | `tests/unit/test_formats.py::test_wal_tail_and_interior_corruption`, `test_wal_invalid_header_and_sequence`, bounded codec tests |
| ST-04 | Old points/scans and detached iterators survive overwrite/delete/flush/full compaction | `tests/acceptance/test_snapshot_contract.py::test_st04_snapshot_and_iterator_survive_compaction`; Hypothesis snapshots |
| ST-05 | First-committer-wins and stale writer after an insert/delete cycle plus compaction | `test_st05_first_committer_wins_and_insert_delete`; extended conflicting-writer histories |
| ST-06 | Two doctors independently leave duty after reading each other; both distinct write sets commit | `test_st06_snapshot_isolation_allows_write_skew` |
| ST-07 | Real child termination at table create/sync, manifest replace/directory sync, obsolete cleanup; simulated unsynced rename survives/rolls back; deleted keys never return | `test_st07_real_process_compaction_crash_no_resurrection`, `test_st07_simulated_unsynced_manifest_rename_reordering` |
| ST-08 | ENOSPC mid-header, short writes, zero writes, failed fsync including constructor cleanup, bounded input, real second owner, historical backup/restore with schema validation before side effects, poisoned writer and sequence advance | fault/backup/limit tests and `tests/integration/test_cli.py` safety tests |

`tests/integration/test_threads.py` independently verifies that concurrent
snapshots never see half of a two-key batch during repeated automatic flush and
compaction. The default pytest run contains every named ST gate. The separately
invoked extended stateful runner supplies the explicitly required larger history
suite; it is not silently skipped by a pytest marker.

Quality commands are `ruff format --check .`, `ruff check .`, `mypy src`,
`pytest --cov --cov-branch`, and `uv build`, all run in the locked uv environment.
Coverage scope is the actual codec, WAL, memtable, SSTable, metadata I/O, error,
and transaction/recovery modules; demo, provenance, and benchmark adapters are
excluded explicitly. CLI behavior has real subprocess acceptance tests anyway.
See `VERIFICATION.md` for exact current results and `BENCHMARKS.md` for measured
artifacts. Both accepted [3.13.16](../../../docs/evidence/final/python313/strata-3.13.16.json)
and [3.14.8](../../../docs/evidence/final/python314/strata-3.14.8.json) compatibility
wrappers and the [full standard run](../../../docs/evidence/final/standard/strata-3.14.8.json)
now identify corrected-reporting source `ec1d0106df086a48923016c33199cfbda0aebbc0`.
The original [500,000-operation extended result](../../../docs/evidence/final/strata-extended/strata-extended.json)
retains source `9218b77769cef807700d67f8a0c2b97512b9cc0e`. Its
[reporter-impact analysis](../../../docs/evidence/final/strata-extended/reporter-impact-analysis.json)
proves unchanged storage algorithms/tests/entry point and only one changed
reporter string that the extended runner does not execute; no new extended
execution or equality of whole-project digests is claimed.

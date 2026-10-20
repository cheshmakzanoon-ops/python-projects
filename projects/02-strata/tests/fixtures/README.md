# Legacy storage fixture

`legacy-v1.json` contains exact file bytes, hex encoded, produced by Strata at
`39d3a8d4be3e8e2e7de85379790d68f5367d6825` using CPython 3.14.8. It is synthetic
compatibility data, not a newly serialized approximation of the old format.

The source database committed `apple=old-red, pear=green`, flushed, then committed
`apple=new-red, delete pear, plum=purple` without another flush. It therefore
contains a version-one SSTable plus an unflushed `STW1` transaction at sequence 2.
The old implementation also exported the sequence-2 view to the included backup.
Its separate `BACKUP` metadata, compacted table, empty WAL and manifest are kept
unchanged. The UUID table filenames are part of those recorded manifests.

`tests/integration/test_legacy_storage.py` materializes these bytes into temporary
directories and checks new-engine open, v2 continuation, pinned historical reads,
compaction, export and restore. It also restores the original backup and verifies
that its input files remain unchanged. Tests require no historical Git checkout.

# Acceptance mapping

Run `uv run --locked pytest --cov=pp_quarry --cov-branch`. Own-core coverage excludes CLI/report/workload wrappers, and includes contracts, events, planning, readers, transformations, catalog, files, lineage, queries and recovery. CLI/demo behavior is additionally exercised through public command functions.

| Gate | Independent evidence |
| --- | --- |
| QU-01 | `test_qu01_out_of_order_repeat_independent_rebuild`; Hypothesis `test_independent_highest_version_model` computes the winning histories without production reduction; demo/benchmark SQL rank complete rebuild reads every arrival independently. |
| QU-02 | `test_qu02_historical_conflict_survives_tombstone_gc_restart`; accepted obsolete versions remain in the exact registry through deletion, retention and restart. |
| QU-03 | `test_qu03_one_bucket_plan_reuse_and_moving_day`; checks paths/fingerprints for unchanged nodes, moving a day and deleting its final row. Demo reports one rewritten bucket and 21 reused nodes. |
| QU-04 | `test_dag_cycles_unknown_nodes_invalid_config`; `test_qu04_strict_rollback_and_invalid_dag`; malformed/oversized source, missing fields and full-batch rollback integration tests. |
| QU-05 | `test_qu05_evolution_preserves_old_snapshots`; `test_csv_nullable_projection_and_public_commands` confirms new typed Parquet column is null for older records; schema migration diagnostics tested. |
| QU-06 | `test_real_process_death_at_publication` runs os._exit in a fresh interpreter at all three boundaries, checks manifest/checkpoint consistency and successfully retries. Exception injection tests also inspect orphan reconciliation. |
| QU-07 | `test_qu07_pin_during_publication_gc_retains_reader` reads an old pinned manifest after publication and GC, then proves its retention ends after closing the handle. |
| QU-08 | `test_qu08_bounded_batch_and_wrong_record_lineage`; max batch cardinality, memory configuration rejection, source offsets and source/column lineage; malformed-source and byte-limit tests, total CSV header/record bounds with explicit multiline rejection, exact consumed-byte source-hash checks under mutate-and-restore and during-build rewrites, and pinned-query memory/spill-setting regression tests. |

The CI benchmark is 20,000 original events, eight buckets, 10% correction and 2% delete batches plus a supported schema addition batch. Standard is five million originals/128 buckets with the same separate update/delete/evolution phases. Every measured run compares a streaming digest of current facts against an independent complete rebuild. Timing and source provenance live in the report, not fabricated acceptance constants.

A retained manifest is immutable by application convention on an owned trusted local filesystem. Checksum diagnostics detect external file corruption. The implementation does not claim malicious-user isolation, distributed commit, automatic historical identity compaction or automatic stale-reader recovery.

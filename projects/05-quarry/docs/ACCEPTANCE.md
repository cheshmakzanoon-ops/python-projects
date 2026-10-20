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

The CI benchmark is 20,000 original events, eight buckets, 10% correction and 2% delete batches plus a supported schema addition batch. Standard is five million originals/128 buckets with the same separate update/delete/evolution phases. Current demo/benchmark code compares streaming digests of facts and daily totals against an independent SQLite rank-all-arrivals rebuild; the daily reference groups winning live events directly without production buckets or transformation SQL. Historical reports retain their original facts-only comparison scope. Synthetic values are integer-valued and exactly representable for these digest comparisons; arbitrary floating-point sums do not acquire an exact-decimal guarantee.

`tests/integration/test_execution_boundaries.py` adds focused execution invariants:

| Boundary | Evidence |
| --- | --- |
| Finite global aggregates | Within-bucket and cross-bucket overflow reject a whole publication; identities/checkpoints roll back, old pins remain readable, orphan recovery and corrected retry succeed. A legacy nonfinite materialization fails validation and a limit-1 daily read before yielding. |
| Reader/GC ownership | A controlled pause before validation reads proves its pin survives concurrent publication/retention. Closing a partially consumed query releases the engine before unpinning; abandoning a stream closes its engine while the handle remains pinned. |
| Retention lock gap | Pause after retention commits, publish a new snapshot, then resume orphan reconciliation. Both the old pinned snapshot and newly published files survive recomputation. |
| Semantic invalidation | Quality-only bounds validate with zero writes/all nodes reused; a rejected stricter policy changes no catalog state. Nullable schema-only addition reuses normalized paths, materializes null typed values and preserves historical schema. |
| Immutable specification | Mutating the caller's field dictionary between validation and publication cannot alter the selected or stored contract. |
| Bounded lineage/CSV | 1,500 history entries page under a stable acceptance cutoff through GC; later obsolete versions below the cursor are excluded. CLI cursor flags agree. Interleaved CSV readers preserve valid large records and restore the global limit. |

The executable [50,000-original exercise](../benchmarks/verify_incremental.py) and its [raw report](../artifacts/deep-correctness-2026-10-20.json) verify all seven published states independently, including exact identity/source cardinality, namespace separation, pinned facts/daily results, one-bucket locality, zero-write obsolete/policy phases, retention/restart and historical conflict rejection. It is a focused correctness diagnostic, not the five-million-event standard benchmark.

A retained manifest is immutable by application convention on an owned trusted local filesystem. Queries, publication reuse and explicit validation reject corrupted bytes, mismatched schemas and wrong row counts. `tests/integration/test_integrity.py` rewrites a file as valid Parquet with altered values and proves historical reads fail and a rejected publication leaves identities, source checkpoints and snapshots unchanged. It also proves recovery refuses unsafe references and empty/partial/unknown manifest topology before retention or deletion, preserving every original snapshot and file. A zero-row publication still retains the complete bucket/node graph and remains queryable. The implementation does not claim malicious-user isolation, distributed commit, automatic historical identity compaction or automatic stale-reader recovery.

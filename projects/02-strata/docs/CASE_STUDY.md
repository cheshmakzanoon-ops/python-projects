# A published manifest can outlive failed cleanup

The problem was to make an embedded byte store explain exactly what remains
true after failure. A synchronized WAL must retain complete acknowledged
transactions; compaction must preserve old snapshots and never resurrect a
deleted value. Dependencies supply testing, packaging and typing. The WAL,
skip-list, Bloom/indexed table format, transaction publication, conflict checks,
version retention, and recovery are original Python implementation.

A SQLite wrapper would hide these mechanisms, so it was rejected as the core.
Full compaction was chosen over a background leveled planner to make the first
file-publication boundary small enough to challenge thoroughly. This costs
whole-database stalls and is documented as a limit.

One defect appeared during review of exception paths. Compaction wrote and
synced the replacement manifest, switched its live table list, then entered
obsolete-file cleanup. If cleanup raised *before* closing the source table
descriptors, the database's normal close routine no longer knew about those
descriptors. Records recovered correctly, but the poisoned owner leaked file
handles. Testing only process termination would hide this because the operating
system closes all descriptors when the process exits.

The regression `tests/acceptance/test_faults.py::test_st07_cleanup_exception_closes_retired_descriptors`
creates two source tables, deletes the record, raises an actual `OSError` after
manifest publication but before cleanup, checks reads and poisoned-writer state,
closes the owner, and independently counts `/proc/self/fd`. Restoring the former
close-after-failpoint ordering in a separately built wheel reproduces **14 open
descriptors versus a baseline of 12**; the
[captured intentional failure](../artifacts/descriptor-regression-before.txt)
records the independently counted leak. This was an explicit local reconstruction
of the earlier ordering, not a claim about a published historical release.

The fix closes source descriptors immediately after durable publication while
holding the database mutex, then runs fallible unlink cleanup. Readers have
already finished or hold detached byte tuples, so they need no retired file
references. The same regression passes against the fixed installed package,
and reopening proves the deletion remains effective and orphan files retire.
Other tests kill actual child owners at seven table/manifest/retirement points
and simulate both allowed outcomes of an unsynced directory rename.

Independent review found two additional boundary failures. If WAL construction
opened its descriptor and then failed directory synchronization, its caller had
not received the instance and could not close it; the new regression observed a
one-descriptor leak in both direct construction and database open. The
constructor now closes its descriptor before propagating any failure. Review
also found that restore verified the backup content hash but ignored the backup
metadata version. Restore now validates the exact typed version-one schema
before even opening the source (normal open itself may perform recovery).
Sixteen malformed-schema cases prove no source-open or destination side effect;
a separate valid-schema, wrong-content-hash test preserves end-to-end integrity
checking. The reviewer's independent MVCC/corruption/poison/manifest-loss script
also passes unchanged after these fixes.

The current 79-test suite passes on CPython 3.13.16 and 3.14.8. Branch-aware
storage-core combined coverage is 95.49% (96.82% statements, 91.43% branches);
this includes the state machine and binary I/O,
and excludes measurement/provenance/demo adapters explicitly. A separate required
100-seed × 5,000-operation suite compares independent dictionary histories,
periodically flushes/compacts pinned snapshots, rejects conflicts, and reopens
the real database. Its current run status is tracked in `VERIFICATION.md`.

The first CI workload measured 0.06822 s full compaction and 0.01793 s validated
reopen for 2,000 starting records with 2,000 mixed operations. Durable batches
of 100 amortized synchronization compared with single writes, but timings vary between runs on the shared host; see [benchmark evidence](BENCHMARKS.md).
These are small generated workloads, not production usage or hardware
power-loss evidence. The accepted committed measurements and fresh compatibility
checks below supply the separate final verification.

An interview explanation: the central invariant is that a durable manifest
never references an unsynchronized replacement table or retires still-needed
versions. The tradeoff is foreground full compaction and materialized scans;
the measured long-suite bottleneck is fsync plus historical scans. The hard
failure is an exception after publication, not just a killed process. The next
justified extension would preserve this boundary while adding bounded streaming
snapshot iterators and compaction planning, then rerun the same fault matrix.

## Committed standard measurement

The [corrected standard report](../../../docs/evidence/final/standard/strata-3.14.8-benchmark-benchmark.json)
and [verification wrapper](../../../docs/evidence/final/standard/strata-3.14.8.json)
at source `ec1d0106df086a48923016c33199cfbda0aebbc0` passed the full 250,000
initial records, 200,000 mixed operations and 50,000 hot-set churn operations
against independent dictionary/recovery checks. Initial batches of 100 took
6.048369 seconds, or 41,333.46 records/s; mixed-read p95 was 1.237005 ms, full
compaction stalled 2.261025 s and reopen/recovery took 1.219946 s. Peak RSS was
316,469,248 bytes. Churn compacted 10,196,594 bytes to 19,641 bytes.

Five separate 2,000-record durable-commit measurements gave median single-record
rates of 3,142.95/s for Strata and 4,175.59/s for SQLite; batches of 100 gave
74,758.99/s and 158,757.46/s respectively. SQLite was faster in both measured
configurations. These variable, cache-uncontrolled synthetic measurements show
the batch/durability tradeoff and do not establish a general engine ranking.
The fresh [3.13.16](../../../docs/evidence/final/python313/strata-3.13.16.json)
and [3.14.8](../../../docs/evidence/final/python314/strata-3.14.8.json) compatibility
runs each passed all 79 tests and the quality/build/installed-wheel/demo/CI gates
at that same corrected-reporting source; default remains 3.14.8.

Final review also caught a measurement-description error: the read-amplification
counter is sampled immediately after the first owner's compaction, before its
next validation scan and the separate recovery owner. The old limitation string
incorrectly included recovery reads. Only that report string changed; the
corrected full standard and compatibility runs above exercise it. The
[erratum](../../../docs/evidence/final/attempts/strata-counter-scope/coordinator-erratum.json)
and [old standard capture](../../../docs/evidence/final/attempts/strata-counter-scope/standard/strata-3.14.8-benchmark-benchmark.json)
preserve the former wording and numeric results at their actual earlier source.
The current 216.55× ratio describes the measured phase, not all recovery I/O.

The separate required **100 × 5,000 = 500,000-operation** stateful suite passed
at source `9218b77769cef807700d67f8a0c2b97512b9cc0e`; its
[raw per-seed results](../../../docs/evidence/final/strata-extended/strata-extended.json)
and [wrapper](../../../docs/evidence/final/strata-extended/strata-3.14.8.json)
retain that exact revision. The [impact analysis](../../../docs/evidence/final/strata-extended/reporter-impact-analysis.json)
shows that storage algorithms, tests, dependencies and the extended entry point
are unchanged and that its execution never invokes the changed reporter.
This retains the original extended evidence for the unchanged storage core;
it does not claim a new execution or equal whole-project digests.

# Current agent status

Status: verifying. Owner A03. Source root: projects/03-current. No external blocker. No Git mutations performed by the worker.

## Implemented interfaces

`Record`, `Config`, `Journal`, `Engine`, `Runtime`, `Delivery`, `IdempotentSink`, stable `partition_for`, canonical JSON. CLI `demo`, `benchmark`, `clean-demo`, `inspect`, `replay`. Exact NDJSON event/control admission ordering, scalar envelope validation, minimum-active monotonic watermarks, explicit idle/resume, tumbling/sliding sum/count/min/max/derived average, inclusive bounded interval joins, late rejection/revision semantics, durable ingress, atomic prefix/checkpoint/local sink/outbox, independent greatest-revision sink, bounded queues and admission/state/outbox/main-database page budgets.

## Verified gates and commands

- CU-01–CU-08 have real mapped executable tests; see ACCEPTANCE.md for exact names and invariants. Includes Hypothesis 80 event/control examples and 35 generated admission histories, process exits at four checkpoint phases, lost acknowledgements, immutable revision conflicts, old-revision retries, repeated event IDs, idle/resume and disk exhaustion.
- `uv run --locked --python 3.13.16 ruff format --check .`: passed (39 files).
- `uv run --locked --python 3.13.16 ruff check .`: passed.
- `uv run --locked --python 3.13.16 mypy src`: passed (21 source files, strict).
- Python 3.13 full suite: 30 passed in 29.10 seconds, 98% core coverage; log copied to `artifacts/tests-python313.txt`.
- Clean built-wheel Python 3.14.8 installation at `/tmp/current-wheel314`: full suite 30 passed in 8.36 seconds; core coverage 98% (469 statements, 152 branches, 7 missed statements, 7 partial branches). Import path confirmed `/tmp/current-wheel314/lib/python3.14/site-packages/pp_current/__init__.py`.
- `uv build`: wheel and source distribution built successfully. Wheel 3.14 rerun after final CLI/oracle metadata changes: 30 passed in 23.24 seconds; `artifacts/tests-wheel-python314.txt`. An installed-wheel `python -I -m pp_current.cli demo` from `/tmp` succeeded, including child exit 73 and full oracle reconciliation; report/timeline are in artifacts.
- Default `.python-version` is now 3.14.8 after successful required dependency installation/full tests; 3.13.16 remains required and supported.

## Evidence and limitations

Development CI baseline showed full independent reconciliation of 10,000 events: 9,902 on-time, 65 accepted-late, 33 rejected-late and 25,345 latest outputs. A trial processing rate was approximately 865 events/s during competing local workers. That run was interrupted before its benchmark completed while scalar serialization was being optimized; it is NOT final performance evidence. No incomplete benchmark is labeled a pass. Final stable-source CI benchmark passed: `artifacts/benchmark-ci.json`, Python 3.14.8, five measured 10,000-event runs plus separate hot run, all full oracle reconciliations true. Median processing throughput 1,194.68 events/s; hot throughput 1,008.98 events/s; process RSS high-water 114,102,272 bytes. Source content digest `ababa3cb1e6836489b8fe1d0f475ecbcd2cc35e63b74aab2d030334b7a10491b`; this is dirty development evidence, not final committed evidence.

Standard is fully implemented at one million approximately 256-byte generated events, four source partitions, 10,000 keys, 10% delayed timestamps, explicit idleness, 30-second windows and separate 50%-hot workload. Per coordinator instruction and the brief's documented run-cost exception, standard uses one full normal measurement plus one full hot measurement; CI retains five measured repetitions. Standard removes only marked owned bulk outputs after each run and retains compact reports. Full independent batch reconciliation is enabled for both profiles. Coordinator will run standard serially on an immutable committed export; worker will not run the costly dirty-source standard workload.

Single owner/fixed topology, integer-millisecond timestamps, timestamp-based late policy and inclusive join bounds are documented. SQLite FULL process-exit tests do not establish power-loss correctness. Main-database page budget is not a whole-filesystem quota. No paid service, credentials, external dataset, broker or sibling source dependency exists.

## Remaining and next action

All worker local quality, tests, packaging, outside-source wheel-demo and CI benchmark checks have passed. Source and documentation writes are now paused for coordinator review/commit. Required outstanding coordinator gates: independent review, final committed immutable verification, standard benchmark and Current→Quarry integration. No local acceptance failure is currently known.

Active files: none; worker paused. Resume only on coordinator followup, inspect the committed snapshot and this checkpoint first. Final checks on immutable source, costly standard and integration are coordinator-owned. No service restart required.

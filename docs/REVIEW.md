# Correctness and reliability review

This is the October 18 historical review of source snapshot
`554e0ba461793657c6279068e361a35b3097ecf6`. Its counts, hashes, and compatibility
observations belong to that revision. See the [later reliability and interface
review](QUALITY_REVIEW.md) and [current verification status](STATUS.md) for subsequent changes.

This review examined all ten products, their public interfaces, persistence and failure
boundaries, and the shared development tooling. The changes address reproducible defects
and add regression coverage; they do not change the repository into a single application
or add deployment infrastructure.

## Changes

| Area | Defects corrected |
| --- | --- |
| Anchor | Empty errors incorrectly completed activities; invalid handler results escaped the retry policy; long internal chains exhausted the Python call stack. |
| Strata | WAL rotation and exceptional cleanup leaked descriptors or left stale handles; malformed manifests passed validation; benchmark scratch paths could overwrite and delete existing databases. |
| Current | Idle inputs did not finalize on end; filtered events bypassed lifecycle validation; inspection initialized missing state; outbox acknowledgements accepted conflicting payloads; recovery and output ownership checks were incomplete. |
| Meridian | URL parsing discarded PostgreSQL transport options; failed backups retained incomplete files; failed restores left partial schema/data; boundary dates raised unexpected exceptions. |
| Quarry | Snapshot reads initialized unowned directories and accepted unsafe manifest paths; JSON nulls became text; numeric overflow, case-colliding fields, and nullable dates produced incorrect analytical data. |
| PyTrace | Several Python expression forms escaped taint analysis; wildcard imports permitted unsafe codemods; malformed cache/plan data, path aliases, interrupted writes, special files, and long filenames were handled incorrectly. |
| Atlas | Readiness exposed hidden corpus statistics; malformed bearer input caused server errors; non-finite ranking parameters were accepted. |
| Proving Ground | Impossible evaluation metrics could pass promotion checks; malformed binary-class probabilities could reach inference or serving. |
| Routecraft | Empty replanning states erased history; float/bool identifiers bypassed validation; invalid geometry and budgets raised unexpected exceptions; large costs overflowed search; initial plans omitted available vehicles. |
| Resonance | Cleanup could partially delete state before rejecting a symlink; outputs could overwrite inputs; non-finite frequency metrics, MIDI rounding/range validation, and sub-sample score durations were incorrect. |
| Shared tooling | Container names alone authorized service management; teardown retained anonymous database volumes and stale connection metadata; normal CI omitted the three public integrations. |

The regression cases cover actual PostgreSQL operations, process termination, failed
filesystem operations, independent numerical outcomes, malformed public inputs, and
preservation of existing files. Peer review also corrected two issues introduced during
this work: temporary filenames exceeding filesystem limits and incomplete cache metadata
validation. Manifest paths explicitly reject wildcard characters even when a literal
filename containing a wildcard exists.

## Compatibility and operational changes

Current now uses checkpoint code version `current-2`. Existing `current-1` checkpoints
are rejected without modifying their stored bytes or raw ingress. A controlled rebuild
must preserve the original configuration, job identity, mapper/predicate, and pipeline
version, and reconcile any invalid input history or changed sink revisions. The default
CLI replay command is not a general migration tool. Follow the
[Current operations guide](../projects/03-current/docs/OPERATIONS.md).

Current also requires fresh demo, replay, and benchmark output directories. Keep personal
data outside generated directories. Cleanup and inspection now fail before modifying
unowned or unsafe paths.

The PostgreSQL helper verifies ownership labels and loopback bindings before starting
existing containers. Teardown removes the selected owned container, its anonymous volumes,
and saved connection metadata. Restart it and export the newly printed URL before use.

Normal CI now runs settlement, stream-lake, and code-search integrations. Their failures,
cancellations, or unexpected absence fail the aggregate check. The aggregate script itself
has executable regression coverage for those outcomes. The
[development guide](../CONTRIBUTING.md) documents local reproduction and separate
interpreter environments.

## Verification and limits

Final verification uses an immutable committed snapshot of the working changes in clean
temporary clones. Creating that snapshot did not move the working branch or alter its
index; the tested snapshot is retained in the final commit history. Each project check
includes locked installation, formatting/lint, strict typing, tests, source/wheel builds,
and an installed-wheel demonstration outside the source tree. Both required Python
versions and real PostgreSQL are used, and source digests are compared before and after
execution. The [machine-readable validation record](evidence/review-2026-10-18.json)
identifies snapshot `554e0ba461793657c6279068e361a35b3097ecf6`, source/lock hashes,
individual suite counts, and outcomes. The workspace implementation hashes match that
tested snapshot.

All **1,680 test executions passed**: **840 cases on each interpreter**, with zero skipped
tests or expected failures. This adds **259 cases** over the previously accepted suite.
The project counts per interpreter are:

| Product | Passed cases |
| --- | ---: |
| Anchor | 60 |
| Strata | 102 |
| Current | 79 |
| Meridian | 59 |
| Quarry | 51 |
| PyTrace | 127 |
| Atlas | 45 |
| Proving Ground | 117 |
| Routecraft | 103 |
| Resonance | 51 |
| Shared tooling | 46 |

Formatting, lint, strict types, packaging, installed-wheel demonstrations, and public
seeded demos passed on both Python 3.13.16 and 3.14.8. Settlement, stream-lake, and
code-search each passed on both interpreters. Shared tooling tests and strict documentation
builds also passed on both.

Existing standard-workload and performance reports retain their original source revisions.
They are historical measurements, not measurements of this patch. No new production
capacity or coverage claim is inferred from the regression suites. Remote TLS certificate
handshakes were not established by the local trust-authenticated PostgreSQL tests, and
hosted GitHub Actions execution remains separate from local validation. A review and
passing tests do not establish that no further defects exist.

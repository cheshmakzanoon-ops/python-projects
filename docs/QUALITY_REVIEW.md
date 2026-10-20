# Reliability and interface review — October 2026

This review concentrates on failures at persistence, input, and operator boundaries. The goal is to make invalid state fail explicitly, preserve valuable data on failure, and make the repository easier to run and assess. Existing algorithm implementations and independently locked package boundaries remain intact.

## Changes by product

| Product | Reproduced problem | Resulting behavior |
| --- | --- | --- |
| Anchor | Retry backoff could overflow PostgreSQL timestamps; HTTP history pagination fetched the complete history; malformed JSON text could return server errors | Bounded retry delays and SQL pagination; supported ASGI body limiting; unambiguous JSON with finite values, valid text, and bounded nesting |
| Strata | A missing WAL was silently recreated; complete transaction frames could be missing from an otherwise valid log | Initialized databases require their WAL; recovery rejects sequence gaps; first initialization synchronizes the WAL before publishing its manifest |
| Current | Opening an unrelated SQLite database could modify it; malformed schemas and checkpoint positions could acknowledge unreplayable state | Recognize schema constraints before writable initialization, create the schema atomically, and verify checkpoint/ingress consistency; reject invalid cursors |
| Meridian | Ambiguous JSON and oversized pagination values reached the backend; validation errors could be reflected as HTML | Strict bounded request parsing, plain-text screen errors, protected authenticated responses, and structured operator views |
| Quarry | Altered Parquet files could change historical reads and be reused; incomplete recovery manifests could misclassify live data as orphaned | Verify committed content and manifest topology before reading, reusing, validating, or recovering snapshots |
| PyTrace | Output paths could overwrite analyzed source; source evaluation inside indices and assignment targets was missed | Refuse source/output aliases, publish caches with exclusive temporary files, and analyze the relevant expressions in evaluation order |
| Atlas | Export pagination materialized the full visible corpus; the browser view had incomplete interaction and accessibility states | Bounded same-snapshot export pages, defensive HTTP headers, and a complete local search interface with document reading and pagination |
| Proving Ground | Artifact publication omitted a directory synchronization; malformed model/input contracts could escape validation | Synchronize staged publication, enforce supported manifests and pipeline structure, and return clean validation errors for invalid sensor data |
| Routecraft | Cancellation could be forgotten between construction attempts; reports misstated boundary delays and zero-duration service | Observe stopping conditions between construction phases, validate strict exchange formats, protect output paths, and draw verified durations |
| Resonance | Score parsing and alignment allocation were unbounded; invalid dimensions and MIDI values were accepted | Bound parsing and quadratic alignment, validate numerical contracts, and provide an accessible playable report with explicit preview scope |

Regression tests exercise these failures through public APIs, actual PostgreSQL and SQLite databases, filesystem operations, process recovery, and independent numerical or state models. Read each product's `docs/VERIFICATION.md` for working-tree checks and historical evidence; [repository status](STATUS.md) identifies the final verification scope.

## Operator experience

Meridian's journal, account, and reconciliation pages show typed records and signed minor-unit amounts rather than raw JSON. Authentication and tenant membership checks remain authoritative. Responses protect authenticated content from caching; screens use restrictive browser policies and plain-text validation errors.

Atlas provides labeled search controls, query help, loading/error/empty states, paging, a keyboard-accessible document dialog, and an explicit connection reset. Concurrent requests cannot replace newer results, and token changes clear the visible authenticated state. Static assets ship locally with the package.

Resonance's report distinguishes the playable preview from the complete recording, labels audio and numerical tables, exposes the full scientific figure, and supports small screens. Native audio controls retain keyboard behavior. Routecraft's timeline distinguishes travel, waiting, and service instead of inventing duration for zero-length operations.

Chromium checks cover desktop and mobile layouts. Selected WCAG 2 A/AA and WCAG 2.1 A/AA rules pass automated Axe checks for Meridian, Atlas, and Resonance. Functional checks include search interactions and native audio playback. These are bounded automated and visual checks, not a complete accessibility conformance assessment.

## Maintenance and compatibility

The root task dispatcher now selects one interpreter consistently for execution, builds, and installed-wheel checks. Immutable verification clears inherited project/source selectors so an external editable environment cannot satisfy a clean-copy test. CI selection rejects ambiguous or overlapping paths and resolves Git revisions before diffing.

The dependency advisory command exports locked runtime requirements, evaluates applicable markers in the audit interpreter, and compares every reported package identity with that export. Incomplete reports, skipped packages, failed exports, service errors, and known vulnerabilities fail the command. A weekly read-only workflow retains reports; [SECURITY.md](../SECURITY.md) documents coverage and limitations.

No dependency resolutions changed. Valid persisted formats remain supported, while malformed schemas, inconsistent state, ambiguous JSON, and unsupported exchange versions are rejected more strictly. Strata also refuses an old interrupted-initialization state with a manifest but no WAL: automatic reconstruction would hide possible data loss. Follow the owning runbook before repairing or rebuilding state.

Quarry's content checks add file I/O to reads and reuse. Historical performance records retain their original source revisions and are not relabeled as measurements of these changes. CI-sized workloads validate behavior; full standard workloads and production capacity are separate questions.

The public documentation now separates product requirements, development commands, architecture, runbooks, and verification history. Obsolete execution prompts and coordination notes were removed. Factual source identities, notices, synthetic-data descriptions, and historical test/benchmark records remain intact.

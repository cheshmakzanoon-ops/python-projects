# Product requirements

This document defines the functional contracts and acceptance identifiers for the ten products. A requirement is an obligation, not a claim that a revision has passed. Each product's `docs/ACCEPTANCE.md` maps these identifiers to executable checks; [verification status](STATUS.md) identifies the source actually tested.

The products target Linux with standard CPython 3.13.16 and 3.14.8. Each owns its package, lockfile, persistence formats, and recovery procedures. Anchor and Meridian require PostgreSQL. Other core workflows run locally without external accounts, paid APIs, GPUs, downloaded model weights, or private datasets. Integrations exchange files or HTTP requests through installed public interfaces.

## Common contracts

- **Durability:** every acknowledgement has a named commit or synchronization point. Tests distinguish committed, rejected, and uncertain outcomes. A process kill does not prove power-loss safety.
- **Concurrency:** the owning product states its lock order, isolation model, and reader lifetime. Cancellation and failure cannot release a resource while an operation still uses it.
- **Compatibility:** persisted formats have explicit versions. A supported old fixture must be read and continued; unsupported formats fail before mutation. Breaking semantic changes include an actionable migration or rebuild procedure.
- **Resource limits:** limits apply before expensive allocation or publication. Reaching a limit produces backpressure or an explicit failure rather than silently dropping accepted data.
- **Security:** authorization is enforced at every supported access path. Parsing and output paths are bounded. The [security policy](../SECURITY.md) states deployment and trust boundaries.
- **Verification:** algorithmic changes have an independently derived model, mathematical check, or external reference where practical. Recovery and race tests target actual commit boundaries. Test counts alone establish no guarantee.

[CONTRIBUTING.md](../CONTRIBUTING.md) defines development commands. The [repository architecture](architecture/REPOSITORY.md) defines package boundaries; the [evidence policy](architecture/EVIDENCE.md) defines reproducible verification and measurements.

## Anchor: durable workflow engine

**Owner:** [`projects/01-anchor`](../projects/01-anchor/), package `pp_anchor`. **Interfaces:** Python SDK, CLI, local HTTP control API.

Anchor coordinates versioned workflows through an append-only event history and a deterministic command reducer. Its workflow language covers activities, parallel dependencies, persisted timers, signals, retries, cancellation, and compensation. Arbitrary suspended Python stacks are outside the persistence model. Temporal is a conceptual reference for replay and external activity boundaries. [S10]

History append, sequence allocation, task/timer projections, and ingress idempotency commit together. A run pins its definition digest and event semantics. Replaying an incompatible definition or unsupported event version fails with a useful diagnostic. Command IDs remain stable across replay and retries.

Workers execute activities at least once. Lease reclamation increments an epoch; heartbeat and completion compare that epoch transactionally. Database time governs persisted deadlines. External side effects require their own stable business key and idempotency contract. Queue selection with `SKIP LOCKED` is an admission technique, not a general consistency guarantee. [S11]

Compensation has explicit pending, blocked, running, failed, and completed states. Dependent cleanup finishes before predecessor resources are released. Failed cleanup remains unresolved and retryable. Cancellation cannot prove an arbitrary external effect stopped: the demonstration provider supplies a durable cancellation fence that prevents a stale publication after cleanup.

HTTP operations cover submission, signals, cancellation, status, history, health, and readiness. Reusing a submission/signal idempotency key with an identical canonical payload returns its original result; a different payload conflicts. The demonstration shows a real provider effect, worker interruption, recovery, compensation, and replay verification.

**Boundary:** one PostgreSQL deployment; no multi-region consensus, arbitrary-code sandbox, general in-flight workflow migration, or universal exactly-once side effects.

### Acceptance criteria

| ID | Scenario and evidence required |
| --- | --- |
| AN-01 | Replay every demo history to the same final state and command IDs; an incompatible definition identifies the divergence event |
| AN-02 | Crash submission before/after database commit, retry, and prove one logical run with consistent idempotency conflict handling |
| AN-03 | Kill a worker after the provider effect but before completion acknowledgement; execution retries and the provider records one logical publication |
| AN-04 | Pause worker A beyond its lease, let worker B take over, resume A, and reject all stale-epoch state changes |
| AN-05 | Stop schedulers with persisted timers, advance the test clock, restart, and record one logical firing per timer |
| AN-06 | Exercise early/duplicate signals, completion/cancellation races, a paused-before-effect stale activity after cleanup, and all completion orders of a parallel join |
| AN-07 | Fail a later stage and a compensation attempt; show retries and an unresolved state until cleanup actually succeeds |
| AN-08 | Run two schedulers and several workers with injected failures; account for every accepted run and verify no silent loss or orphan activity |

## Strata: transactional embedded storage engine

**Owner:** [`projects/02-strata`](../projects/02-strata/), package `pp_strata`. **Interfaces:** embedded byte-record API and inspection CLI.

Strata implements a write-ahead log, ordered memtable, immutable sorted tables, Bloom filters, manifests, snapshot-isolated transactions, and compaction. LevelDB supplies architectural context; the formats and bounded implementation remain Strata's own. [S12]

One process owns a database. Readers share that owner's resources; commits publish serially. A second owner fails explicitly. Transactions overlay private writes/deletes on a repeatable snapshot and use first-committer-wins checks for their write sets. Write skew is allowed: snapshot isolation is not serializability.

A synchronized complete WAL batch is the durability boundary. Append/sync failure leaves an uncertain outcome, fences further writes, and requires close plus verified recovery. Recovery validates frame integrity and sequence continuity before repairing a tail. Interior corruption is never silently skipped. Persistent hashes are stable across processes, and malformed lengths are rejected before allocation.

An old snapshot retains every version and file it needs through flush and compaction. Conflict metadata survives insert/delete cycles while an older writer may still conflict, then becomes reclaimable. A tombstone is dropped only when an older value cannot reappear. Table and manifest publication precede source-file retirement. Backup/restore names its snapshot and synchronization guarantees.

POSIX filesystem assumptions and tested failure points are explicit. The demonstration closes the first owner's snapshots before a separate process is killed and recovery begins; in-memory handles do not survive owner termination. SQLite's atomic-commit discussion informs the distinction between process and storage failures. [S13]

**Boundary:** no SQL, networking, replication, distributed transactions, or arbitrary-object persistence.

### Acceptance criteria

| ID | Scenario and evidence required |
| --- | --- |
| ST-01 | Compare seeded operations and range scans against an independent versioned reference model |
| ST-02 | Interrupt at WAL append/sync/publication points; retain every acknowledged transaction and never expose a partial batch |
| ST-03 | Distinguish an incomplete final WAL frame from interior corruption; never silently discard later committed data |
| ST-04 | Hold snapshots across overwrite/delete/flush/compaction and preserve their original point-read and scan results |
| ST-05 | Reject conflicting writers, including an old transaction racing with insert-then-delete on its written key |
| ST-06 | Demonstrate allowed snapshot-isolation write skew and explain why it is not a serializable database |
| ST-07 | Interrupt table creation, manifest publication, and obsolete-file cleanup; recover without resurrecting deleted keys |
| ST-08 | Handle disk-full, short-write, failed-sync, oversize input, malformed length, second-process open, and snapshot backup/restore; reject writes after uncertain WAL failure and recover without sequence reuse |

## Current: event-time stream processor

**Owner:** [`projects/03-current`](../projects/03-current/), package `pp_current`. **Interfaces:** pipeline API and CLI.

Current processes keyed event streams with fixed worker topology, map/filter stages, tumbling/sliding windows, bounded interval joins, explicit event-time control records, late revisions, backpressure, and SQLite-backed ingress/checkpoints/outbox state.

An event carries source/partition/offset identity, event ID, event time, key, payload, and schema version. The first committed admission assigns a durable ordinal. Identical retries return that admission; conflicting offset reuse fails. Distinct offsets sharing an event ID remain distinct inputs. Event/control interleaving, including idle/resume/end decisions, is journaled so recovery can reproduce disposition.

Time units and half-open window boundaries are explicit. Watermarks never regress. Unfinished active inputs determine minimum progress; idle inputs are excluded, but an idle unfinished source does not become complete when another input ends. Global terminal progress requires all inputs to end. Resumed old records follow the declared lateness policy and cannot resurrect expired state. Flink documents the underlying event-time concepts. [S14]

A checkpoint commits one consistent ingress prefix, operator/input state, compatibility identity, and pending outputs. A stale owner cannot replace a newer prefix. Serialized connection operations and settled asynchronous cancellation preserve commit/close ordering. Runtime state limits are enforced during allocation; changing a resource budget does not change the window semantics.

Output identity is `(job_id, operator_id, logical_result_key, revision)`. Retries preserve canonical payloads; conflicting identity reuse fails. Sinks retain the greatest committed revision so older retries cannot overwrite corrections. Exactly-once observable results depend on this explicit sink/source contract; physical replay remains possible. [S15]

**Boundary:** local fixed-topology execution; no distributed rescaling, unbounded joins, general SQL planner, or exactly-once arbitrary HTTP effects.

### Acceptance criteria

| ID | Scenario and evidence required |
| --- | --- |
| CU-01 | Independently derive admission/disposition from the raw journaled event/control trace and compare both dispositions and finalized windows/joins |
| CU-02 | Test exact window/join boundaries, empty keys, repeated timestamps, multiple join matches, and supported negative time behavior |
| CU-03 | Distinguish on-time, accepted-late, and rejected-late inputs; preserve revision rules and avoid state resurrection |
| CU-04 | Stall, mark idle, advance, and resume a source with old records without regressing watermarks |
| CU-05 | Interrupt before/during/after checkpoint staging and publication; restore only a complete consistent checkpoint |
| CU-06 | Lose sink acknowledgement, retry revisions, publish revision 2 before retrying revision 1, and preserve revision 2; reject conflicting reuse of a delivery ID |
| CU-07 | Stall the sink and inject a 50%-hot key; enforce buffer/disk limits and observable backpressure |
| CU-08 | Prevent double application of replayed offsets, document repeated event IDs, and reject incompatible checkpoint/code versions |

## Meridian: multi-tenant ledger and reconciliation backend

**Owner:** [`projects/04-meridian`](../projects/04-meridian/), package `pp_meridian`. **Interfaces:** authenticated Django API, operator CLI, and focused review screens.

Meridian maintains simulated double-entry journals, currency-specific accounts, immutable postings, full reversals, idempotent requests, historical balances, statement imports, and reviewed reconciliation proposals. Django transaction APIs do not themselves establish an isolation guarantee. [S16] [S17]

Amounts use bounded integer minor units with strict decimal-string input. A journal has at least two nonzero postings, one tenant/currency, and a zero signed sum. Cross-tenant/account/currency consistency and posted-data immutability are enforced in PostgreSQL, including direct SQL paths and nested savepoints. A linked reversal corrects a journal; posted rows are not edited.

Posting, balance projection, idempotency result, and tenant sequence commit together. The tenant sequencing lock is held through commit, giving historical sequence queries a defined committed prefix. Authorization derives from verified user membership, held consistently through writes. The lock order and whole-transaction retry policy are documented. Cached idempotency results must agree with immutable journal content.

Balance reconstruction independently folds immutable postings. Largest-remainder allocation conserves positive and negative totals with stable tie-breaking. Projection repair does not rewrite journal history.

Reconciliation uses stable import/row identities and bounded bipartite candidate graphs for one tenant/account. The original matching solver includes unmatched choices and detects equally optimal solutions by exhaustive tiny-graph comparison. Row selection and scope/component budgets provide a usable path for large accounts without silent truncation. Statement-row and posting uniqueness hold across runs. Approval, match creation, and audit state commit coherently; terminal decisions cannot be reopened or deleted.

**Boundary:** synthetic accounting only; no real payments, banking connectors, foreign-exchange accounting, tax/regulatory certification, or database-enforced end-user authorization beyond explicitly tested policies.

### Acceptance criteria

| ID | Scenario and evidence required |
| --- | --- |
| ME-01 | Reject unbalanced/mixed-currency/invalid-precision journals and preserve allocation totals for positive and negative amounts |
| ME-02 | Submit the same request concurrently and after a lost response; produce one journal and reject mismatched idempotency payloads |
| ME-03 | Execute opposite-direction concurrent transfers on real PostgreSQL; preserve balances and retry whole failed transactions correctly |
| ME-04 | Interrupt posting and prove no partial journal/projection/idempotency result; direct prohibited database edits also fail |
| ME-05 | Rebuild balances independently after randomized postings/reversals and match current and as-of-sequence queries |
| ME-06 | Reject cross-tenant account references and prevent tenant leakage through all reads, exports, and reconciliation operations |
| ME-07 | Solve hand-checkable graphs, detect ambiguous optima, handle repeated imports, bound large components, and reject conflicting concurrent approvals across runs |
| ME-08 | Demonstrate migrations from a previous fixture schema, snapshot backup/restore, and an operator audit exposing an intentionally inconsistent derived projection |

## Quarry: incremental lakehouse and data-quality engine

**Owner:** [`projects/05-quarry`](../projects/05-quarry/), package `pp_quarry`. **Interfaces:** ingestion/planning/query API and CLI.

Quarry ingests immutable CSV/NDJSON changes into a versioned analytical DAG: normalized events, curated facts, daily aggregates, and quality/lineage records. PyArrow and DuckDB provide columnar primitives; Quarry owns event identity, incremental planning, publication, and retention. [S18]

One writer publishes immutable Parquet snapshots while readers pin a catalog snapshot. Namespaced keys and monotonic versions distinguish updates from duplicate delivery. Equal-version conflicting payloads fail; an older update cannot resurrect a tombstoned key. Incremental execution must equal an independently implemented complete rebuild.

Fingerprints distinguish data/transform dependencies from validation policy. A policy-only change still validates all applicable constraints but does not rewrite unchanged data. Supported nullable field additions preserve compatible historical reads; incompatible schema changes require an explicit migration. A contract used for validation and publication is immutable for that run.

Referenced files are complete, synchronized, and content-verified before catalog publication. Input checkpoints and visible snapshot metadata commit together. Recovery distinguishes incomplete uncommitted files from a published manifest. Historical queries and validation hold retention pins for their entire resource lifetime; collection cannot delete a file still in use.

Parsing, batch processing, analytical sessions, and pagination obey configured budgets. Finite input values cannot publish nonfinite aggregate results. Lineage identifies source acceptance/version and supports a stable historical horizon across pages and physical snapshot collection. The demo includes corrections, deletes, validation refusal, interrupted publication, and a historical query.

**Boundary:** local files and one writer; no distributed lakehouse, cloud-object-store atomicity, or complete Iceberg/Delta compatibility.

### Acceptance criteria

| ID | Scenario and evidence required |
| --- | --- |
| QU-01 | Match incremental results to an independent complete rebuild after original, repeated, and out-of-order files |
| QU-02 | Preserve corrections and deletes, reject equal-version conflicts, and prevent older upserts from resurrecting tombstoned rows |
| QU-03 | Rebuild only affected buckets/downstream nodes and prove unchanged node reuse from recorded fingerprints |
| QU-04 | Detect DAG cycles, invalid transforms/configuration, and malformed source records before publishing an invalid snapshot |
| QU-05 | Accept supported nullable additions; reject incompatible schema changes with a useful migration diagnostic |
| QU-06 | Crash after file creation, before catalog commit, and after commit; restore consistent visible data and checkpoints |
| QU-07 | Query an older pinned snapshot during a new publication and preserve its historical rows; GC respects retained/active snapshots |
| QU-08 | Process bounded batches, enforce memory configuration, and show source-to-output lineage for a deliberately wrong source record |

## PyTrace: static analysis and safe refactoring toolkit

**Owner:** [`projects/06-pytrace`](../projects/06-pytrace/), package `pp_pytrace`. **Interfaces:** analysis API/CLI, JSON/SARIF findings, reviewable codemod patches.

PyTrace performs flow-sensitive intraprocedural analysis with lexical binding, a control-flow graph, a finite abstract lattice, and a fixed-point solver. Its rules trace configured input to shell execution and string-built SQL, and identify configured blocking calls in asynchronous functions. AST and LibCST supply parsing/source structure. [S19]

Assignments, evaluation order, short-circuit paths, loops, abrupt exits, and finally continuations are part of the supported model. Shadowed names and aliases follow lexical scope. Diagnostics derive from converged states rather than transient worklist visits. Unknown dynamic behavior remains uncertain under a documented boundary; absence of a finding does not prove safety. Shell and SQL sanitization are context-specific.

Each finding identifies its rule, severity, confidence/coverage, source/sink locations, and evidence. Unicode byte/column conventions are deliberate. SARIF output validates against the official schema. [S20] Cache identity includes parser, rules, configuration, and relevant dependency content; incremental output must equal a clean run.

Two narrow codemods are supported: an unshadowed literal `str()` constructor and a version/hash-bound fixture API keyword rename. Preconditions cover docstring creation, comments, unpacking, aliases, stale hashes, overlapping edits, and reflective behavior assumptions. Default output is a patch. Explicit apply preserves source formatting and verifies syntax without running the target. Repeated application is idempotent.

Target analysis never imports the target, executes build hooks/plugins/configuration, or runs target tests. Parser, CFG, and solver work are bounded. Differential execution is restricted to trusted authored fixtures with harmless stand-in APIs.

**Boundary:** no complete Python soundness, full type checking, automatic security certification, arbitrary plugins, or automatic rewrites of security findings.

### Acceptance criteria

| ID | Scenario and evidence required |
| --- | --- |
| PY-01 | Match labeled positive/negative cases for all three rules, including aliasing, reassignment, shadowing, and path joins |
| PY-02 | Show fixed-point convergence on loops and conservative handling of unknown calls and unsupported constructs |
| PY-03 | Emit correct source locations/evidence for Unicode, multiline expressions, syntax errors, and suppression directives |
| PY-04 | Validate SARIF structure and stable diagnostic identifiers; repeated identical runs produce equivalent findings |
| PY-05 | After local and dependency edits, incremental analysis equals a clean run and invalidates the necessary inputs |
| PY-06 | Apply both codemods to eligible trusted fixtures, preserve behavior/comments, and verify idempotence |
| PY-07 | Refuse uncertain rewrites, stale content hashes, overlapping edits, and malformed/path-escaping inputs |
| PY-08 | Enforce parser resource limits and prove target imports/executable configuration are never executed during analysis |

## Atlas: permission-aware document search engine

**Owner:** [`projects/07-atlas`](../projects/07-atlas/), package `pp_atlas`. **Interfaces:** retrieval API/CLI, FastAPI search/document routes, local search view.

Atlas implements normalized positional indexing, immutable segments, generation publication, bounded query parsing, phrase/filter retrieval, BM25 scoring, permission-safe snippets, and judged evaluation.

The documented BM25 variant uses `log(1 + (N - df + 0.5)/(df + 0.5))`, term-frequency saturation, length normalization, unique query terms, and stable document-ID ties. Defaults are configuration choices, not universal optima. Hand calculations establish the tiny-corpus reference. [S21]

Tenant namespaces are physically separate. Visibility intersects authorized documents, current revisions, and explicit query filters before scoring, phrase evaluation, top-k selection, snippets, counts, facets, or export. `N`, document frequency, and average length use that same visible set; hidden documents cannot change visible statistics.

Every request captures one coherent generation/revision/ACL/configuration snapshot. Requests beginning after a revocation commits observe it; already-running request semantics are explicit. Cache keys bind identity, permissions, ACL revision, generation, normalized query/filter, and ranking parameters. Direct fetch and export enforce the same authorization contract.

A generation becomes visible only after its complete segments and corresponding current revisions publish atomically. Readers pin it; merges preserve positions, scores, and current-document visibility. Corruption fails explicitly. Development/held-out relevance queries remain separate, and pooled or incomplete judgments are described as such.

**Boundary:** no external crawling, OCR, chatbot, mandatory dense model, or claim to eliminate every timing side channel.

### Acceptance criteria

| ID | Scenario and evidence required |
| --- | --- |
| AT-01 | Match hand-calculated BM25 scores/ranks, query-term policy, deterministic ties, and empty cases |
| AT-02 | Verify Unicode normalization, phrase positions, repeated terms, bounded queries, and correctly escaped snippets |
| AT-03 | Preserve results through flush/segment merge and concurrent generation publication |
| AT-04 | Update/delete documents and prove obsolete revisions never reappear through search or direct fetch |
| AT-05 | Test cross-tenant and within-tenant ACL isolation across snippets, counts, facets, exports, and cache entries |
| AT-06 | Modify only hidden documents and preserve visible scores/counts/snippets under the defined visible-statistics contract |
| AT-07 | Revoke access and make the next query observe it; reject corrupted segments and malformed/unbounded inputs |
| AT-08 | Evaluate independently judged queries, report per-query ranking failures, and improve one documented weakness without tuning on held-out judgments |

## Proving Ground: reproducible ML experiment and promotion platform

**Owner:** [`projects/08-proving-ground`](../projects/08-proving-ground/), package `pp_proving_ground`. **Interfaces:** experiment/registry CLI and prediction API.

Proving Ground implements the lifecycle of a synthetic tabular fault-prediction problem: dataset/run identity, frozen temporal splits, leakage checks, train-only preprocessing, evaluation, content-addressed artifacts, promotion, serving, rollback, and descriptive monitoring. scikit-learn supplies estimators. [S22]

Feature metadata declares availability time and label horizon. Split manifests bind dataset identity, membership, purge/embargo rules, and optional entity holdout. Training never fits preprocessing on validation/test data. Promotion thresholds are selected independently of held-out test outcomes.

Evaluation reports bind the exact fitted artifact, dataset/split digests, seed, metrics, slice sample sizes, and gate policy. Missing, nonfinite, undefined, or insufficient-sample required metrics make a candidate ineligible. An unrelated passing report cannot authorize promotion.

Artifact publication is staged, synchronized, content-verified, and restricted to an explicitly supported serialization/type/version contract. Deserialization trust is separate from checksum integrity; a checksum does not make executable formats safe. [S23]

Promotion compares the expected registry generation and records its decision. Serving captures one immutable pipeline/artifact/model/applied-generation snapshot per request. Candidate loading precedes an atomic swap and rechecks generation so a slow old load cannot replace a newer deployment. Failed loads keep the old snapshot or report unavailable without mislabeling predictions. Rollback is a new auditable generation referencing historical content.

**Boundary:** no arbitrary models, distributed/GPU training, AutoML, Kubernetes, or accuracy guarantees for real equipment. Unlabeled drift reports describe distribution changes, not proven predictive degradation.

### Acceptance criteria

| ID | Scenario and evidence required |
| --- | --- |
| PG-01 | Generate, freeze splits, train baselines/candidate, evaluate, and reproduce predictions within a declared numerical tolerance |
| PG-02 | Reject deliberately overlapping splits, policy-violating entities, unavailable features, and declared future-derived leakage |
| PG-03 | Prove preprocessing learns only from training rows and that held-out test judgments do not choose promotion thresholds |
| PG-04 | Reject a failing candidate, promote a passing candidate, and audit the metrics/rules responsible |
| PG-05 | Race promotions and out-of-order load completions, enforce generation comparison, and prevent an obsolete load from replacing a newer deployment |
| PG-06 | Match offline and HTTP predictions; reject corrupted, unsupported, or untrusted model artifacts |
| PG-07 | Roll back, fail candidate loading, and force a prediction across a model swap; its metadata must match the exact pipeline and applied generation used |
| PG-08 | Inject feature drift and schema changes, produce a descriptive monitoring report, and recover cleanly from an interrupted run/artifact write |

## Routecraft: routing and scheduling optimization engine

**Owner:** [`projects/09-routecraft`](../projects/09-routecraft/), package `pp_routecraft`. **Interfaces:** solver API/CLI, independently verified JSON, route/timeline reports.

Routecraft solves a single-depot capacitated routing problem with directed static travel times, service durations, time windows, shifts, and rolling replanning. It owns construction, regret insertion, local moves, and adaptive large-neighborhood search, with an independent verifier and tiny exhaustive reference.

Integer time/demand/cost units are explicit. Time windows constrain service start. Complete plans visit every mandatory stop exactly once and respect capacity, waiting, shift, and return-to-depot constraints. The verifier recomputes schedules and the lexicographic objective—vehicles first, travel second—from input, without trusting optimizer caches. Directed route reversal recalculates changed arc directions.

Iteration budgets give reproducible search effort for a fixed input/seed. Wall-clock budgets report actual effort and stopping reason without promising identical iteration counts. The best feasible incumbent survives rejected moves, cancellation, and timeout. Outcomes distinguish optimal, feasible, proven infeasible, no feasible plan found, and invalid input. A heuristic timeout is not an infeasibility certificate; an optimality gap requires a valid bound. [S24]

Replanning freezes executed prefixes and starts from a named-node service-completion/departure boundary. Onboard job identities and quantities constrain suffixes: loaded deliveries stay on their vehicle, spare capacity does not create cargo, and started vehicles cannot accept new unloaded jobs. Unsupported mid-edge/in-service states fail. Expanded matrices preserve old-node costs unless a new matrix version is explicitly declared.

The tiny reference enumerates cases up to six customers/two vehicles independently of production neighborhoods. Comparisons use equal declared budgets and report failures/no-improvement cases as well as gains.

**Boundary:** no live traffic/roads, multi-depot operation, implicit reload/transfers, or global-optimum claim for large instances.

### Acceptance criteria

| ID | Scenario and evidence required |
| --- | --- |
| RC-01 | Match exhaustive tiny-instance objective values and proven infeasibility on hand-checkable fixtures |
| RC-02 | Reject duplicate/missing stops, capacity overflow, window/shift violations, and inconsistent cached objective values |
| RC-03 | Test asymmetric travel matrices and demonstrate correct move-cost/schedule recalculation |
| RC-04 | Preserve a valid best incumbent through rejected moves, cancellation, and wall-clock timeout |
| RC-05 | Reproduce iteration-budget results with the same input/seed and report actual search effort |
| RC-06 | Compare authored heuristics to their construction baseline under stated equal budgets and publish failures as well as gains |
| RC-07 | Replan around a new request; reject changed executed stops, transferred onboard jobs, new unloaded jobs on started vehicles, inconsistent cargo manifests, and unsupported mid-edge states |
| RC-08 | Produce independently verified JSON plus route/timeline reports, and distinguish no solution found from proven infeasibility |

## Resonance: guitar audio analysis and transcription workbench

**Owner:** [`projects/10-resonance`](../projects/10-resonance/), package `pp_resonance`. **Interfaces:** audio analysis API/CLI, JSON, monophonic MIDI, playable report.

Resonance estimates pitch/voicing/onsets, groups notes, aligns a monophonic phrase with a versioned reference score, and reports pitch/timing evidence. NumPy/SciPy provide numerical primitives; framing, YIN-style estimation, decoding, and alignment are authored algorithms. The YIN paper and SciPy transform conventions are explicit references. [S25] [S26]

Integer sample positions govern time. Frame/hop size, padding, timestamp convention, lookahead, sample-rate/channel policy, pitch lag bounds, normalization/interpolation, and voicing thresholds are documented. The baseline covers E2–E6 at 44.1/48 kHz. Unsupported rates are rejected or explicitly resampled, never silently reinterpreted.

Silence remains unvoiced. Short/clipped/noisy/polyphonic/low-confidence inputs receive bounded, useful behavior. Cents calculations exclude nonpositive/unvoiced estimates. Bend/vibrato summaries do not manufacture stable notes or musical judgments. Random chunk boundaries preserve frame identity, timestamps, and final flushing under declared tolerances.

The reference score declares note identities, units, tempo mapping, and alignment costs. Monotone matching permits insertions/deletions rather than forcing correspondence. MIDI has explicit tempo, quantization, note-off, and deterministic ordering, checked through an independent parser.

RE-01's E2–E6 grid, steady-state eligibility, noise/amplitude conditions, and RE-05/06 timing/correspondence expectations are fixed before tuning. Every eligible ground-truth frame contributes to RE-01: unvoiced/missing/nonfinite estimates count as failures. Conditional pitch error is reported separately, so abstaining cannot inflate accuracy. Synthetic fixtures establish their stated scope only.

**Boundary:** offline monophonic analysis; no universal polyphonic transcription, subjective performance grading, full-band separation, or hard real-time guarantee.

### Acceptance criteria

| ID | Scenario and evidence required |
| --- | --- |
| RE-01 | On the fixed E2–E6 grid, at least 95% of all predetermined ground-truth-voiced steady-state frames must be classified voiced and estimated within 10 cents |
| RE-02 | Handle silence, short files, clipping, stereo conversion, unsupported rates, and last-buffer flushing without fabricated notes or crashes |
| RE-03 | Match batch and randomized-chunk outputs under documented boundary/tolerance rules |
| RE-04 | Reconstruct the supported STFT fixture within a stated floating-point tolerance and compare key features to an independent reference |
| RE-05 | Recover the intended events of the fixed clean isolated-pluck fixture within predefined onset/note tolerances and invent no events in its silent intervals; report challenge-set errors separately |
| RE-06 | Reproduce the expected match/unmatched mapping for an unambiguous phrase with one inserted and one omitted note; separately analyze bends/vibrato and timing perturbations |
| RE-07 | Export valid MIDI and JSON with consistent note times; round-trip MIDI through an independent parser/checker |
| RE-08 | Produce a playable annotated report, preserve analysis provenance, and process a long recording with bounded chunk buffers |

## Workload profiles

These are profile contracts, not measurements or claims that a workload has been run on the latest source. `ci` exercises behavior with bounded cost. `standard` and extended/focused diagnostics are separate commands and evidence scopes. Exact executed parameters, repetitions, correctness checks, hardware, memory/thread settings, source hashes, and exceptions belong in each report.

| Product | CI profile | Standard / separate stress scope |
| --- | --- | --- |
| Anchor | 100 workflows × five activities | 5,000 workflows; separate 100,000-future-timer exercise |
| Strata | 2,000 records plus fault/property sequences | 250,000 initial records + 200,000 mixed operations; separate churn and 100 × 5,000-operation stateful suite |
| Current | 10,000 events across four partitions | One million events, 10,000 keys, out-of-order/idle/hot-key schedules |
| Meridian | 1,000 journals, 200 accounts, 500 statement rows, eight clients | 250,000 journals, approximately one million postings, 100 tenants, 100,000 statement rows |
| Quarry | 20,000 events/eight buckets with corrections/deletes | Five million events/128 buckets plus late updates, deletes, schema changes |
| PyTrace | At least 50 labeled fixture files / approximately 5,000 lines | Pinned license-compatible 250,000-line corpus plus dependency invalidation graph |
| Atlas | 200 documents / 30 smoke queries | 100,000 generated documents / 2,000 queries; separately judged 250-document / 60-query quality corpus |
| Proving Ground | 5,000 rows and fixed small estimators | 250,000 rows / approximately 40 features with imbalance, missingness, temporal shift |
| Routecraft | Tiny exact cases plus 25-stop search | 25/100/500-stop tiers, multiple seeds, windows/asymmetry/replanning |
| Resonance | Approximately one minute of generated audio | Ten minutes of generated annotated audio with noise, bends, vibrato, rests |

Storage comparisons use equivalent durability and transaction batches. Stream reports reconcile accepted/rejected/replayed input and output revisions. Incremental reports count rewritten/reused work and bytes. Search reports separate scale latency from judged relevance; nDCG/MRR/recall require stated judgment coverage. Model reports include sample sufficiency and preprocessing identity. Solver reports preserve feasibility and actual budgets. Audio reports include voicing coverage as well as conditional error.

## Integration contracts

Adapters live under `integrations/` and execute each participant in its own locked environment through installed CLIs, JSON, or HTTP. They do not import sibling implementation code. Product defects are fixed in the owning product; adapters never patch internal state to produce a successful demonstration.

| ID | Participants / command | Required behavior and evidence |
| --- | --- | --- |
| IN-01 | Anchor + Meridian; `integration settlement` | Terminate after a simulated journal commits but before activity acknowledgement; retry the same business key and verify one journal, balanced replay, and a completed workflow. A separately confirmed reversal is idempotent. Meridian does not supply Anchor's cancellation-before-first-effect fence. |
| IN-02 | Current + Quarry; `integration stream-lake` | Map stable result keys/revisions to namespaced keys/versions. Deliver duplicates, a correction, and an older retry; verify greatest-revision latest state and an unchanged pinned historical snapshot against a full rebuild. |
| IN-03 | PyTrace + Atlas; `integration code-search` | Analyze trusted fixtures, index authorized findings, update/delete obsolete documents, and verify current search/document/export visibility and statistics. Relevance does not establish vulnerability severity or diagnostic correctness. |

Each execution owns fresh state and retains stage commands, source identities, logs, and a structured result. A product or integration failure fails the aggregate gate. Exchange-contract changes require affected product and integration checks. All accounts, source programs, documents, and events in these demonstrations are synthetic local fixtures.

## Technical references

These references describe the underlying algorithms and tools. Project-specific acceptance criteria and workload sizes are repository design choices; references do not imply endorsement or copied implementations.

Check the pinned dependency version before applying examples from external documentation.

| ID | Primary reference | Supports |
| --- | --- | --- |
| [S01] | Python Developer's Guide: status of Python versions | Supported interpreter lifecycle and version selection |
| [S02] | uv: using workspaces | Shared resolution/lock behavior and independent-project alternative |
| [S03] | uv: locking and syncing | Lock freshness, --locked, --frozen, repeatable installation |
| [S04] | Python typing documentation | Type-system interfaces and runtime-validation distinction |
| [S05] | Python asyncio task documentation | Task groups, cancellation, structured asynchronous work |
| [S06] | pytest good integration practices | src layout, importlib mode, installed-package checks |
| [S07] | Hypothesis stateful testing | Generated operation sequences and reference-model testing |
| [S08] | GitHub Actions job matrices | Project/interpreter matrix execution |
| [S09] | GitHub Actions secure-use reference | Permissions, untrusted input handling, pinned Actions |
| [S10] | Temporal workflow definitions | Deterministic command replay and external activities |
| [S11] | PostgreSQL SELECT documentation | Row locking and SKIP LOCKED queue semantics |
| [S12] | LevelDB implementation notes | LSM tables, manifests, compaction, recovery concepts |
| [S13] | SQLite atomic commit documentation | Persistence assumptions and crash-testing methodology |
| [S14] | Apache Flink watermark generation | Event-time progress, idleness, watermark interaction |
| [S15] | Apache Flink fault tolerance | Checkpoints, replay, and bounded exactly-once claims |
| [S16] | Django 5.2 release notes | LTS status and interpreter compatibility |
| [S17] | Django database transactions, plus [PostgreSQL isolation](https://www.postgresql.org/docs/current/transaction-iso.html) | Transaction boundaries and isolation behavior |
| [S18] | Apache Arrow datasets, plus [DuckDB Parquet](https://duckdb.org/docs/current/data/parquet/overview) | Bounded columnar processing and Parquet query primitives |
| [S19] | Python AST, plus [LibCST metadata](https://libcst.readthedocs.io/en/latest/metadata.html) and [codemods](https://libcst.readthedocs.io/en/latest/codemods.html) | Grammar, source structure, scope metadata, formatting-aware transformations |
| [S20] | OASIS SARIF 2.1.0 with Errata 01; [official schema](https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json) | Static-analysis interchange format and schema validation |
| [S21] | Stanford Introduction to Information Retrieval: Okapi BM25 | Term-frequency and document-length ranking concepts |
| [S22] | scikit-learn common pitfalls | Preprocessing consistency and data-leakage prevention |
| [S23] | scikit-learn model persistence | Artifact format trust and version compatibility |
| [S24] | OR-Tools CP-SAT solver documentation | Distinguishing optimal, feasible, infeasible, and unknown outcomes |
| [S25] | SciPy ShortTimeFFT documentation | Windowed transforms, reconstruction, and boundary treatment |
| [S26] | de Cheveigné and Kawahara, “YIN, a fundamental frequency estimator for speech and music,” JASA 111, 1917–1930 (2002) | Original pitch-estimation method; DOI 10.1121/1.1458024 |
| [S27] | Ruff configuration documentation | Explicit parent configuration extension |

[S01]: https://devguide.python.org/versions/
[S02]: https://docs.astral.sh/uv/concepts/projects/workspaces/
[S03]: https://docs.astral.sh/uv/concepts/projects/sync/
[S04]: https://docs.python.org/3.13/library/typing.html
[S05]: https://docs.python.org/3.13/library/asyncio-task.html
[S06]: https://docs.pytest.org/en/stable/explanation/goodpractices.html
[S07]: https://hypothesis.readthedocs.io/en/latest/stateful.html
[S08]: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations
[S09]: https://docs.github.com/en/actions/reference/security/secure-use
[S10]: https://docs.temporal.io/workflow-definition
[S11]: https://www.postgresql.org/docs/current/sql-select.html
[S12]: https://github.com/google/leveldb/blob/main/doc/impl.md
[S13]: https://sqlite.org/atomiccommit.html
[S14]: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/event-time/generating_watermarks/
[S15]: https://nightlies.apache.org/flink/flink-docs-stable/docs/learn-flink/fault_tolerance/
[S16]: https://docs.djangoproject.com/en/5.2/releases/5.2/
[S17]: https://docs.djangoproject.com/en/5.2/topics/db/transactions/
[S18]: https://arrow.apache.org/docs/python/dataset.html
[S19]: https://docs.python.org/3.13/library/ast.html
[S20]: https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/sarif-v2.1.0-errata01-os-complete.html
[S21]: https://nlp.stanford.edu/IR-book/html/htmledition/okapi-bm25-a-non-binary-model-1.html
[S22]: https://scikit-learn.org/stable/common_pitfalls.html
[S23]: https://scikit-learn.org/stable/model_persistence.html
[S24]: https://developers.google.com/optimization/cp/cp_solver
[S25]: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.ShortTimeFFT.html
[S26]: https://pubs.aip.org/asa/jasa/article/111/4/1917/547221/YIN-a-fundamental-frequency-estimator-for-speech
[S27]: https://docs.astral.sh/ruff/configuration/

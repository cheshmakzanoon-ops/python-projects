# Verification status

The subsequent [correctness and reliability review](REVIEW.md) fixes additional defects
across all ten products and shared tooling. Its immutable snapshot passed **1,680 test
executions** across Python 3.13.16 and 3.14.8, including **259 additional cases**, plus
builds, installed-wheel demos, and all three integrations on both versions. Its
[validation record](evidence/review-2026-10-18.json) retains exact source/lock hashes and
counts. Current's checkpoint compatibility change is documented in that review. The
acceptance and performance records below describe their original source revisions.

All ten projects have passed their local required acceptance gates and coordinator review. The 80 project IDs map to concrete implementations, tests and workload evidence in each `docs/ACCEPTANCE.md`; the [inventory](evidence/final/gate-inventory.json) is navigation, not a substitute for execution. No required implementation or local workload is left pending. Hosted CI is separately unverified.

The clean-source CPython 3.13.16/3.14.8 matrix passed **1,136 project test executions**, without skips or expected failures. Every project/interpreter check includes locked installation, formatting/lint, strict types, wheel/sdist builds, runtime-only wheel installation and a full installed-wheel demo outside source. All ten standard workload profiles passed; [evidence](evidence/README.md) retains actual commands, source revisions, input hashes, outputs and limitations. Later documentation commits do not relabel earlier measurements.

| Product | Tests per interpreter | Accepted standard workload |
| --- | ---: | --- |
| Anchor | 54 | 5,000 workflows, 25,000 activities; 100,000 future timers |
| Strata | 79 | 250,000 initial rows, 200,000 mixed operations, 50,000 churn operations |
| Current | 32 | One million ordinary events and one million 50%-hot-key events |
| Meridian | 46 | 250,000 measured journals; 100,000 statement rows |
| Quarry | 37 | Five million originals, 500,000 corrections, 100,000 deletes, 100 schema changes |
| PyTrace | 77 | 250,899 lines; five warm scans and incremental invalidation |
| Atlas | 40 | 100,000 documents; 10,000 measured warm queries |
| Proving Ground | 103 | 250,000 rows × 40 features; lifecycle and serving transitions |
| Routecraft | 75 | 18 scale scenarios × five paired trials, plus five exact-optimal control ties |
| Resonance | 25 | 600 seconds at 48 kHz; five measured runs |

Strata also passed **100 seeds × 5,000 stateful operations**, using an independent dictionary/snapshot oracle and real durable reopen/compaction paths. The extended report retains its original revision; the later reporting-only counter clarification is covered by a separate unchanged-storage-core impact analysis. Independent findings and their regressions are recorded in [review](evidence/INDEPENDENT_REVIEW.md). Each defined domain core exceeded the brief's 85% branch-coverage aim; whole-package figures and scope remain explicit in project documents.

## Integrations

| ID | Result and exercised boundary |
| --- | --- |
| IN-01 | Passed: settlement uses real Meridian HTTP effects, Anchor worker process death before acknowledgement, idempotent retry and reversal compensation; independent SQL checks balanced final journals. |
| IN-02 | Passed: Current emits late revisions delivered in order 1/1/2/1; Quarry retains exact historical identities, a pinned old result and the correct latest result, and rejects conflicting history. |
| IN-03 | Passed: PyTrace findings become Atlas documents; deletion/update, hidden-score and snippet invariance, tenant isolation, direct access denial, merge and next-request revocation are checked. |

[Integration records](evidence/README.md) use separate installed package environments and public HTTP/JSON interfaces, with no sibling source imports.

## Global gates

| Gate | Outcome |
| --- | --- |
| G01 | Passed: ten substantial, identifiable original Python domain cores. |
| G02 | Passed: independent fresh-clone locked installs on both required interpreters. |
| G03 | Passed locally: all 80 required project acceptance IDs, including full workloads. |
| G04 | Passed locally: required formatting, lint, strict types, tests, builds and installed-wheel execution. |
| G05 | Passed: ten seeded demos in clean committed snapshots, including installed wheels. |
| G06 | Passed: independent reference models and actual PostgreSQL, process and filesystem failure boundaries; review defects have regressions. |
| G07 | Passed: all ten standard profiles have measured results and declared provenance, repetitions and limits. |
| G08 | Passed locally: linked architecture, decisions, runbooks, case studies and evidence; strict documentation build is recorded. |
| G09 | Passed: IN-01, IN-02 and IN-03 through public interfaces. |
| G10 | Local selector and aggregate-failure tests passed; hosted workflow execution remains unverified, with real runs observed queued. |
| G11 | Passed: database-free Current quickstart and focused reviewer routes are documented and exercised. |
| G12 | Reviewed implementations and evidence committed/pushed; exact Git and hosted CI observations are reported separately in the final handoff. |

## Limits and external status

Hosted GitHub Actions runs have been observed queued, not successful. GitHub REST API access returned HTTP 403 through this environment's proxy; the read-only public Actions page exposes actual run states. The final handoff checks its exact pushed SHA. No cause for the queue is inferred, and no remote pass is claimed from local tests.

Full required suites were verified on Linux x86_64; other systems remain unverified. Fixtures and scale workloads are synthetic. Single costly benchmark runs are labeled; timings do not establish production capacity. Process termination and fsync tests do not simulate every power-loss/storage failure. Each project documents narrower algorithmic limits and unfavorable results. No code license has been chosen by the owner; provenance and third-party notices are preserved. No release or public deployment has been made.

The tested cloud install/startup configuration is saved as a draft. Saving, publishing and independently proving fresh-task restoration are distinct operations.

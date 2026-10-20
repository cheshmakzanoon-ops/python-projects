# Verification records

[Current verification status](../STATUS.md) identifies the latest tested source. The
[reliability and interface review](../QUALITY_REVIEW.md) describes subsequent product
and tooling changes. Records below retain their original source revisions; they do
not certify later code or repeat historical performance measurements.

Historical command arrays and logs use `$DISPATCHER_PYTHON` for a machine-specific
dispatcher executable path. The [archive publication map](archive-publication.json)
records each original and published file hash and the Git commit containing the
original bytes. Source identities, inputs, outcomes, and measurements are unchanged.
Embedded historical artifact hashes refer to the original bytes; the publication
map binds them to these portable copies.

The [October 20 review record](quality-review-2026-10-20.json) identifies fixed source
`0e52603de3bfbe50094904b5c5b9620af2ac0178`: 2,274 project test executions,
122 shared tooling test executions, twenty package/demo/CI-workload checks, and
six public integration runs passed. It also records the dependency-advisory and
browser checks and their limits.

## Original acceptance matrix

The original local compatibility matrix recorded all ten projects on both required interpreters: **1,136 project test executions**, with no skips or expected failures. Every check also ran Ruff formatting/lint, strict mypy, wheel/sdist build, runtime-only wheel installation and a complete installed-wheel demo outside source. Each verification record retains actual commands, exit codes, source/lock/shared-input hashes and unchanged/clean-source checks.

| Product | Tests per interpreter | CPython 3.13.16 | CPython 3.14.8 |
| --- | ---: | --- | --- |
| anchor | 54 | [record](final/python313/anchor-3.13.16.json) | [record](final/python314/anchor-3.14.8.json) |
| strata | 79 | [record](final/python313/strata-3.13.16.json) | [record](final/python314/strata-3.14.8.json) |
| current | 32 | [record](final/python313/current-3.13.16.json) | [record](final/python314/current-3.14.8.json) |
| meridian | 46 | [record](final/python313/meridian-3.13.16.json) | [record](final/python314/meridian-3.14.8.json) |
| quarry | 37 | [record](final/python313/quarry-3.13.16.json) | [record](final/python314/quarry-3.14.8.json) |
| pytrace | 77 | [record](final/python313/pytrace-3.13.16.json) | [record](final/python314/pytrace-3.14.8.json) |
| atlas | 40 | [record](final/python313/atlas-3.13.16.json) | [record](final/python314/atlas-3.14.8.json) |
| proving-ground | 103 | [record](final/python313/proving-ground-3.13.16.json) | [record](final/python314/proving-ground-3.14.8.json) |
| routecraft | 75 | [record](final/python313/routecraft-3.13.16.json) | [record](final/python314/routecraft-3.14.8.json) |
| resonance | 25 | [record](final/python313/resonance-3.13.16.json) | [record](final/python314/resonance-3.14.8.json) |

Compatibility source is `7114e39c7e9e8af177e84fe8cd990fe5a09bde63`, with Meridian rerun at `59443e2bcdfc6a1dd81f8334c108474eef2d3030`, Current and Routecraft at `b3caa0e4594034ee8edf9ca05c3fd879d6fe18a2`, and Strata at `ec1d0106df086a48923016c33199cfbda0aebbc0` after reporting/control corrections. Exact full commits in the JSON records are authoritative. The initial parallel Meridian attempt shared Django's default test database and failed; those reports/logs, with only the documented executable-path normalization, remain under `final/attempts/parallel-database-collision/`. They are superseded by the successful isolated-database runs in the main table, not counted as passes.

Strata's [extended suite](final/strata-extended/strata-extended.json) passed all **100 seeds × 5,000 operations**, with independent dictionary/snapshot oracles, conflict/abort cases, flush/compaction and reopen checks. Its [outer verification record](final/strata-extended/strata-3.14.8.json) confirms clean committed source and unchanged hashes.

All three public-interface integrations passed in clean committed snapshots: [settlement](final/integrations/settlement/integration.json), [stream-lake](final/integrations/stream-lake/integration.json), and [code-search](final/integrations/code-search/integration.json). Separate installed package environments exchange HTTP or JSON; no integration imports sibling source. Each record retains its actual source commit and commands.

The [acceptance audit](final/acceptance-summary.json) checks 30 accepted project/interpreter/profile records, their raw workload artifacts and three integrations. It independently recounts 1,136 project test executions and compares every accepted project/lock digest with the reviewed current bytes. It retains artifact SHA-256 values and actual tested commits; shared root tooling, the extended suite and hosted status are separate. The [current source comparison](final/current-source-comparison.json) has the same explicit scope.

The [integration verification snapshot](final/handoff-summary.json) reproduces all ten small demos and all three integrations from one clean commit. Its shared-root record checks the current informational manifest statuses, 13 tooling tests, and the strict documentation build; earlier full-workload records retain their actual measurement commits.

All ten full standard profiles are accepted:

| Product | Standard execution record | Principal scale |
| --- | --- | --- |
| anchor | [record](final/standard/anchor-3.14.8.json) | 5,000 workflows / 25,000 activities; 100,000 future timers |
| strata | [record](final/standard/strata-3.14.8.json) | 250,000 initial / 200,000 mixed / 50,000 churn operations |
| current | [record](final/standard/current-3.14.8.json) | 1,000,000 ordinary + 1,000,000 hot-key events |
| meridian | [record](final/standard/meridian-3.14.8.json) | 250,000 measured journals / 100,000 statement rows |
| quarry | [record](final/standard/quarry-3.14.8.json) | 5,000,000 originals + corrections, deletes and schema changes |
| pytrace | [record](final/standard/pytrace-3.14.8.json) | 250,899 lines / five warm scans |
| atlas | [record](final/standard/atlas-3.14.8.json) | 100,000 documents / 10,000 measured queries |
| proving-ground | [record](final/standard/proving-ground-3.14.8.json) | 250,000 rows × 40 features / full lifecycle |
| routecraft | [record](final/standard/routecraft-3.14.8.json) | 18 scale scenarios × five paired trials + five control ties |
| resonance | [record](final/standard/resonance-3.14.8.json) | 600 seconds at 48 kHz / five measured runs |

The standard source is `59443e2bcdfc6a1dd81f8334c108474eef2d3030` for seven products and `ec1d0106df086a48923016c33199cfbda0aebbc0` for Strata, Current and Routecraft. Exact full commits and declared hash inputs in each JSON record are authoritative. Raw benchmark digests and outer-wrapper digests have distinct documented scopes; historical reports are never relabeled as newer executions. Some products expose identical raw JSON under two artifact aliases; those copies are not independent experimental repetitions. Large data, databases, environments and caches are excluded from Git.

Current's accepted record samples process RSS after both ordinary and hot runs and cleanup. Its original standard attempt was deliberately [cancelled](final/attempts/current-rss-before-hot/standard/current-cancellation.json); pre-hot memory figures are superseded. Routecraft's original full report is [superseded](final/attempts/routecraft-missing-control/coordinator-review.json) because it omitted the required non-improvement case. The corrected standard executes a separate exact-optimal fixture with five measured ties without changing the 18 scale workloads. Strata's original read-counter wording has a [scope erratum](final/attempts/strata-counter-scope/coordinator-erratum.json). Its accepted corrected report describes the first-open-owner counters accurately. The [reporting-only impact analysis](final/strata-extended/reporter-impact-analysis.json) proves that the original extended suite's storage core and execution path remain unchanged; it does not claim a newer 500,000-operation execution.

Unsuccessful and superseded attempts remain explicitly identified under `final/attempts/`; they are excluded from accepted totals. Product benchmark and case-study documents explain unfavorable results, memory scope, cost exceptions, synthetic evaluation limits and workload comparability. The [root verification](final/root/verification.json) records the shared-tooling tests and strict documentation build separately from project test counts.

Local validation, Git synchronization and hosted CI are distinct. Hosted runs were observed queued; no remote pass is claimed. See [status](../STATUS.md), [environment](../ENVIRONMENT.md), [independent review](INDEPENDENT_REVIEW.md), [reviewer routes](../PORTFOLIO_GUIDE.md) and [evidence policy](../architecture/EVIDENCE.md).

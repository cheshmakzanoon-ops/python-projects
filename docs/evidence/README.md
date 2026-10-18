# Committed verification evidence

The accepted local compatibility matrix passes all ten projects on both required interpreters: **1,136 project tests**, with no skips or expected failures. Every check also runs Ruff formatting/lint, strict mypy, wheel/sdist build, runtime-only wheel installation and a complete installed-wheel demo outside source. Each verification record retains actual commands, exit codes, source/lock/shared-input hashes and unchanged/clean-source checks.

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

Compatibility source is `7114e39c7e9e8af177e84fe8cd990fe5a09bde63`, with Meridian rerun at `59443e2bcdfc6a1dd81f8334c108474eef2d3030`, Current and Routecraft at `b3caa0e4594034ee8edf9ca05c3fd879d6fe18a2`, and Strata at `ec1d0106df086a48923016c33199cfbda0aebbc0` after reporting/control corrections. Exact full commits in the JSON records are authoritative. The initial parallel Meridian attempt shared Django's default test database and failed; those unaltered reports/logs remain under `final/attempts/parallel-database-collision/`. They are superseded by the successful isolated-database runs in the main table, not counted as passes.

Strata's [extended suite](final/strata-extended/strata-extended.json) passed all **100 seeds × 5,000 operations**, with independent dictionary/snapshot oracles, conflict/abort cases, flush/compaction and reopen checks. Its [outer verification record](final/strata-extended/strata-3.14.8.json) confirms clean committed source and unchanged hashes.

All three public-interface integrations passed committed source `7114e39`: [settlement](final/python314/settlement/integration.json), [stream-lake](final/python314/stream-lake/integration.json), [code-search](final/python314/code-search/integration.json). Separate package environments exchange HTTP or JSON; they do not import sibling source.

Seven unaffected full-size records are accepted: [Anchor](final/standard/anchor-3.14.8.json), [Meridian](final/standard/meridian-3.14.8.json), [Quarry](final/standard/quarry-3.14.8.json), [PyTrace](final/standard/pytrace-3.14.8.json), [Atlas](final/standard/atlas-3.14.8.json), [Proving Ground](final/standard/proving-ground-3.14.8.json) and [Resonance](final/standard/resonance-3.14.8.json). Strata's earlier numbers remain valid with a [counter-scope erratum](final/attempts/strata-counter-scope/coordinator-erratum.json). Its wording-corrected profile, Current's RSS-corrected profile and Routecraft's added non-improvement control are running serially from `ec1d0106df086a48923016c33199cfbda0aebbc0`, followed by all three integrations. Large generated data, databases, environments and caches are excluded from Git.

Local validation, Git synchronization and hosted CI are distinct. Hosted runs were observed queued; no remote pass is claimed. See [status](../STATUS.md), [environment](../ENVIRONMENT.md), [independent review](INDEPENDENT_REVIEW.md) and [evidence policy](../architecture/EVIDENCE.md).

Current's original standard attempt was deliberately [cancelled](final/attempts/current-rss-before-hot/standard/current-cancellation.json) and is excluded from accepted workload evidence. Routecraft's original full run is [superseded](final/attempts/routecraft-missing-control/coordinator-review.json) because it omitted the required non-improvement example. Both corrected full compatibility suites now pass; their earlier reports remain under the respective attempt directories. Corrected standard acceptance is pending, not inferred from the smaller CI profile.

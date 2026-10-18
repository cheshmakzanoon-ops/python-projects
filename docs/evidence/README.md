# Committed verification evidence

The final local compatibility matrix passes all ten projects on both required interpreters: **1,130 project tests**, with no skips or expected failures. Every check also runs Ruff formatting/lint, strict mypy, wheel/sdist build, runtime-only wheel installation and a complete installed-wheel demo outside source. Each verification record retains actual commands, exit codes, source/lock/shared-input hashes and unchanged/clean-source checks.

| Product | Tests per interpreter | CPython 3.13.16 | CPython 3.14.8 |
| --- | ---: | --- | --- |
| anchor | 54 | [record](final/python313/anchor-3.13.16.json) | [record](final/python314/anchor-3.14.8.json) |
| strata | 79 | [record](final/python313/strata-3.13.16.json) | [record](final/python314/strata-3.14.8.json) |
| current | 30 | [record](final/python313/current-3.13.16.json) | [record](final/python314/current-3.14.8.json) |
| meridian | 46 | [record](final/python313/meridian-3.13.16.json) | [record](final/python314/meridian-3.14.8.json) |
| quarry | 37 | [record](final/python313/quarry-3.13.16.json) | [record](final/python314/quarry-3.14.8.json) |
| pytrace | 77 | [record](final/python313/pytrace-3.13.16.json) | [record](final/python314/pytrace-3.14.8.json) |
| atlas | 40 | [record](final/python313/atlas-3.13.16.json) | [record](final/python314/atlas-3.14.8.json) |
| proving-ground | 103 | [record](final/python313/proving-ground-3.13.16.json) | [record](final/python314/proving-ground-3.14.8.json) |
| routecraft | 74 | [record](final/python313/routecraft-3.13.16.json) | [record](final/python314/routecraft-3.14.8.json) |
| resonance | 25 | [record](final/python313/resonance-3.13.16.json) | [record](final/python314/resonance-3.14.8.json) |

Compatibility source is `7114e39c7e9e8af177e84fe8cd990fe5a09bde63`, with Meridian rerun at `59443e2bcdfc6a1dd81f8334c108474eef2d3030` after correcting workload failure reporting. Exact full commits in the JSON records are authoritative. The initial parallel Meridian attempt shared Django's default test database and failed; those unaltered reports/logs remain under `final/attempts/parallel-database-collision/`. They are superseded by the successful isolated-database runs in the main table, not counted as passes.

Strata's [extended suite](final/strata-extended/strata-extended.json) passed all **100 seeds × 5,000 operations**, with independent dictionary/snapshot oracles, conflict/abort cases, flush/compaction and reopen checks. Its [outer verification record](final/strata-extended/strata-3.14.8.json) confirms clean committed source and unchanged hashes.

All three public-interface integrations passed committed source `7114e39`: [settlement](final/python314/settlement/integration.json), [stream-lake](final/python314/stream-lake/integration.json), [code-search](final/python314/code-search/integration.json). Separate package environments exchange HTTP or JSON; they do not import sibling source.

The required standard profiles are currently running serially from `59443e2bcdfc6a1dd81f8334c108474eef2d3030`, together with all ten demos and the three integrations. Completed standard reports will be added here. Large generated data, databases, environments and caches are excluded from Git.

Local validation, Git synchronization and hosted CI are distinct. Hosted runs were observed queued; no remote pass is claimed. See [status](../STATUS.md), [environment](../ENVIRONMENT.md), [independent review](INDEPENDENT_REVIEW.md) and [evidence policy](../architecture/EVIDENCE.md).

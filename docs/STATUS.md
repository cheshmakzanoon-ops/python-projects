# Verification status

All ten assignments have started. Six implementation owners have submitted working packages; Atlas, Proving Ground, Routecraft, and Resonance are completing their tests and interfaces. The coordinator continues independent review, integration, committed-source checks, and required full-size workloads. No whole-portfolio completion claim is made.

| Product | State | Observed local evidence | Remaining |
| --- | --- | --- | --- |
| Anchor | verifying | 54 tests on 3.13/3.14; coordinator check and installed-wheel export demo pass; committed/pushed `eb88f10` | Immutable evidence, full standard |
| Strata | verifying | 79 tests after independent FD-leak/backup-format corrections; both interpreters; installed wheel demo | Coordinator updated check passes; committed/pushed `0909bba`; 100×5000 extended and standard remain |
| Current | verifying | 30 tests on both interpreters; coordinator check passes; committed/pushed `6e857f4` | Immutable evidence, full standard |
| Meridian | needs-fix | 30 local tests and installed-wheel PostgreSQL demo; independent review found missing relational constraints | Correct tenant-idempotency/account-history constraints; reverify; standard |
| Quarry | verifying | 37 tests, bounded CSV/source-mutation regressions; coordinator check/installed-wheel demo; committed/pushed `b98e69e` | Immutable evidence, 5m standard |
| PyTrace | verifying | 77 tests, bounded-source/codemod regressions; coordinator check and independent fixture export pass | Committed/pushed `a76e5a3`; immutable evidence, 250k-LOC standard |
| Atlas | building | Owner reports 40 tests on both interpreters; original index/ACL API and relevance corpus runnable | Final matrix/packaging/benchmarks and independent integration |
| Proving Ground | building | First actual training/promotion/serving lifecycle implemented | Required failure/race/leakage tests and verification |
| Routecraft | building | Actual 25-stop directed search and cargo-safe replanning demo | Required oracle/property/negative suites and verification |
| Resonance | building | Fixed pitch grid and clean-pluck numerical slice runnable | Remaining chunk/STFT/alignment/MIDI/report acceptance and verification |

## Integrations

IN-01 settlement passed a development-tree run through live Meridian HTTP and a separate Anchor environment. An actual killed worker retried one ledger identity, and the confirmed-post reversal scenario completed. IN-02 stream-lake passed revisions 1/1/2/1, correction 10→17, retained historical value 10, independent reduction, and historical conflict rejection. Both need final committed-source runs. IN-03 code-search also passed through separate PyTrace/Atlas environments: current findings, deletion of obsolete evidence, project/source filters, restricted fetch/export, hidden-score invariance, merge, cross-tenant isolation, and next-request revocation. All three integrations still need final committed-source runs.

## Independent review

Strata's constructor sync-failure descriptor leak and unsupported backup format acceptance were reproduced, corrected, and regression-tested. Meridian's cross-tenant idempotency relation and account mutation after statement use were reproduced in isolated schemas; corrections are underway. Positive independent checks include MVCC/compaction/corruption/poison recovery, ledger deferred balance/immutability/reversal/sequence behavior, concurrent reconciliation approval, and 1,000 exhaustive tiny matching comparisons.

Atlas's authored relevance judgments received a separate [semantic review](evidence/atlas-judgment-review.md); its narrow template corpus is not a real-user relevance study.

## Global gates and remote state

G01–G12 remain open until all required product checks and workloads, independent review corrections, IN-01–03, documentation, and committed-source evidence are evaluated together. Root selector, subprocess cleanup/exit propagation, source-scope, CI-state parsing, and demo-cleanup routing tests pass locally. Documentation is checked as owners finish it; missing in-progress targets remain failures.

GitHub Actions runs are visible through the public web page and were observed queued, not passed. REST API access returned proxy403; `api.github.com` was saved as a custom domain addition in the environment configuration draft, without replacing package-manager presets. Saving that draft does not activate or publish it. No remote CI success or environment publication is claimed.

No code license has been selected. Full Linux gates are required; unsupported platform results are not invented.

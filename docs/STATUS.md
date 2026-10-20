# Verification status

The [October reliability and interface review](QUALITY_REVIEW.md) verified committed source `0e52603de3bfbe50094904b5c5b9620af2ac0178` in disposable clean checkouts. All twenty product/interpreter checks passed, with unchanged implementation and shared-input hashes before and after execution. The [machine-readable record](evidence/quality-review-2026-10-20.json) contains exact source and lock hashes, input lists, test counts, command outcomes, and log digests. Subsequent status/evidence documentation does not change those tested implementation inputs.

## Current compatibility checks

| Product | CPython 3.13.16 | CPython 3.14.8 |
| --- | ---: | ---: |
| Anchor | 111 | 111 |
| Strata | 110 | 110 |
| Current | 123 | 123 |
| Meridian | 94 | 94 |
| Quarry | 93 | 93 |
| PyTrace | 151 | 151 |
| Atlas | 64 | 64 |
| Proving Ground | 155 | 155 |
| Routecraft | 129 | 129 |
| Resonance | 107 | 107 |

**2,274 project test executions passed**, with zero failures, skips, or expected failures. Every product check also passed locked dependency installation, Ruff formatting and lint, strict mypy, source/wheel builds, runtime-only wheel installation, and an installed-wheel demonstration outside source. Each product additionally passed its public demo and CI-sized benchmark on both interpreters.

Shared tooling passed **61 tests on each interpreter** (122 executions), formatting/lint, local documentation link validation, and the strict documentation build. Its checks include subprocess cleanup, CI selection and aggregate failure behavior, immutable-copy isolation, service ownership, and complete dependency-audit reporting.

## Public integrations

All three integrations passed on both interpreters, for six executions. Each uses independently installed products and their public HTTP or JSON interfaces.

| Integration | Exercised boundary |
| --- | --- |
| [Settlement](../integrations/01-settlement/) | Meridian HTTP effects, Anchor worker death before acknowledgement, idempotent retry, reversal compensation, and independent SQL balance checks |
| [Stream to lake](../integrations/02-stream-lake/) | Duplicate and out-of-order revisions, retained historical identities, pinned old results, correct latest aggregates, and conflicting-history rejection |
| [Code search](../integrations/03-code-search/) | Finding publication/deletion, permission-aware search, tenant isolation, hidden-score invariance, direct-access denial, and next-request revocation |

## Browser and dependency checks

The fixed-source Atlas browser harness passed functional and selected Axe WCAG 2/2.1 A/AA checks for desktop, mobile, and document-dialog states. It exercises paging, escaped content, keyboard navigation, stale requests, authentication/empty states, identity changes, and absence of external requests or browser storage.

Working-tree Chromium checks of the matching Meridian screens and Resonance report passed the selected accessibility rules and small-screen overflow checks. Journal/account views rendered successfully; Resonance's native audio controls advanced playback. These are bounded automated and visual checks, not complete accessibility conformance.

All ten runtime lock exports passed pip-audit 2.10.1 against PyPI advisories with no known vulnerabilities found. The command verifies the complete applicable package identity set and fails on skipped packages or incomplete/service-error reports. Coverage is CPython 3.14.8 on Linux; development tools, other marker combinations, and unknown vulnerabilities require separate review. See [SECURITY.md](../SECURITY.md).

## Historical workloads

The [evidence index](evidence/README.md) preserves the original compatibility matrix, independent reviews, standard workload reports, and corrections. Those records retain their actual tested revisions and should be compared only within their declared input scopes. Standard workloads include large storage/stream/lake datasets, PostgreSQL contention, static-analysis and search corpora, model lifecycles, routing scenarios, and synthetic guitar audio. Strata also has a recorded 100-seed × 5,000-operation stateful recovery suite.

The full standard-scale workloads were **not rerun for this review**. CI profiles exercise correctness at smaller scale; they do not update historical performance claims. Quarry's new content checks add read/reuse I/O. Synthetic measurements do not establish production capacity or real-recording accuracy.

## Scope and external status

The supported verification platform is Linux x86_64 with standard CPython 3.13.16 and 3.14.8. Other operating systems and experimental interpreter builds remain unverified. PostgreSQL checks use actual isolated local databases; process-fault tests do not simulate every hardware or power-loss failure.

Hosted GitHub Actions is a separate observation. No hosted CI success is established by these local runs. No public deployment, package-registry release, production security certification, or environment publication is claimed. The owner has not selected a code license; notices and factual provenance remain intact.

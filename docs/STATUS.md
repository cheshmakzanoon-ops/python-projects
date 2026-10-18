# Verification status

All ten original implementations exist and have passed local quality, packaging and substantive tests on CPython3.13/3.14. Independent findings have been corrected. The clean-commit compatibility matrix now passes all20project/interpreter combinations (1,136 project tests), including actual installed-wheel demos and CI-size benchmarks. All three committed-source integrations pass. Standard workloads are running serially; whole-portfolio completion is not yet claimed. Current subsequently received an RSS-accounting correction at `5c04cd5`; its affected compatibility reruns passed and its full-size rerun remains pending, and its cancelled old standard attempt is not counted.

| Product | Local suite | Review | Remaining final work |
| --- | --- | --- | --- |
| Anchor |54tests, real PostgreSQL/process faults | Coordinator and live settlement | Standard passed |
| Strata |79tests, MVCC/corruption/crash | Descriptor/format findings closed |100×5000 passed; corrected standard passed |
| Current |32tests, independent raw-control oracle | Coordinator and stream-lake | RSS fix: matrix passed; million-event profiles pending |
| Meridian |46tests, PostgreSQL constraints/races/reporting | Tenant/history/cost findings closed | Standard passed: 250k journals and 100k statement rows |
| Quarry |37tests, exact historical identities | Bounded input/source race findings closed | Standard passed: 5m originals plus corrections/deletes |
| PyTrace |77tests, CFG/codemod/SARIF | Bounded read findings closed | Standard passed: 250,899 lines, independent cache/closure checks |
| Atlas |40tests, visible scores/ACLs | Judgment audit and code-search | Standard passed: 100k documents and 10k measured queries |
| Proving Ground |103tests, leakage/CAS/serving |58independent closure checks | Standard passed: 250k rows × 40 features, full lifecycle |
| Routecraft |75tests, including canonical-order regression |180independent static+24rolling cases | Exact-optimal control matrix passed; standard rerun pending |
| Resonance |25tests,6,272fixed pitch frames | Reattack/subtick/tempo findings closed | Standard passed: 600 seconds × five measurements |

See [independent review](evidence/INDEPENDENT_REVIEW.md) and each project's acceptance map, case study and operations guide. Counts describe tests actually run; the final evidence will identify exact revisions and exit codes. Local branch coverage for each defined domain core exceeds85%; whole-package coverage is separately reported by each owner.

Routecraft's first full standard run executed all 18 scale scenarios and 90 paired trials, but every paired outcome was a gain. The brief also requires a no-improvement case. That report is preserved as a [superseded attempt](evidence/final/attempts/routecraft-missing-control/coordinator-review.json); a real exact-optimal baseline control and affected compatibility checks now pass, while the standard rerun remains pending. Its runner's passing status does not close this missing requirement.

## Integrations

IN-01 settlement, IN-02 stream-lake and IN-03 code-search passed development-tree runs through separate package environments/public interfaces. All three passed committed source7114e39; they will also rerun on the standard snapshot59443e2 after the Meridian reporting fix. Settlement includes live HTTP effect/process death/retry/reversal. Stream-lake includes revisions1/1/2/1 and historical pin isolation. Code-search includes current/obsolete findings, restricted direct access, hidden-score invariance, merge and revocation.

## Global gates

| Gate | Current evaluation |
| --- | --- |
|G01|Implemented: ten identifiable original cores|
|G02|Passed20fresh-clone locked installations|
|G03|Passed1,136projecttests; standard workload portions pending|
|G04|Passed required local matrix lint/types/tests/build and installed-wheel demos|
|G05|Passed all ten seeded demos in both clean-clone interpreters|
|G06|Independent oracles, actual PostgreSQL/process/filesystem boundaries; review corrections closed|
|G07|Development measurements are labeled; committed standard evidence underway|
|G08|Architecture/decisions/operations/case studies and evidence policy present; final link build pending|
|G09|All three pass clean committed source; newest snapshot rerun pending|
|G10|Selector/failure propagation tests pass locally; real remote workflows observed queued|
|G11|Current's database-free quickstart and reviewer routes runnable locally|
|G12|All ten source implementations and fixes committed/pushed; final workload evidence pending|

Remote CI is a separate observation. Actual public GitHub Actions runs were observed queued, including Meridian source3f2c220; no runner success is inferred. API access returned proxy403; the public-page fallback exposes actual run state. No code license has been selected; no public release/deployment is authorized. Full required suites are Linux-only; other platforms remain unverified. Environment configuration saving and publication are separate from these code gates.

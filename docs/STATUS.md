# Verification status

All ten original implementations exist and have passed local quality, packaging and substantive tests on CPython3.13/3.14. Independent findings have been corrected. Final clean-commit compatibility, standard workloads and integration evidence are being collected; this page does not yet claim whole-portfolio completion.

| Product | Local suite | Review | Remaining final work |
| --- | --- | --- | --- |
| Anchor |54tests, real PostgreSQL/process faults | Coordinator and live settlement | Clean clone, standard |
| Strata |79tests, MVCC/corruption/crash | Descriptor/format findings closed |100×5000 running; clean clone, standard |
| Current |30tests, independent raw-control oracle | Coordinator and stream-lake | Clean clone, million-event profiles |
| Meridian |40tests, PostgreSQL constraints/races | Tenant/history/cost findings closed | Clean clone,250k journals |
| Quarry |37tests, exact historical identities | Bounded input/source race findings closed | Clean clone,5m originals/corrections |
| PyTrace |77tests, CFG/codemod/SARIF | Bounded read findings closed | Clean clone,250k LOC |
| Atlas |40tests, visible scores/ACLs | Judgment audit and code-search | Clean clone,100k documents |
| Proving Ground |103tests, leakage/CAS/serving |58independent closure checks | Clean clone,250k×40 data |
| Routecraft |73full tests before ordering fix;61affected tests both versions after fix |180independent static+24rolling cases | Full updated74tests in clean clone, standard |
| Resonance |25tests,6,272fixed pitch frames | Reattack/subtick/tempo findings closed | Clean clone,600s standard |

See [independent review](evidence/INDEPENDENT_REVIEW.md) and each project's acceptance map, case study and operations guide. Counts describe tests actually run; the final evidence will identify exact revisions and exit codes. Local branch coverage for each defined domain core exceeds85%; whole-package coverage is separately reported by each owner.

## Integrations

IN-01 settlement, IN-02 stream-lake and IN-03 code-search passed development-tree runs through separate package environments/public interfaces. All three require final committed-source reruns. Settlement includes live HTTP effect/process death/retry/reversal. Stream-lake includes revisions1/1/2/1 and historical pin isolation. Code-search includes current/obsolete findings, restricted direct access, hidden-score invariance, merge and revocation.

## Global gates

| Gate | Current evaluation |
| --- | --- |
|G01|Implemented: ten identifiable original cores|
|G02|Local locked installs pass; final fresh-clone matrix pending|
|G03|Local mandatory suites pass; full workload portions pending|
|G04|Local lint/types/tests/build/installed-wheel demos pass; final matrix pending|
|G05|All ten real seeded demos pass locally; clean-clone runs pending|
|G06|Independent oracles, actual PostgreSQL/process/filesystem boundaries; review corrections closed|
|G07|Development measurements are labeled; committed standard evidence underway|
|G08|Architecture/decisions/operations/case studies and evidence policy present; final link build pending|
|G09|All three pass development runs; final immutable reruns pending|
|G10|Selector/failure propagation tests pass locally; real remote workflows observed queued|
|G11|Current's database-free quickstart and reviewer routes runnable locally|
|G12|All ten source implementations committed; remaining evidence/shared docs and final push pending|

Remote CI is a separate observation. Actual public GitHub Actions runs were observed queued, including Meridian source3f2c220; no runner success is inferred. API access returned proxy403; the public-page fallback exposes actual run state. No code license has been selected; no public release/deployment is authorized. Full required suites are Linux-only; other platforms remain unverified. Environment configuration saving and publication are separate from these code gates.

# Experiment, publication, and deployment boundaries

Proving Ground answers two separate questions: what a candidate achieved on a
frozen synthetic dataset, and which verified model a process actually used.
A registry promotion is a deployment request. It does not assert that a serving
process has loaded it or that a generated-data result transfers to real equipment.

## Ownership

| Owner | State and responsibility |
| --- | --- |
| `DatasetVersion` | An owned snapshot of identity, time, feature, and label arrays; schema and content identity. |
| `SplitManifest` | Exact positional memberships, dataset identity, scientific question, and time/entity restrictions. |
| `training.pipeline` | Train-only preprocessing and an estimator; fitted-result data/split/sensor provenance. |
| `ArtifactStore` | Verified serialized snapshots and immutable content-addressed publication. |
| `evaluation` | Predictions from the verified artifact, numerical summaries, slices, and clustered uncertainty. |
| `Registry` | Immutable report binding, frozen policy, serialized generation changes, and audit. |
| `ServingProcess` | In-flight loads, one published snapshot, request capture, and terminal shutdown. |

No package imports a sibling product. NumPy and scikit-learn own numerical
estimation; skops owns serialization; SQLite owns its transactions. The product
owns the lifecycle connecting these boundaries.

## Dataset and split

Each row has an integer ID and asset ID, observation time, feature-availability
times, label-availability time, and a binary six-hour outcome. Times are hours
since the synthetic epoch. Missing feature values are NaN internally and null in
record inference. Required identity, label, and time values cannot be missing.
Parquet loading checks exact physical Arrow types before conversion and verifies
schema and content identity after loading.

Construction copies every input array into independently owned immutable byte
buffers **before** validating the snapshot. A writable caller alias cannot change
its values, and NumPy cannot re-enable writes into the byte buffers. Shape, dtype,
and strides are also checked because NumPy permits altering array metadata even
on read-only storage. Content hashes are recomputed from actual arrays; there is
no cached digest that could outlive an altered array view. Construction does not
provide an atomic snapshot of several independently changing external producers;
callers must finish producing arrays before passing them in.

The temporal question is future observations of an existing fleet, so asset IDs
may overlap. For observation-time quantiles `v=0.6` and `t=0.8`, and embargo `e`:

| Partition | Membership rule |
| --- | --- |
| train | `label_available_at < v` |
| validation | `observed_at >= v + e` and `label_available_at < t` |
| test | `observed_at >= t + e` |

The default embargo is two hours. Equality at a label boundary is purged; rows
in purge/embargo gaps are deliberately unused. A separate deterministic hash of
asset ID allocates entity holdouts into 60/20/20 groups. Those groups are disjoint
and answer unseen-asset generalization rather than future forecasting. Validation
checks supplied memberships for overlap, bounds, and the declared restrictions;
it does not prove that a person selected the policy before examining outcomes.

Availability checks reject a declared future offset, a declared label-derived
feature, or an actual feature availability later than its observation. They
cannot discover an undisclosed causal relationship in a seemingly available
sensor. Synthetic generation is not evidence about real fleet performance.

## Fit, serialize, evaluate

The median imputer, missing-value indicators, retained empty features, standard
scaler, and classifier are fitted as one pipeline using only training indices.
`TrainingResult` records the dataset, split, sensor order, training-row digest,
and preprocessing identifier. Publication refuses different data/split/sensor
arguments before staging. These records prevent accidental substitution within
the supported fitter; they do not authenticate arbitrary in-process Python code.

The persisted archive is the evaluation boundary. The public function is:

```python
evaluate(store, data, split, artifact_digest, role="validation", seed=1729)
```

It loads and verifies that artifact, checks its data/split/sensor binding, then
scores the loaded pipeline. It accepts no separate fitted pipeline. Mutating or
replacing the original training object cannot substitute another model's
statistics. This matters because skops can write different bytes for the same
semantic fit; serializing the caller again is not a reliable equality test.

Publication proceeds in this order:

1. Serialize into a unique `.stage-*` directory and reject unreviewed types.
2. Build a manifest binding actual model bytes to run, data, split, ordered
   sensors, estimator, serialization format, and exact persistence-library versions.
3. Deserialize the staged bytes through the same structural and inference
   checks used on load. Supported classes alone do not authorize malformed state.
4. Synchronize model and manifest files, then the stage directory entries.
5. Rename into the manifest identity and synchronize the store directory.

Existing identical destinations must verify; they are not overwritten. A crash
before rename leaves an unpublished stage. A crash after rename can leave an
unreferenced immutable artifact. Registration happens separately and cannot
reference an unpublished stage through the normal API. The supplied staging
cleanup requires exclusive ownership and never deletes published directories.

A loader bounds archive expansion, checks its exact bytes against the manifest,
reviews types, enforces step order/preprocessing/feature count/classifier family,
and probes finite and missing inputs. Content hashes establish integrity, not
permission to load arbitrary executable objects. The type allowlist is explicit;
there is no model-upload, pickle, or arbitrary plugin interface.

## Numerical evidence

The report contains average precision (named `pr_auc`), ROC-AUC, Brier score,
counts/class balance, ten calibration bins, fixed asset-modulo and missingness
slices, and asset-cluster bootstrap uncertainty. PR/ROC discrimination is
undefined for a one-class partition. Calibration bins are left-closed and
right-open except that probability 1 belongs in the last bin. Small slices are
flagged; they do not silently become promotion evidence.

`evaluation/bootstrap.py` orders distinct scores once. A draw samples whole
assets with replacement and converts the draw into asset multiplicities. Row
weights then produce positive and total counts at each tied-score threshold.
No duplicate-row matrix or repeated score ordering is needed. The
[numerical contract](EVALUATION.md) derives this calculation and its work bound.
The seed, algorithm, score-group count, and both defined and undefined draw
counts are retained. Percentiles are conditional on draws containing both
classes. One asset can give a degenerate interval; the gate does not impose a
minimum number of independent assets.

The default gate requires at least 100 validation observations, ten per class,
AP at least 0.35, ROC-AUC at least 0.65, and Brier at most 0.20. It rejects
undefined/nonfinite metrics and inconsistent counts. It does not gate on bootstrap
intervals or estimate uncertainty across new fleets. Candidate selection uses
validation evidence; the staged CLI permits descriptive test evaluation only
after that candidate has appeared in accepted deployment history.

## Registry commit boundary

Registry files retain SQLite application ID 1347430193 and schema version 1.
The table layout did not change when the evaluation contract changed: current
reports are schema 2, and the frozen policy version is
`validation-artifact-v2`. Legacy `validation-v1` policies are audit-only.
Opening them for writes is refused even when explicitly requested. Historical
reports remain readable through `Registry.open_read_only`; connections use
SQLite `mode=ro` plus `query_only`, and mutation methods reject immediately.
Policy mismatch is checked before writable initialization pragmas or DDL.

Registration serializes the supplied nested report once. Its stored bytes,
SHA-256 identity, returned `ModelVersion`, and idempotent retry comparison all
refer to that one snapshot, even if the caller subsequently updates a metrics
dictionary. An artifact can bind to only one immutable evaluation in a registry.
Submitted reports and the local registry API are trusted application inputs;
hashes do not independently prove that a manually submitted statistic is true.

Promotion uses a fresh connection and `BEGIN IMMEDIATE`. It checks the frozen
policy, stored report integrity and candidate/data/split binding, expected
current generation, and artifact integrity. Rollback additionally requires a
previous deployment of its target. An accepted audit row and deployment row
commit together. A rejection commits only its audit row, then raises
`PromotionRejected`. An unknown model is an invalid request, not a candidate
policy decision. All write connections use foreign keys and FULL synchronization.

A process exit before COMMIT leaves neither an accepted deployment nor its audit
row. Exit after COMMIT can lose the response while leaving both durable; retrying
with the old expected generation must reject. A rejected decision has its own
commit boundary and cannot create a deployment. The crash tests exercise real
SQLite writes and abrupt child exits at these positions. They do not emulate
all filesystem or hardware power-loss behavior.

Legacy reevaluation reads existing artifacts into a fresh registry. It records
old/new report identities, model-version mapping, gate failures, and unreadable
artifacts. It carries no deployment or old audit decisions into the new registry.
Old files retain their historical meaning. `ServingProcess` also refuses a
legacy policy even when given an explicit read-only registry handle; audit-only
access cannot start legacy serving. The [runbook](OPERATIONS.md) shows
how to inspect and adopt the new target without replacing them.

## Serving ownership

Load work occurs outside the snapshot lock. Concurrent refresh calls for one
generation share one load attempt and its result. Another generation can load
independently, allowing a rollback to progress while an old loader is stalled.
Failures do not become permanent retry caches: a later explicit refresh retries.
There is no global admission limit across many different simultaneous generations;
the local API's thread pool and operator usage remain capacity limits.

Before publishing a candidate, the process reacquires its lock, checks terminal
state and the authoritative requested generation, and refuses obsolete loads.
The generation is distinct from model version: rollback can apply model 1 at
generation 3. Each prediction captures a pipeline/artifact/model/applied-generation
snapshot once and retains it through parsing and inference. An older in-flight
prediction can finish after a swap with its original, correct metadata.

Readiness reads requested generation while holding the publication lock, so a
new snapshot cannot be paired with an older captured request. It reports pending
or failed loading separately from the applied snapshot. A registry change just
after that observation is a normal asynchronous transition, not a global
transaction over SQLite and every serving process.

`close()` is terminal and idempotent. It releases the active snapshot, wakes
waiting refresh calls, and prevents late loads from publishing. A prediction
that already captured a snapshot can finish. Python cannot forcibly cancel an
arbitrary loader thread; its temporary candidate is released when it returns.
The API lifespan closes the process before cancelling the watcher, since
cancelling `asyncio.to_thread` does not stop its worker. Create a new
`ServingProcess` for a new lifespan.

Requests are limited to 2 MiB and 1–1000 records with exact sensor keys. Null is
explicit missingness; booleans, strings, NaN, and infinity are refused. Body
limits count actual streamed bytes before dispatch. Validation responses omit
input values. The CLI binds loopback; no authentication is supplied.

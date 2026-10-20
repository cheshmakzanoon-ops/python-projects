# Design decisions

## Evaluate persisted content

An evaluation must answer what the published model predicts. Previously the
caller supplied both a fitted result and an artifact digest. Those arguments
could disagree: a strong logistic result authorized a published prior classifier
in the reproduced baseline failure. Matching the report's digest to the manifest
only checked the false attribution consistently.

The evaluator now loads the verified artifact and scores that pipeline. The
extra deserialization is intentional. Re-serializing a caller pipeline would
not prove equality because skops archives can differ between saves. A manifest
or a report hash is not a signature from an independent trusted evaluator;
manual report submission remains a trusted local API.

## Version evidence without rewriting history

Changing evaluator code alone cannot repair reports already accepted under the
old contract. Reports are now schema 2 and the frozen policy identity is
`validation-artifact-v2`. Numeric demonstration thresholds remain the same.
SQLite's table format remains version 1 because its structural schema did not
change. Report/decision semantics have their own explicit versions.

Legacy policies are read-only even when an operator explicitly supplies one.
Historical reports and decisions retain their original identity and meaning.
Reevaluation creates a fresh registry, preserves an old/new mapping, exposes
unreadable models and gate failures, and requests no deployment. A `--registry`
selector lets operators inspect, train, promote, and serve that target while
keeping the source registry intact. It does not relocate its shared model store.

## Own dataset buffers

Setting `array.flags.writeable = False` on a caller-owned view does not freeze
its writable base. Dataset construction now copies arrays into immutable byte
buffers before validating them. This costs a full dataset copy and hashing still
reads the actual content; the benefit is stable values through ordinary aliases.
A cached digest would need to account for NumPy's mutable shape, dtype, strides,
and other state. It is deliberately avoided. The recorded layout rejects common
metadata mutations, including zero-stride views that otherwise preserve shape
and dtype while changing observed values.

The data producer must finish constructing its arrays before calling the
constructor. Copying several independent concurrent producers is not a substitute
for their own snapshot protocol. In-process Python objects are not a sandbox
against code intentionally bypassing their contracts.

## Freeze membership and the scientific question

Random row splitting would overstate future forecasting quality for correlated
asset observations. Temporal purge and embargo enforce label availability across
boundaries; entity holdout asks a different unseen-asset question. Neither policy
solves the other question. Membership, data identity, boundaries, and question
are explicit so reviewers can inspect what was estimated.

The imputer, missingness indicators, scaler, and classifier are one fitted
pipeline. Independent held-out-value tests check that its preprocessing learns
only from training rows. Publication carries the fit's data/split/sensor order
and rejects inconsistent caller arguments.

## Asset multiplicities instead of duplicate rows

Cluster bootstrap must sample whole assets. Expanding rows repeated work and
memory, and searching the complete dataset separately for every asset added
`O(nU)` setup. The revised algorithm prepares asset and tied-score indices once,
then changes only asset multiplicities. Its per-draw work is linear in rows,
assets, and score groups. Exact tiny threshold models protect tie handling and
absent-class behavior independently of NumPy/scikit-learn implementation details.

The interval remains conditional on both classes being present. Undefined draws
are counted explicitly rather than silently described as unconditional evidence.
A stricter scientific policy might require a minimum number of independent
assets or use a different estimand. That would change the declared approval
question and requires a new frozen policy, rather than a quiet numerical tweak.

## Separate semantic and byte identity

Experiment identity covers data/split/source/lock/preprocessing/estimator/
hyperparameters/seed. Timestamps and retry IDs belong to separate attempts.
Each actual skops archive has a content identity that may differ across repeated
saves. Numerical reproducibility means predictions match at absolute tolerance
`1e-12` for the declared fixtures, not universal byte equality or portability
across arbitrary library versions.

Only reviewed built-in median-imputer/scaler plus prior/logistic/tree pipelines
are supported. `numpy.dtype` and sklearn's native decision-tree storage are
explicit allowlist additions. Unknown classes are never automatically trusted.
The publication path validates the serialized snapshot before making it visible;
the loader repeats those checks at use. This is a constrained persistence
contract rather than arbitrary-model sandboxing.

## SQLite owns deployment decisions

A filesystem current-model pointer cannot safely express competing promotions,
rejection audit, or rollback history. SQLite's `BEGIN IMMEDIATE` serializes the
expected-generation comparison and accepted deployment/audit writes. A rejected
known candidate commits its audit without changing deployment. After an
acknowledgement is lost, the operator observes current state before making a new
decision; blindly retrying an old generation is intentionally rejected.

Registration captures canonical report bytes once so stored identity and returned
metadata cannot disagree when caller-owned dictionaries change. Immutable
historical model/evaluation binding is preserved: a new evaluation goes into a
new registry, rather than replacing one in place. Real child-process exits test
the database commit boundaries; mocks cannot establish SQLite recovery behavior.

## One load per generation; snapshots outlive publication

Same-generation refresh calls share one load and result. A separate newer
generation may load while an old loader stalls, preserving the ability to apply
a rollback. This permits concurrent work across distinct generations rather than
pretending Python can forcibly cancel arbitrary loaders. Global admission control
and remote fleet coordination are outside this local service's contract.

Prediction captures a strong reference to one pipeline and all its metadata.
Snapshot publication and readiness observation share a lock; fitting and
inference do not hold that lock. Closing is terminal, wakes waiters, and prevents
late publication. Already captured predictions may finish. API shutdown closes
before cancelling the watcher because cancellation of `to_thread` leaves the
worker running. A fresh process object owns a later server lifespan.

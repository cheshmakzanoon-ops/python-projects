# Historical evaluation fixture

`legacy-evaluation-v1.json` was produced by the actual package at
`39d3a8d4be3e8e2e7de85379790d68f5367d6825`, exported with `git archive` and
executed with the project's locked Python 3.14.8 environment. It contains a skops
prior classifier archive, its original manifest, and `sqlite3.Connection.iterdump()`
from the accepted legacy registry. Archive and SQL bytes have separate SHA-256
checksums. SQLite application/schema pragmas are recorded separately because
`iterdump()` omits them. Tests reconstruct the database without requiring Git.

The baseline generated 5,000 rows, 12 sensors and 50 assets with seed 1729,
froze the default temporal split, and fitted prior and logistic pipelines. It
published the prior but called the old evaluator with the logistic result and
the prior's digest. The resulting schema-v1 report claimed AP 0.842070 and ROC
0.917735 for a model whose actual values are AP 0.321667 and ROC 0.5. The old
registry accepted and deployed it at generation 1. Three bootstrap repetitions
were used solely to keep this reproduction small.

The fixture protects the upgrade boundary: old facts and audit remain readable,
legacy policy cannot regain write authority, and reassessment scores the actual
prior bytes into a fresh registry with no deployment. Corrupt artifacts produce
an explicit partial result. This fixture demonstrates a former implementation
failure; the false statistical attribution is intentionally preserved as evidence.
It is not a candidate recommendation or a current quality report.

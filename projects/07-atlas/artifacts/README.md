# Evidence records

`core-baseline-reproductions.json` records 17 deliberately failing regressions
against source extracted from `39d3a8d`, separately from passing acceptance tests.
`query-memory-before.json` and `query-memory-after.json` retain scoped, single-sample
allocation diagnostics and actual dirty source digests; see the
[method and limits](../benchmarks/README.md). `runtime-rebuild.json` records a real
CPython3.14 ->3.13 ->3.14 offline rebuild round trip, preserving source text, ACLs
and group permissions while refusing cross-UCD direct reads. These are focused
development checks, not an immutable release or standard-workload measurement.

`development-ci.json` and `development-quality.json` are actual local development
runs. They record the tested source digest and `source_dirty=true`; they do not
claim to test their own later artifact commit. Large state is under ignored
`.local/`. Final committed evidence is generated separately
from an immutable clean clone. Per-query failures are preserved rather than
removed from the quality report.

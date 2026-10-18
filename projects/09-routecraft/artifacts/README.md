# Hand-checkable generated sample

`tiny-instance.json` and `tiny-plan.json` describe the actual directed tour
0→1→2→3→0, whose four arcs each cost two. `tiny-routes.svg` and
`tiny-timeline.svg` were rendered from independent verification of that plan.
`sample-manifest.json` records exact input/output hashes and the measured dirty
development snapshot. Reproduce through `pp_routecraft.fixtures.tiny()`,
`solve(instance, SearchBudget(0))`, `verify`, and `reporting.report.render`.
These samples are presentation artifacts, not final immutable release evidence.

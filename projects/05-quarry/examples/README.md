# Device fixture

`devices.ndjson` creates two measurements on January 1. `correction.ndjson` moves sensor-1 to January 2 with a corrected value and deletes sensor-2 using version 2. Ingest them in that order and query daily: the only group is January 2, count 1, total 22. Reingesting either immutable file is idempotent and does not resurrect sensor-2. All examples are synthetic, original fixtures; no third-party data is included.

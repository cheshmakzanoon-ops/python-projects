# License and provenance

No code license existed in the starting repository, and the owner has not selected one. The recommendation is to choose a permissive license such as MIT after reviewing the intended distribution and dependency obligations. This is a recommendation, not a license grant. Package metadata must not invent a license identifier.

Third-party Python distributions retain their own licenses; exact versions and transitive dependencies are recorded in independent `uv.lock` files. The implementation does not vendor those dependencies. Default fixtures and demonstrations should use original synthetic data and authored source/audio rather than copied assets. Project-specific `docs/THIRD_PARTY.md` documents describe algorithm references, datasets, and redistribution restrictions. Technical references are collected in the master execution brief; citation does not imply copying an implementation or endorsement.

The root CI uses actions/checkout v4.2.2 at `11bd71901bbe5b1630ceea73d27597364c9af683` and actions/upload-artifact v4.6.2 at `ea165f8d65b6e75b540449e92b4886f43607fa02`. PostgreSQL demo images use the official postgres repository; the development baseline pulled during bootstrap was postgres:17, digest `sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3`. Its included software remains subject to its own notices.

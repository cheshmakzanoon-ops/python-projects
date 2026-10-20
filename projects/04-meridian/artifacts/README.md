# Sample output

`demo-development-snapshot.json` records a local development demonstration. Its
source commit, content hashes, and dirty flag identify the exact measured input.
It illustrates the report format; it does not verify later source revisions.

The CLI writes full JSON and HTML reports to a caller-selected owned directory.
Generated bulk output remains outside the source tree. Historical committed-source
verification is indexed in [repository evidence](../../../docs/evidence/README.md).
This artifacts directory is excluded from source digests to avoid self-reference.

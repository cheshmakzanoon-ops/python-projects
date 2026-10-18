# Provenance and licensing

All default data are generated from a recorded integer seed. No downloaded
dataset, copied implementation, model, audio, or icon is included. The core uses
Python's standard library. SQLite is used only by a comparison workload.

Architecture references: [LevelDB implementation notes](https://github.com/google/leveldb/blob/main/doc/impl.md)
for LSM tables/manifests; [SQLite atomic commit](https://sqlite.org/atomiccommit.html)
for the distinction between process failure and broader storage failure testing.
These are conceptual influences, not incorporated code.

Development dependencies and their exact releases are recorded in `uv.lock`:
pytest (MIT), pytest-cov (MIT), coverage.py (Apache-2.0), Hypothesis (MPL-2.0),
Ruff (MIT), mypy (MIT), Hatchling (MIT), with transitive dependency metadata
available in the installed distributions. No third-party source is vendored.
The repository owner has not selected a code license at implementation time;
package metadata deliberately does not invent an SPDX license. The owner should
choose an appropriate license before inviting reuse or registry publication.

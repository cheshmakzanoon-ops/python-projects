# Provenance and dependencies

All default device measurements, maintenance-like nullable firmware metadata and event histories are generated locally from the committed seeded generator. They are synthetic fixtures with no personal information, external datasets, pretrained models, audio, icons or copied implementation excerpts. No external data redistribution permission is required.

PyArrow (Apache-2.0) supplies Arrow/Parquet serialization. DuckDB (MIT) supplies relational execution. SQLite comes through the Python standard library and is public domain; CPython uses the Python Software Foundation license. Development tools include pytest (MIT), Hypothesis (MPL-2.0), mypy (MIT), Ruff (MIT), hatchling (MIT), uv (MIT OR Apache-2.0); exact resolved versions are in uv.lock. Dependency license statements describe upstream projects and do not grant a license to this repository's own code.

The repository started without an owner-selected code license. No license identifier has been invented in package metadata. Recommend that the owner explicitly choose a license (for example MIT or Apache-2.0) before marketing reusable third-party distribution terms. Building/testing the local portfolio continues independently of that choice.

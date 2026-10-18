# Third-party and data provenance

| Asset | Source and license/permission | Modification | Pin |
| --- | --- | --- | --- |
| SARIF 2.1.0 official schema | OASIS SARIF TC, https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json ; OASIS repository policies and schema distribution terms; upstream notice retained in OASIS_LICENSE.txt | Unmodified JSON | SHA-256 `c3b4bb2d6093897483348925aaa73af03b3e3f4bd4ca38cef26dcb4212a2682e` |
| Labeled synthetic service fixtures | Original repository-authored examples; no external code/data | Contextual, Unicode, expression and import-alias variants generated from reviewed cases | `tests/fixtures/labeled/labels.json`; report corpus SHA-256 |
| Trusted API migration fixture | Original `src/pp_pytrace/trusted_api.py` version 1 | None outside reviewed source | Literal SHA-256 in MigrationManifest.trusted |
| Standard 250,880-line corpus | Deterministic concatenation/replication of original synthetic fixtures, no network download | Ten reviewed fixtures/chunk | Dataset content SHA-256 in each benchmark |

The corpus deliberately includes no external service implementation, private input, scraped repository, model or licensed dataset. Default demos need no account or credentials. The project code license remains unchosen by the repository owner; no SPDX identifier has been invented. The owner should choose an explicit code license before implying redistribution permission for the original work.

Runtime dependencies: LibCST (MIT), jsonschema (MIT), and their resolved dependencies; exact distributions and transitive versions are in uv.lock and each distribution retains its own license metadata. Development dependencies include pytest (MIT), Hypothesis (MPL-2.0), Ruff (MIT), mypy (MIT), Hatchling (MIT) and coverage.py (Apache-2.0). Dependencies are installed from upstream distributions, not copied into our implementation. The OASIS upstream license/policy notice is preserved as `docs/OASIS_LICENSE.txt`; OASIS specification terms are distinct from a blanket license of this portfolio.

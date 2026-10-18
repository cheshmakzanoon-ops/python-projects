# Shared change request PY-SHARED-001

Requester: A06 / PyTrace

Shared path: portfolio.toml

Concrete proposed change: set PyTrace default_python to `3.14.8`; keep required_python_versions including `3.13.16` and `3.14.8`.

Reason and affected command/API: both interpreters pass the full 77-test suite and 3.14 passes strict Ruff/mypy; .python-version now selects 3.14.8 after required evaluation.

Compatibility impact: no runtime API/schema change; 3.13 remains supported. The product remains independent and requires no service or secret.

Suggested verification: run the root dispatcher setup/check/demo commands with the updated entry and each explicit interpreter CI matrix job.

Coordinator integration uses `python -m pp_pytrace.cli analyze ROOT --format json --output REPORT`, with the stable versioned diagnostic schema documented in OPERATIONS. No Atlas import/dependency is introduced.

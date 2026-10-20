"""The same contract drives CI, development commands and packaging diagnostics."""

from copy import deepcopy
from pathlib import Path

import pytest
from catalog import checkout_problems, load_projects, resolve_python

ROOT = Path(__file__).resolve().parents[2]


def test_declared_projects_match_their_actual_package_contracts():
    for project in load_projects(ROOT):
        assert checkout_problems(project, ROOT) == []
        assert resolve_python(project, None) == project["default_python"]
        for pin in project["required_python_versions"]:
            assert resolve_python(project, pin.rsplit(".", 1)[0]) == pin


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("required_python_versions", ["3.13", "3.14"], "patch"),
        ("default_python", "3.15.0", "default_python"),
        ("test_arguments", "pytest --collect-only", "string list"),
        ("demo_module", "pp_strata.cli", "owning package"),
        ("package", "pp_strata", "duplicate package"),
        ("default_port", True, "TCP port"),
    ],
)
def test_invalid_contract_fails_before_task_dispatch(monkeypatch, field, value, error):
    import catalog

    projects = deepcopy(load_projects(ROOT))
    projects[0][field] = value
    if field == "package":
        projects[0]["demo_module"] = f"{value}.cli"
    monkeypatch.setattr(
        catalog.tomllib,
        "load",
        lambda stream: {
            "schema_version": 1,
            "uv_version": "0.12.23",
            "projects": projects,
        },
    )
    with pytest.raises(ValueError, match=error):
        load_projects(ROOT)


def test_unsupported_python_fails_without_silently_upgrading_environment():
    with pytest.raises(ValueError, match="unsupported interpreter"):
        resolve_python(load_projects(ROOT)[0], "3.15")

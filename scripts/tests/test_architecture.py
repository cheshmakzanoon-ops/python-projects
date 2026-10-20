"""Public exchange adapters must never become sibling-source runtime dependencies."""

import pytest
from catalog import load_projects
from check_architecture import check_projects, import_violations


def test_all_production_packages_are_independent():
    assert check_projects(load_projects()) == []


def test_missing_source_cannot_pass_as_an_empty_independent_package(tmp_path):
    project = load_projects()[0]
    assert "missing production source" in check_projects([project], tmp_path)[0]


@pytest.mark.parametrize(
    "source",
    [
        "import pp_anchor.persistence",
        "from pp_anchor import Engine",
        'import importlib as loader\nloader.import_module("pp_anchor.api")',
        'from importlib import import_module as load\nload("pp_anchor")',
        '__import__("pp_anchor")',
        "import projects.anchor",
        "import sys as runtime\nruntime.path.insert(0, '../anchor/src')",
        "from sys import path\npath.append('../anchor/src')",
        "import sys\nsys.path = ['../anchor/src']",
        "import sys\nsys.path[:] = ['../anchor/src']",
        'import importlib.util\nimportlib.import_module("pp_anchor")',
    ],
)
def test_sibling_import_and_path_escape_hatches_fail(source):
    assert import_violations(source, "pp_current", {"pp_current", "pp_anchor"})


def test_own_imports_and_rule_fixture_strings_remain_valid():
    source = """
from pp_current.runtime import Engine
from .pp_anchor import local_name
fixture = 'import pp_anchor'
import sys
current = sys.path.copy()
"""
    assert import_violations(source, "pp_current", {"pp_current", "pp_anchor"}) == []

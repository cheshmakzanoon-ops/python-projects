"""Exercise the actual merge-gate script with failed and skipped CI results."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("selection", "projects", "integrations", "count", "passed"),
    [
        ("success", "success", "success", "20", True),
        ("success", "skipped", "skipped", "0", True),
        ("failure", "skipped", "skipped", "0", False),
        ("success", "failure", "success", "20", False),
        ("success", "success", "failure", "20", False),
        ("success", "success", "cancelled", "20", False),
        ("success", "success", "skipped", "20", False),
        ("success", "success", "skipped", "0", False),
        ("success", "skipped", "success", "0", False),
    ],
)
def test_merge_gate_requires_all_selected_checks(selection, projects, integrations, count, passed):
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    gate = workflow["jobs"]["aggregate"]
    assert set(gate["needs"]) == {"selection", "projects", "integrations"}
    result = subprocess.run(
        ["bash", "-e", "-c", gate["steps"][0]["run"]],
        env={
            **os.environ,
            "SELECTION": selection,
            "PROJECTS": projects,
            "INTEGRATIONS": integrations,
            "COUNT": count,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) is passed, result.stderr

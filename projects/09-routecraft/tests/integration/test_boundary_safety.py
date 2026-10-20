"""Owned report paths and versioned JSON fail without losing constraints or files."""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from pp_routecraft import construct
from pp_routecraft.fixtures import tiny
from pp_routecraft.reporting.report import clean_output, output_directory
from pp_routecraft.reporting.serialization import (
    instance_dict,
    instance_from_dict,
    plan_from_dict,
    read_instance,
    read_plan,
)


@pytest.mark.parametrize("operation", [output_directory, clean_output])
def test_output_rejects_symlinked_ancestor(tmp_path: Path, operation) -> None:
    real = tmp_path / "real"
    real.mkdir()
    owned = output_directory(real / "report")
    plan = owned / "plan.json"
    plan.write_text("preserve me")
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        operation(alias / "report")
    assert plan.read_text() == "preserve me"


@pytest.mark.parametrize("document", ["instance", "plan"])
def test_json_rejects_unknown_fields(document: str) -> None:
    if document == "instance":
        value = json.loads(json.dumps(instance_dict(tiny())))
        value["maximum_route_duration"] = 5
        decode = instance_from_dict
    else:
        plan = construct(tiny())
        assert plan is not None
        value = json.loads(json.dumps(asdict(plan)))
        value["verified"] = True
        decode = plan_from_dict
    with pytest.raises(ValueError, match="unknown"):
        decode(value)


@pytest.mark.parametrize("record", ["stop", "vehicle", "state", "loaded", "route", "visit"])
def test_json_rejects_unknown_nested_fields(record: str) -> None:
    from pp_routecraft.fixtures import new_request

    previous = tiny()
    plan = construct(previous)
    assert plan is not None
    if record in ("route", "visit"):
        value = json.loads(json.dumps(asdict(plan)))
        nested = value["routes"][0]
        if record == "visit":
            nested = nested["schedule"][0]
        decode = plan_from_dict
    else:
        value = json.loads(json.dumps(instance_dict(new_request(previous, plan))))
        if record in ("stop", "vehicle"):
            nested = value[{"stop": "stops", "vehicle": "vehicles"}[record]][0]
        else:
            nested = value["states"][0]
            if record == "loaded":
                nested = nested["loaded"][0]
        decode = instance_from_dict
    nested["unsupported_constraint"] = 1
    with pytest.raises(ValueError, match="unknown"):
        decode(value)


def test_plan_parser_rejects_future_version_before_verification() -> None:
    plan = construct(tiny())
    assert plan is not None
    value = json.loads(json.dumps(asdict(plan)))
    value["schema_version"] = 2
    with pytest.raises(ValueError, match="schema"):
        plan_from_dict(value)


@pytest.mark.parametrize("document", ["instance", "plan"])
def test_json_files_reject_duplicate_object_keys(tmp_path: Path, document: str) -> None:
    if document == "instance":
        value = instance_dict(tiny())
        read = read_instance
    else:
        plan = construct(tiny())
        assert plan is not None
        value = asdict(plan)
        read = read_plan
    text = json.dumps(value)
    path = tmp_path / "input.json"
    path.write_text('{"schema_version":99,' + text[1:])
    with pytest.raises(ValueError, match="duplicate"):
        read(path)


@pytest.mark.parametrize("invalid", ["budget", "instance"])
def test_cli_invalid_solver_input_returns_failure_and_diagnostics(
    tmp_path: Path, invalid: str
) -> None:
    import subprocess
    import sys

    value = instance_dict(tiny())
    if invalid == "instance":
        value = json.loads(json.dumps(value))
        value["stops"][0]["demand"] = 0
    path = tmp_path / "instance.json"
    path.write_text(json.dumps(value))
    output = tmp_path / "output"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pp_routecraft.cli",
            "solve",
            "--instance",
            str(path),
            "--output",
            str(output),
            "--iterations",
            "-1" if invalid == "budget" else "0",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2, result.stderr
    assert json.loads(result.stdout)["status"] == "INVALID_INPUT"
    assert json.loads((output / "result.json").read_text())["diagnostics"]
    assert not (output / "plan.json").exists()


@pytest.mark.parametrize("version", ["", 1, None])
def test_sdk_requires_meaningful_matrix_version(version: object) -> None:
    from dataclasses import replace

    from pp_routecraft import SearchBudget, Status, solve

    instance = replace(tiny(), matrix_version=version)  # type: ignore[arg-type]
    result = solve(instance, SearchBudget(0))
    assert result.status == Status.INVALID_INPUT
    assert "matrix version" in " ".join(result.diagnostics)


def test_replan_invalid_budget_returns_failure_with_diagnostics(tmp_path: Path) -> None:
    import subprocess
    import sys

    from pp_routecraft.fixtures import new_request

    previous = tiny()
    plan = construct(previous)
    assert plan is not None
    expanded = new_request(previous, plan)
    instance_path = tmp_path / "expanded.json"
    previous_path = tmp_path / "previous.json"
    plan_path = tmp_path / "plan.json"
    instance_path.write_text(json.dumps(instance_dict(expanded)))
    previous_path.write_text(json.dumps(instance_dict(previous)))
    plan_path.write_text(json.dumps(asdict(plan)))
    output = tmp_path / "output"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pp_routecraft.cli",
            "replan",
            "--instance",
            str(instance_path),
            "--previous-instance",
            str(previous_path),
            "--previous-plan",
            str(plan_path),
            "--output",
            str(output),
            "--iterations",
            "-1",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2, result.stderr
    assert json.loads(result.stdout)["status"] == "INVALID_INPUT"
    assert json.loads((output / "result.json").read_text())["diagnostics"]
    assert not (output / "plan.json").exists()

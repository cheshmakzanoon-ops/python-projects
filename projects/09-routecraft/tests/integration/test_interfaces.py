"""Public CLI uses installed package, strict JSON, and owned output cleanup."""

import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from pp_routecraft import construct, verify
from pp_routecraft.fixtures import tiny
from pp_routecraft.reporting.report import clean_output, output_directory, render, write_json
from pp_routecraft.reporting.serialization import instance_dict, instance_from_dict, plan_from_dict


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pp_routecraft.cli", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=90,
        env={**os.environ, "MPLCONFIGDIR": str(cwd / "mpl")},
    )


def test_json_roundtrip() -> None:
    instance = tiny()
    candidate = construct(instance)
    assert candidate is not None
    decoded_instance = instance_from_dict(json.loads(json.dumps(instance_dict(instance))))
    decoded_plan = plan_from_dict(json.loads(json.dumps(asdict(candidate))))
    assert decoded_instance == instance
    assert decoded_plan == candidate
    assert verify(decoded_instance, decoded_plan).valid


@pytest.mark.parametrize(
    "payload",
    [[], {}, {"schema_version": 2}, {"schema_version": True}, {"schema_version": 1, "stops": None}],
)
def test_json_invalid(payload: object) -> None:
    with pytest.raises(ValueError):
        instance_from_dict(payload)


def test_demo_verify_replan_cleanup_from_outside_source(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    result = run("demo", "--output", str(output), "--seed", "1729", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    report = json.loads((output / "demo.json").read_text())
    assert report["verified"]
    assert report["rejected_plan_diagnostics"]
    for name in ("routes.svg", "timeline.svg", "replanned-routes.svg", "replanned-timeline.svg"):
        assert "<svg" in (output / name).read_text()
    verified = run(
        "verify",
        "--instance",
        str(output / "replanned-instance.json"),
        "--plan",
        str(output / "replanned-plan.json"),
        cwd=tmp_path,
    )
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["valid"]
    replan_output = tmp_path / "replan-cli"
    replanned = run(
        "replan",
        "--previous-instance",
        str(output / "instance.json"),
        "--previous-plan",
        str(output / "plan.json"),
        "--instance",
        str(output / "replanned-instance.json"),
        "--output",
        str(replan_output),
        "--iterations",
        "5",
        cwd=tmp_path,
    )
    assert replanned.returncode == 0, replanned.stderr
    assert json.loads((replan_output / "result.json").read_text())["status"] == "FEASIBLE"
    (output / "keep-me.txt").write_text("user file")
    cleaned = run("clean-demo", "--output", str(output), cwd=tmp_path)
    assert cleaned.returncode == 0
    assert (output / "keep-me.txt").read_text() == "user file"
    assert not (output / "plan.json").exists()


def test_generate_solve_compare_exact_and_verify_failure(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    assert (
        run(
            "generate", "--output", str(generated), "--customers", "5", "--tight", cwd=tmp_path
        ).returncode
        == 0
    )
    solved = tmp_path / "solved"
    result = run(
        "solve",
        "--instance",
        str(generated / "instance.json"),
        "--output",
        str(solved),
        "--iterations",
        "10",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "FEASIBLE"
    exact = tmp_path / "exact"
    assert (
        run(
            "solve",
            "--instance",
            str(generated / "instance.json"),
            "--output",
            str(exact),
            "--exact",
            cwd=tmp_path,
        ).returncode
        == 0
    )
    comparison = tmp_path / "compare"
    assert run("compare", "--output", str(comparison), cwd=tmp_path).returncode == 0
    assert json.loads((comparison / "result.json").read_text())["reference"]["status"] == "OPTIMAL"
    bad = tmp_path / "bad-plan.json"
    data = json.loads((solved / "plan.json").read_text())
    data["objective"] = [999, 999]
    write_json(bad, data)
    assert (
        run(
            "verify",
            "--instance",
            str(generated / "instance.json"),
            "--plan",
            str(bad),
            cwd=tmp_path,
        ).returncode
        == 1
    )
    missing = run(
        "solve",
        "--instance",
        str(tmp_path / "missing.json"),
        "--output",
        str(tmp_path / "failed"),
        cwd=tmp_path,
    )
    assert missing.returncode == 2


def test_owned_output_refuses_unsafe_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        output_directory(Path("relative"))
    with pytest.raises(ValueError):
        output_directory(Path("/"))
    unowned = tmp_path / "unowned"
    unowned.mkdir()
    (unowned / "mine").write_text("preserve")
    with pytest.raises(ValueError, match="unowned"):
        output_directory(unowned)
    with pytest.raises(ValueError):
        clean_output(unowned)
    owned = output_directory(tmp_path / "owned")
    (owned / "plan.json").symlink_to(unowned / "mine")
    with pytest.raises(ValueError, match="symlink"):
        output_directory(owned)
    with pytest.raises(ValueError, match="symlink"):
        clean_output(owned)
    assert (unowned / "mine").read_text() == "preserve"


def test_invalid_plan_cannot_be_rendered(tmp_path: Path) -> None:
    from pp_routecraft import Plan

    with pytest.raises(ValueError, match="unverified"):
        render(tiny(), Plan((), (0, 0)), tmp_path)


def test_unknown_result_removes_previous_success_artifacts(tmp_path: Path) -> None:
    from pp_routecraft import SearchBudget, solve
    from pp_routecraft.reporting.report import save_result

    output = output_directory(tmp_path / "owned")
    success = solve(tiny(), SearchBudget(0))
    save_result(tiny(), success, output)
    assert (output / "plan.json").exists()
    unknown = solve(tiny(), SearchBudget(0, 0))
    save_result(tiny(), unknown, output)
    assert not (output / "plan.json").exists()
    assert not (output / "routes.svg").exists()
    assert json.loads((output / "result.json").read_text())["status"] == "NO_FEASIBLE_PLAN_FOUND"


def test_unverified_result_json_is_never_published(tmp_path: Path) -> None:
    from dataclasses import replace

    from pp_routecraft import Plan, SearchBudget, solve
    from pp_routecraft.reporting.report import save_result

    output = output_directory(tmp_path / "rejected-output")
    result = replace(solve(tiny(), SearchBudget(0)), plan=Plan((), (0, 0)))
    with pytest.raises(ValueError, match="unverified plan JSON"):
        save_result(tiny(), result, output)
    assert not (output / "plan.json").exists()

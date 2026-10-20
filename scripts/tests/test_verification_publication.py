"""Publication rejects incomplete matrices and outcomes inconsistent with retained tests."""

import hashlib
import json

import pytest
import summarize_verification as publication
from catalog import load_projects


def _write(path, value):
    path.write_text(json.dumps(value))


def _inventory(folder):
    path = folder / "verification.json"
    run = json.loads(path.read_text())
    run["artifacts"] = [
        {
            "path": item.relative_to(folder).as_posix(),
            "bytes": item.stat().st_size,
            "sha256": hashlib.sha256(item.read_bytes()).hexdigest(),
        }
        for item in folder.rglob("*")
        if item.is_file() and item != path
    ]
    _write(path, run)


@pytest.fixture
def runs(tmp_path, monkeypatch):
    projects = load_projects()[:2]
    monkeypatch.setattr(publication, "load_projects", lambda: projects)
    folders = []
    for version in ("3.13.16", "3.14.8"):
        folder = tmp_path / version
        folder.mkdir()
        for project in projects:
            slug = project["slug"]
            report = dict.fromkeys(
                ("source_content_sha256", "lockfile_sha256", "root_contract_sha256"), "a" * 64
            )
            report.update(
                source_commit="b" * 40,
                project=slug,
                interpreter=version,
                status="passed",
                source_dirty=False,
                source_unchanged_after=True,
                source_inputs=["source.py"],
                root_contract_inputs=["scripts/portfolio.py"],
                python_dispatcher="3.12.14",
                os="Linux",
                verified_at_utc="2026-10-20T00:00:00+00:00",
                checks=[],
            )
            for task in ("check", "demo", "benchmark"):
                log = f"{slug}-{task}.log"
                (folder / log).write_text("completed")
                check = {
                    "command": ["/host/bin/python", "scripts/portfolio.py", task, slug],
                    "exit_code": 0,
                    "log": log,
                    "seconds": 1.0,
                }
                if task == "benchmark":
                    check["command"] += ["--profile", "ci"]
                if task == "check":
                    junit = f"{slug}.xml"
                    (folder / junit).write_text('<testsuite tests="1"><testcase/></testsuite>')
                    check.update(
                        junit_report=junit,
                        tests={"passed": 1, "failed": 0, "errors": 0, "skipped": 0},
                    )
                report["checks"].append(check)
            _write(folder / f"{slug}-{version}.json", report)
        for name, stages in {
            "settlement": ["meridian"],
            "stream-lake": ["current", "quarry"],
            "code-search": ["pytrace", "atlas"],
        }.items():
            (folder / name).mkdir()
            for stage in stages:
                (folder / name / f"{stage}.log").write_text("completed")
            _write(
                folder / name / "integration.json",
                {
                    "integration": name,
                    "source_commit": "b" * 40,
                    "source_dirty": False,
                    "status": "passed",
                    "stages": [{"project": p, "exit_code": 0} for p in stages],
                },
            )
        _write(
            folder / "verification.json",
            {
                "schema_version": 1,
                "source_commit": "b" * 40,
                "interpreter": version,
                "status": "passed",
                "requested_projects": [p["slug"] for p in projects],
                "requested_checks": ["check", "demo", "benchmark"],
                "benchmark_profile": "ci",
                "integrations": [
                    {"integration": n, "exit_code": 0, "status": "passed"}
                    for n in publication.INTEGRATIONS
                ],
            },
        )
        _inventory(folder)
        folders.append(folder)
    return folders


def test_complete_retained_matrix_publishes_actual_outcomes(runs):
    result = publication.summarize(runs)
    assert result["status"] == "passed"
    assert result["tests"] == {"passed": 4, "failed": 0, "errors": 0, "skipped": 0}
    assert len(result["projects"]) == 4
    assert len(result["integrations"]) == 6
    assert result["projects"][0]["checks"][0]["command"][0] == "python"


@pytest.mark.parametrize(
    "defect",
    [
        "missing_version",
        "duplicate_version",
        "partial_scope",
        "changed_log",
        "skipped_tests",
        "mixed_commit",
        "different_source",
        "missing_stage",
        "failed_process",
        "wrong_command_target",
        "failed_outer_integration",
    ],
)
def test_incomplete_or_contradictory_evidence_cannot_publish(runs, defect):
    folder = runs[1]
    if defect == "missing_version":
        runs.pop()
    elif defect == "duplicate_version":
        runs.append(folder)
    elif defect == "changed_log":
        (folder / "anchor-check.log").write_text("replaced after inventory")
    elif defect == "skipped_tests":
        (folder / "anchor.xml").write_text(
            '<testsuite tests="1" skipped="1"><testcase><skipped/></testcase></testsuite>'
        )
        _inventory(folder)
    elif defect == "partial_scope":
        path = folder / "verification.json"
        run = json.loads(path.read_text())
        run["requested_projects"] = ["anchor"]
        _write(path, run)
    elif defect == "different_source":
        path = folder / "anchor-3.14.8.json"
        record = json.loads(path.read_text())
        record["source_content_sha256"] = "c" * 64
        _write(path, record)
        _inventory(folder)
    elif defect == "failed_process":
        path = folder / "anchor-3.14.8.json"
        record = json.loads(path.read_text())
        record["checks"][0]["process_exit_code"] = 23
        _write(path, record)
        _inventory(folder)
    elif defect == "wrong_command_target":
        path = folder / "strata-3.14.8.json"
        record = json.loads(path.read_text())
        record["checks"][0]["command"][3] = "anchor"
        _write(path, record)
        _inventory(folder)
    elif defect == "failed_outer_integration":
        path = folder / "verification.json"
        record = json.loads(path.read_text())
        record["integrations"][0].update(exit_code=23, status="failed")
        _write(path, record)
    elif defect == "missing_stage":
        path = folder / "stream-lake/integration.json"
        record = json.loads(path.read_text())
        record["stages"].pop()
        _write(path, record)
        _inventory(folder)
    elif defect == "mixed_commit":
        for path in folder.rglob("*.json"):
            record = json.loads(path.read_text())
            if "source_commit" in record:
                record["source_commit"] = "c" * 40
                _write(path, record)
        _inventory(folder)
    with pytest.raises(ValueError):
        publication.summarize(runs)

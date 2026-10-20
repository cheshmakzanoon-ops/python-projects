"""Publish a complete two-interpreter verification record from retained run outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from catalog import load_projects
from test_results import read_junit

INTEGRATIONS = {"settlement", "stream-lake", "code-search"}
CHECKS = {"check", "demo", "benchmark"}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected an object: {path}")
    return value


def _owned(folder: Path, name: str) -> Path:
    path = folder / name
    if (
        path.is_symlink()
        or not path.resolve().is_relative_to(folder.resolve())
        or not path.is_file()
    ):
        raise ValueError(f"missing or unsafe evidence file: {name}")
    return path


def _sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _portable(command: list[str]) -> list[str]:
    result = []
    for index, argument in enumerate(command):
        if index == 0 and Path(argument).is_absolute():
            result.append(Path(argument).name)
        elif "/source/" in argument and Path(argument).is_absolute():
            result.append("$VERIFICATION_COPY/" + argument.split("/source/", 1)[1])
        else:
            result.append(argument)
    return result


def summarize(folders: list[Path]) -> dict[str, Any]:
    """Fail closed on incomplete scope, changed files, or contradictory outcomes.

    Hashes establish consistency of locally retained evidence, not authenticity
    against an actor able to replace both reports and their inventories.
    """
    projects = load_projects()
    expected = {
        (project["slug"], version)
        for project in projects
        for version in project["required_python_versions"]
    }
    versions = {version for _, version in expected}
    commits, contracts = set(), set()
    seen_versions: set[str] = set()
    records: dict[tuple[str, str], dict[str, Any]] = {}
    integrations = []
    sources: dict[str, tuple[str, str]] = {}
    totals = dict.fromkeys(("passed", "failed", "errors", "skipped"), 0)
    for folder in folders:
        run = _read(folder / "verification.json")
        version = run["interpreter"]
        if (
            run["schema_version"] != 1
            or run["status"] != "passed"
            or version not in versions
            or version in seen_versions
            or set(run["requested_projects"]) != {p["slug"] for p in projects}
            or set(run["requested_checks"]) != CHECKS
            or len(run["requested_checks"]) != len(CHECKS)
            or run["benchmark_profile"] != "ci"
        ):
            raise ValueError("expected one complete successful CI-profile run per interpreter")
        seen_versions.add(version)
        commits.add(run["source_commit"])
        artifacts = {}
        for artifact in run["artifacts"]:
            name = artifact["path"]
            path = _owned(folder, name)
            if (
                name in artifacts
                or path.stat().st_size != artifact["bytes"]
                or _sha(path) != artifact["sha256"]
            ):
                raise ValueError(f"duplicate or changed retained artifact: {name}")
            artifacts[name] = artifact["sha256"]
        if {item["integration"] for item in run["integrations"]} != INTEGRATIONS:
            raise ValueError("all three public integrations are required")
        for name in INTEGRATIONS:
            relative = f"{name}/integration.json"
            integration = _read(_owned(folder, relative))
            expected_stages = {
                "settlement": ["meridian"],
                "stream-lake": ["current", "quarry"],
                "code-search": ["pytrace", "atlas"],
            }[name]
            if (
                relative not in artifacts
                or integration["integration"] != name
                or integration["source_commit"] != run["source_commit"]
                or integration["source_dirty"] is not False
                or integration["status"] != "passed"
                or [stage["project"] for stage in integration["stages"]] != expected_stages
                or any(stage["exit_code"] != 0 for stage in integration["stages"])
                or any(f"{name}/{project}.log" not in artifacts for project in expected_stages)
            ):
                raise ValueError(f"invalid public integration record: {name}")
            integrations.append(
                {
                    "integration": name,
                    "interpreter": version,
                    "status": "passed",
                    "record_sha256": artifacts[relative],
                }
            )
        for project in projects:
            slug = project["slug"]
            relative = f"{slug}-{version}.json"
            report = _read(_owned(folder, relative))
            if (
                relative not in artifacts
                or report["source_commit"] != run["source_commit"]
                or report["project"] != slug
                or report["interpreter"] != version
                or report["status"] != "passed"
                or report["source_dirty"] is not False
                or report["source_unchanged_after"] is not True
                or any(check["exit_code"] != 0 for check in report["checks"])
            ):
                raise ValueError(f"invalid clean-source project record: {relative}")
            checks = {}
            for check in report["checks"]:
                command = check["command"]
                if len(command) > 2 and command[1] == "scripts/portfolio.py":
                    task = command[2]
                    if task in checks:
                        raise ValueError(f"duplicate project check: {slug} {task}")
                    checks[task] = check
                if check["log"] not in artifacts:
                    raise ValueError("command log missing from retained inventory")
            if set(checks) != CHECKS:
                raise ValueError(f"missing required project check: {slug}")
            result_file = checks["check"]["junit_report"]
            outcomes = read_junit(_owned(folder, result_file))
            if (
                result_file not in artifacts
                or not outcomes.ready
                or outcomes.as_dict() != checks["check"]["tests"]
            ):
                raise ValueError(f"test outcomes disagree: {slug}")
            for outcome, count in outcomes.as_dict().items():
                totals[outcome] += count
            contracts.add(report["root_contract_sha256"])
            identity = report["source_content_sha256"], report["lockfile_sha256"]
            if slug in sources and sources[slug] != identity:
                raise ValueError(f"different source/lock bytes across interpreters: {slug}")
            sources[slug] = identity
            records[slug, version] = {
                **{
                    key: report[key]
                    for key in (
                        "project",
                        "interpreter",
                        "source_commit",
                        "source_content_sha256",
                        "source_inputs",
                        "lockfile_sha256",
                        "root_contract_sha256",
                        "root_contract_inputs",
                        "source_dirty",
                        "source_unchanged_after",
                        "python_dispatcher",
                        "os",
                        "verified_at_utc",
                        "status",
                    )
                },
                "raw_record_sha256": artifacts[relative],
                "tests": outcomes.as_dict(),
                "checks": [
                    {
                        **check,
                        "command": _portable(check["command"]),
                        "log_sha256": artifacts[check["log"]],
                    }
                    for check in report["checks"]
                ],
                "junit_sha256": artifacts[result_file],
            }
    if set(records) != expected or len(commits) != 1 or len(contracts) != 1:
        raise ValueError("incomplete matrix or mixed source/shared-contract revisions")
    return {
        "schema_version": 1,
        "source_commit": next(iter(commits)),
        "root_contract_sha256": next(iter(contracts)),
        "status": "passed",
        "scope": "All ten products on both declared Python patches: required checks, installed-wheel demos, public demos, CI-profile workloads, and all three public integrations per interpreter. Shared tooling and focused/standard measurements are separate records.",
        "publication": "Commands use portable executable names and $VERIFICATION_COPY. Raw record/log/JUnit hashes identify the retained original files. Hashes establish local consistency, not signed authenticity.",
        "projects": [records[key] for key in sorted(records)],
        "integrations": sorted(
            integrations, key=lambda item: (item["integration"], item["interpreter"])
        ),
        "tests": totals,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("publication output must be fresh")
    try:
        result = summarize(args.folders)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Complete matrix: {len(result['projects'])} project records; {result['tests']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Audit locked runtime dependencies against PyPI advisories without installing products."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDITOR = "pip-audit==2.10.1"
EXPECTED_PACKAGES = r"""
import json, sys
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

expected = set()
for line in Path(sys.argv[1]).read_text().replace("\\\n", "").splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    requirement = Requirement(line.split(" --hash=", 1)[0].strip())
    pins = list(requirement.specifier)
    if requirement.url or len(pins) != 1 or pins[0].operator != "==":
        raise ValueError("audit requires exact package versions")
    if requirement.marker is None or requirement.marker.evaluate():
        expected.add((canonicalize_name(requirement.name), pins[0].version))
print(json.dumps(sorted(expected)))
"""


def audit_project(project: dict[str, str], output: Path) -> dict[str, object]:
    slug = project["slug"]
    requirements = output / f"{slug}-requirements.txt"
    report = output / f"{slug}-audit.json"
    export = subprocess.run(
        [
            "uv",
            "export",
            "--locked",
            "--project",
            str(ROOT / project["directory"]),
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements-txt",
            "--output-file",
            str(requirements),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        check=False,
    )
    if export.returncode:
        return {"project": slug, "status": "error", "stage": "locked export"}
    # Evaluate markers in the same pinned interpreter/tool environment used by
    # pip-audit; the standard-library dispatcher needs no packaging dependency.
    expected = {
        tuple(package)
        for package in json.loads(
            subprocess.check_output(
                [
                    "uvx",
                    "--python",
                    "3.14.8",
                    "--from",
                    AUDITOR,
                    "python",
                    "-I",
                    "-c",
                    EXPECTED_PACKAGES,
                    str(requirements),
                ],
                cwd=ROOT,
                text=True,
            )
        )
    }
    result = subprocess.run(
        [
            "uvx",
            "--python",
            "3.14.8",
            "--from",
            AUDITOR,
            "pip-audit",
            "--disable-pip",
            "--require-hashes",
            "-r",
            str(requirements),
            "--format",
            "json",
            "--output",
            str(report),
        ],
        cwd=ROOT,
        check=False,
    )
    # A successful process without a complete report is not audit evidence.
    complete = False
    try:
        data = json.loads(report.read_text())
        dependencies = data["dependencies"]
        complete = isinstance(dependencies, list) and all(
            isinstance(dependency, dict)
            and isinstance(dependency.get("name"), str)
            and isinstance(dependency.get("version"), str)
            and isinstance(dependency.get("vulns"), list)
            and not dependency["vulns"]
            and "skip_reason" not in dependency
            for dependency in dependencies
        )
        if complete:
            reported = {
                (
                    re.sub(r"[-_.]+", "-", dependency["name"]).lower(),
                    dependency["version"],
                )
                for dependency in dependencies
            }
            complete = reported == expected
    except (OSError, ValueError, KeyError, TypeError):
        pass
    # Exit 1 means known vulnerabilities. Service/format failures remain failures,
    # even if a partial report happens to contain no vulnerability rows.
    return {
        "project": slug,
        "status": "passed" if result.returncode == 0 and complete else "failed",
        "exit_code": result.returncode,
        "lockfile_sha256": hashlib.sha256(
            (ROOT / project["directory"] / "uv.lock").read_bytes()
        ).hexdigest(),
        "requirements_sha256": hashlib.sha256(requirements.read_bytes()).hexdigest(),
        "report": report.name if report.is_file() else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Fresh report directory")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("output already exists; choose a fresh report directory")
    output.mkdir(parents=True)
    with (ROOT / "portfolio.toml").open("rb") as stream:
        projects = tomllib.load(stream)["projects"]
    results = []
    for project in projects:
        try:
            result = audit_project(project, output)
        except (OSError, subprocess.CalledProcessError, ValueError) as error:
            result = {"project": project["slug"], "status": "error", "detail": str(error)}
        results.append(result)
        print(f"{project['slug']}: {result['status']}", flush=True)
    (output / "summary.json").write_text(
        json.dumps({"auditor": AUDITOR, "python": "3.14.8", "projects": results}, indent=2) + "\n"
    )
    return int(any(result["status"] != "passed" for result in results))


if __name__ == "__main__":
    sys.exit(main())

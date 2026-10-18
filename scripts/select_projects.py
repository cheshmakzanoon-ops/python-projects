"""Select required CI jobs from trusted Git diff metadata; fail closed to all jobs."""

from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "anchor",
    "strata",
    "current",
    "meridian",
    "quarry",
    "pytrace",
    "atlas",
    "proving-ground",
    "routecraft",
    "resonance",
}


def load_projects(root: Path = ROOT) -> list[dict[str, Any]]:
    with (root / "portfolio.toml").open("rb") as stream:
        projects: list[dict[str, Any]] = tomllib.load(stream)["projects"]
    if len(projects) != 10 or {p["slug"] for p in projects} != EXPECTED:
        raise ValueError("manifest must declare exactly all ten unique projects")
    directories: set[str] = set()
    for p in projects:
        directory = p["directory"]
        resolved = (root / directory).resolve()
        if not resolved.is_relative_to(root.resolve()) or resolved == root.resolve():
            raise ValueError("project path must be a nonempty path within the repository")
        if directory in directories or not p["required_python_versions"]:
            raise ValueError("duplicate directory or empty interpreter matrix")
        directories.add(directory)
    return projects


def select(paths: list[str] | None, projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if paths is None:
        return projects
    selected: set[str] = set()
    for path in paths:
        match = next((p for p in projects if path.startswith(p["directory"] + "/")), None)
        if match is None:
            # Root docs, workflows, integrations, tooling, and unknown paths affect contracts.
            return projects
        selected.add(match["slug"])
    return [p for p in projects if p["slug"] in selected]


def diff_paths(base: str | None, head: str, root: Path = ROOT) -> list[str] | None:
    if not base or set(base) == {"0"}:
        return None
    try:
        # --name-only -z without rename detection includes both sides of a rename.
        result = subprocess.run(
            ["git", "diff", "--no-renames", "--name-only", "-z", base, head, "--"],
            cwd=root,
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return [p for p in result.stdout.decode("utf-8", errors="strict").split("\0") if p]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    projects = load_projects()
    chosen = select(None if args.all else diff_paths(args.base, args.head), projects)
    jobs = [
        {"project": p["slug"], "python": version}
        for p in chosen
        for version in p["required_python_versions"]
    ]
    print(json.dumps({"include": jobs}, separators=(",", ":")))


if __name__ == "__main__":
    main()

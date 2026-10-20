"""Select required CI jobs from trusted Git diff metadata; fail closed to all jobs."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from catalog import ProjectSpec, load_projects

ROOT = Path(__file__).resolve().parents[1]


def select(paths: list[str] | None, projects: list[ProjectSpec]) -> list[ProjectSpec]:
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
        revisions = [
            subprocess.check_output(
                ["git", "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"],
                cwd=root,
                timeout=30,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            for ref in (base, head)
        ]
        # --name-only -z without rename detection includes both sides of a rename.
        result = subprocess.run(
            ["git", "diff", "--no-renames", "--name-only", "-z", *revisions, "--"],
            cwd=root,
            check=True,
            capture_output=True,
            timeout=30,
        )
        return [p for p in result.stdout.decode("utf-8", errors="strict").split("\0") if p]
    except (subprocess.SubprocessError, OSError, UnicodeDecodeError):
        return None


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

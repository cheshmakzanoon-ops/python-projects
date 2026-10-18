"""Hash the explicit source scope used by portfolio verification reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".hypothesis",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "results",
    "htmlcov",
    "artifacts",
    "docs",
}
ROOT_INPUTS = [
    "AGENTS.md",
    "PYTHON_PORTFOLIO_MASTER_EXECUTION_BRIEF.md",
    "portfolio.toml",
    "ruff.toml",
    "scripts",
    "tooling/quality/pyproject.toml",
    "tooling/quality/uv.lock",
    ".github/workflows",
    "integrations",
]


def files_under(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        p
        for p in path.rglob("*")
        if p.is_file() and not EXCLUDED_PARTS.intersection(p.relative_to(path).parts)
    )


def digest(paths: list[Path], root: Path = ROOT) -> tuple[str, list[str]]:
    value = hashlib.sha256()
    names = []
    for path in sorted(set(paths)):
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"source scope escapes repository: {path}")
        name = path.relative_to(root).as_posix()
        data = path.read_bytes()
        value.update(len(name.encode()).to_bytes(8, "big"))
        value.update(name.encode())
        value.update(len(data).to_bytes(8, "big"))
        value.update(data)
        names.append(name)
    return value.hexdigest(), names


def capture(project: Path, root: Path = ROOT) -> dict[str, Any]:
    files = files_under(project)
    files = [
        p
        for p in files
        if not EXCLUDED_PARTS.intersection(p.relative_to(project).parts)
        and p.name not in {".coverage", "coverage.xml"}
    ]
    source, names = digest(files, root)
    contract, contract_names = digest(
        [p for name in ROOT_INPUTS for p in files_under(root / name)], root
    )
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    changed = subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            str(project.relative_to(root)),
            *ROOT_INPUTS,
        ],
        cwd=root,
        text=True,
    ).strip()
    return {
        "source_commit": commit,
        "source_dirty": bool(changed),
        "source_scope": "project",
        "source_content_sha256": source,
        "source_inputs": names,
        "root_contract_sha256": contract,
        "root_contract_inputs": contract_names,
        "lockfile_sha256": hashlib.sha256((project / "uv.lock").read_bytes()).hexdigest(),
        "python_dispatcher": platform.python_version(),
        "os": platform.platform(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    args = parser.parse_args()
    print(json.dumps(capture((ROOT / args.project).resolve()), indent=2))


if __name__ == "__main__":
    main()

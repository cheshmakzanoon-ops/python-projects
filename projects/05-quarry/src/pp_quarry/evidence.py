"""Small source/environment provenance shared by demo and benchmark reports."""

from __future__ import annotations

import hashlib
import platform
import subprocess
from pathlib import Path
from typing import Any

from pp_quarry.sources import file_hash


def provenance(seed: int, profile: str) -> dict[str, Any]:
    package = Path(__file__).resolve().parent
    project = package.parents[1]
    repository = project.parents[1]
    if not (project / "uv.lock").is_file():
        digest = hashlib.sha256()
        for path in sorted(package.rglob("*.py")):
            digest.update(path.relative_to(package).as_posix().encode())
            digest.update(path.read_bytes())
        return {
            "schema_version": 1,
            "project": "quarry",
            "source_commit": "unavailable",
            "source_dirty": None,
            "source_scope": "installed-package",
            "source_content_sha256": digest.hexdigest(),
            "root_contract_sha256": None,
            "lockfile_sha256": None,
            "python": platform.python_version(),
            "os": platform.platform(),
            "cpu": platform.processor() or "unknown",
            "memory_limit_bytes": None,
            "seed": seed,
            "profile": profile,
            "provenance_note": "Installed distribution has no checkout or lockfile; digest covers installed package source. Run source-tree verification for commit/lock provenance.",
        }
    digest = hashlib.sha256()
    selected = [project / "pyproject.toml", project / "uv.lock", project / ".python-version"]
    selected += [
        path
        for name in ("src", "tests", "examples", "benchmarks")
        for path in (project / name).rglob("*")
        if path.is_file() and path.suffix in {".py", ".json", ".csv", ".ndjson"}
    ]
    for path in sorted(selected):
        digest.update(path.relative_to(project).as_posix().encode())
        digest.update(path.read_bytes())
    root_digest = hashlib.sha256()
    for name in (
        "AGENTS.md",
        "ruff.toml",
        "portfolio.toml",
        "scripts/portfolio.py",
        "PYTHON_PORTFOLIO_MASTER_EXECUTION_BRIEF.md",
    ):
        path = repository / name
        if path.exists():
            root_digest.update(name.encode())
            root_digest.update(path.read_bytes())

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repository), *args], text=True, capture_output=True, timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else "unavailable"

    return {
        "schema_version": 1,
        "project": "quarry",
        "source_commit": git("rev-parse", "HEAD"),
        "source_dirty": bool(git("status", "--porcelain", "--", str(project))),
        "source_scope": "project",
        "source_content_sha256": digest.hexdigest(),
        "root_contract_sha256": root_digest.hexdigest(),
        "lockfile_sha256": file_hash(project / "uv.lock"),
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": platform.processor() or "unknown",
        "memory_limit_bytes": None,
        "seed": seed,
        "profile": profile,
        "memory_metadata_note": "OS peak RSS measured; cgroup maximum not inferred",
    }

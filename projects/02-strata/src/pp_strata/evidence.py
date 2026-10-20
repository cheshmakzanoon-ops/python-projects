"""Small source/environment provenance records for reproducible measurements."""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_digest(root: Path, paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def provenance() -> dict[str, object]:
    project = Path(__file__).resolve().parents[2]
    source_checkout = (project / "pyproject.toml").exists() and (project / "src/pp_strata").is_dir()
    if not source_checkout:
        project = Path(__file__).resolve().parent
    repo = project.parents[1]
    paths = [
        p
        for folder in ("src", "tests", "benchmarks", "examples")
        for p in (project / folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc",)
    ]
    paths.extend(project / name for name in ("pyproject.toml", "uv.lock", ".python-version"))
    paths = [p for p in paths if p.exists()]
    if not source_checkout:
        paths = [p for p in project.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    contracts = [
        repo / p
        for p in (
            "ruff.toml",
            "CONTRIBUTING.md",
            "docs/REQUIREMENTS.md",
            "portfolio.toml",
            "scripts/portfolio.py",
        )
        if (repo / p).exists()
    ]
    try:
        revision: str | None = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=project,
            text=True,
            timeout=10,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty: bool | None = bool(
            subprocess.check_output(
                [
                    "git",
                    "status",
                    "--porcelain",
                    "--untracked-files=all",
                    "--",
                    str(project),
                    *(str(p) for p in contracts),
                ],
                cwd=repo,
                text=True,
                timeout=10,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
    except (OSError, subprocess.SubprocessError):
        revision, dirty = None, None
    memory_limit: int | None = None
    cgroup = Path("/sys/fs/cgroup/memory.max")
    if cgroup.exists():
        value = cgroup.read_text().strip()
        if value.isdigit():
            memory_limit = int(value)
    cpu = platform.processor() or "unknown"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.partition(":")[2].strip()
                break
    return {
        "schema_version": 1,
        "project": "strata",
        "source_commit": revision,
        "source_dirty": dirty,
        "source_scope": "project",
        "packaging_context": "source-checkout" if source_checkout else "installed-wheel",
        "source_content_sha256": content_digest(project, paths),
        "root_contract_sha256": content_digest(repo, contracts),
        "lockfile_sha256": sha256(project / "uv.lock") if (project / "uv.lock").exists() else None,
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": cpu,
        "memory_limit_bytes": memory_limit,
        "pid": os.getpid(),
        "digest_inputs": "src/**, tests/**, benchmarks/**, examples/** (excluding __pycache__); pyproject.toml; uv.lock; .python-version"
        if source_checkout
        else "installed pp_strata package files excluding __pycache__; repository/lock metadata may be unavailable",
        "root_digest_inputs": [p.relative_to(repo).as_posix() for p in contracts],
    }

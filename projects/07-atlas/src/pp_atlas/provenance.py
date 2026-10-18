"""Small benchmark provenance, excluding generated reports to avoid self-reference."""

import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path


def digest(paths: list[Path], relative_to: Path) -> str:
    value = hashlib.sha256()
    for path in sorted(paths):
        value.update(str(path.relative_to(relative_to)).encode() + b"\0")
        value.update(path.read_bytes())
    return value.hexdigest()


def provenance(project: Path) -> dict[str, object]:
    root = project.parent.parent
    paths = [
        path
        for directory in ["src", "tests", "benchmarks", "examples"]
        for path in (project / directory).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    paths += [
        p
        for p in [project / "pyproject.toml", project / "uv.lock", project / ".python-version"]
        if p.is_file()
    ]
    contracts = [
        path
        for path in [
            root / "AGENTS.md",
            root / "PYTHON_PORTFOLIO_MASTER_EXECUTION_BRIEF.md",
            root / "ruff.toml",
            root / "portfolio.toml",
            root / "scripts/portfolio.py",
        ]
        if path.is_file()
    ]

    def git(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except OSError:
            return None

    cpu = "unknown"
    try:
        cpu = next(
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        )
    except (OSError, StopIteration):
        pass
    memory: int | None = None
    try:
        raw = Path("/sys/fs/cgroup/memory.max").read_text().strip()
        memory = int(raw) if raw != "max" else None
    except (OSError, ValueError):
        pass
    lock = project / "uv.lock"
    commit = git("rev-parse", "HEAD")
    changes = (
        git(
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            *(str(p) for p in paths + contracts),
        )
        if paths
        else None
    )
    return {
        "source_commit": commit,
        "source_dirty": bool(changes) if changes is not None else None,
        "source_scope": "project",
        "source_content_sha256": digest(paths, project) if paths else None,
        "source_inputs": [str(p.relative_to(project)) for p in sorted(paths)],
        "root_contract_sha256": digest(contracts, root) if contracts else None,
        "root_contract_inputs": [str(p.relative_to(root)) for p in sorted(contracts)],
        "lockfile_sha256": hashlib.sha256(lock.read_bytes()).hexdigest()
        if lock.is_file()
        else None,
        "provenance_note": "checkout source scope captured"
        if lock.is_file() and commit
        else "installed distribution or non-Git copy: unavailable checkout/lock provenance is null",
        "python": sys.version,
        "os": platform.platform(),
        "cpu": cpu,
        "memory_limit_bytes": memory,
        "threads": {
            key: os.environ.get(key, "not-set")
            for key in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]
        },
    }

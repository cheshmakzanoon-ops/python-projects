"""Read-only provenance capture; hashes exclude generated evidence and status."""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
from pathlib import Path
from typing import Any


def digest(paths: list[Path], base: Path) -> str:
    state = hashlib.sha256()
    for path in sorted(paths):
        state.update(path.relative_to(base).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return state.hexdigest()


def metadata(seed: int, profile: str) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    installed = not (root / "pyproject.toml").is_file()
    if installed:
        root = Path(__file__).resolve().parent
    repository = root if installed else root.parents[1]
    source = [
        path
        for folder in ("src", "tests", "benchmarks", "examples")
        for path in (root / folder).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in (".pyc",)
    ]
    if installed:
        source = [
            path
            for path in root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        ]
    else:
        source += [root / "pyproject.toml", root / "uv.lock", root / ".python-version"]
    lockfile = root / "data/uv.lock" if installed else root / "uv.lock"
    contracts = [
        repository / name
        for name in (
            "CONTRIBUTING.md",
            "docs/REQUIREMENTS.md",
            "ruff.toml",
            "portfolio.toml",
            "scripts/portfolio.py",
        )
        if (repository / name).is_file()
    ]
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, capture_output=True, text=True, check=False
    )
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", str(root)],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    memory: int | None = None
    for file in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            memory = int(Path(file).read_text())
            break
        except (OSError, ValueError):
            pass
    cpu = platform.processor()
    if not cpu and Path("/proc/cpuinfo").exists():
        cpu = next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            "unknown",
        )
    return {
        "schema_version": 1,
        "project": "pytrace",
        "source_commit": revision.stdout.strip() if revision.returncode == 0 else None,
        "source_dirty": bool(status.stdout) or revision.returncode != 0,
        "source_scope": "project",
        "provenance_limitation": "Installed wheel has no Git/root contracts; digest covers installed distribution resources"
        if installed
        else None,
        "source_content_sha256": digest(source, root),
        "root_contract_sha256": digest(contracts, repository),
        "lockfile_sha256": hashlib.sha256(lockfile.read_bytes()).hexdigest(),
        "source_digest_inputs": [
            "src/**",
            "tests/**",
            "benchmarks/**",
            "examples/**",
            "pyproject.toml",
            "uv.lock",
            ".python-version",
        ],
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": cpu or "unknown",
        "memory_limit_bytes": memory,
        "seed": seed,
        "profile": profile,
        "parameters": {
            "threads": 1,
            "parser_processes": 1,
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS", "unset"),
        },
        "warmup_runs": 1,
        "measurement_runs": 5,
    }

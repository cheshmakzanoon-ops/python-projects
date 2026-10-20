"""Capture actual source bytes before a workload; generated evidence is excluded."""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from pp_proving_ground.experiments.identity import canonical, file_hash


def _git(project: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=project, check=True, capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def source_digest(project: Path) -> str:
    h = hashlib.sha256()
    files = [project / name for name in ["pyproject.toml", "uv.lock", ".python-version"]]
    for name in ["src", "tests", "benchmarks", "examples"]:
        files += sorted(
            p
            for p in (project / name).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        )
    for path in sorted(files):
        if path.exists():
            h.update(str(path.relative_to(project)).encode())
            h.update(bytes.fromhex(file_hash(path)))
    return h.hexdigest()


def provenance(
    project: Path, profile: str, seed: int, parameters: dict[str, Any]
) -> dict[str, Any]:
    root = project.parent.parent
    root_hash = hashlib.sha256()
    for name in [
        "CONTRIBUTING.md",
        "docs/REQUIREMENTS.md",
        "ruff.toml",
        "portfolio.toml",
        "scripts/portfolio.py",
    ]:
        path = root / name
        if path.exists():
            root_hash.update(name.encode())
            root_hash.update(bytes.fromhex(file_hash(path)))
    memory: int | None = None
    for path in [
        Path("/sys/fs/cgroup/memory.max"),
        Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    ]:
        try:
            value = path.read_text().strip()
            if value.isdigit():
                memory = int(value)
                break
        except OSError:
            pass
    cpu = platform.processor()
    if not cpu and Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    return {
        "schema_version": 1,
        "project": "proving-ground",
        "source_commit": _git(project, "rev-parse", "HEAD"),
        "source_dirty": bool(
            _git(project, "status", "--porcelain", "--", ".", ":!docs", ":!artifacts")
        ),
        "source_scope": "project",
        "source_content_sha256": source_digest(project),
        "root_contract_sha256": root_hash.hexdigest(),
        "lockfile_sha256": file_hash(project / "uv.lock")
        if (project / "uv.lock").exists()
        else None,
        "python": sys.version,
        "os": platform.platform(),
        "cpu": cpu or "unknown",
        "memory_limit_bytes": memory,
        "seed": seed,
        "profile": profile,
        "parameters": parameters,
        "warmup_runs": 1,
        "measurement_runs": 5,
        "thread_configuration": {
            k: os.environ.get(k, "unset")
            for k in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]
        },
    }


def project_directory() -> Path:
    # Installed wheels can use --source-root/PP_SOURCE_ROOT; metadata is never invented.
    override = os.environ.get("PP_PROVING_GROUND_SOURCE_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[3]


def identity_for_source(project: Path) -> tuple[str, str]:
    lock = project / "uv.lock"
    return source_digest(project), file_hash(lock) if lock.exists() else hashlib.sha256(
        canonical("wheel-no-lock")
    ).hexdigest()

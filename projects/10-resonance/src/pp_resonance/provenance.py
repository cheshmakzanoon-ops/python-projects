"""Source-scoped reproducibility metadata; generated evidence is excluded."""

import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path


def digest(paths: list[Path], base: Path) -> str:
    hashed = hashlib.sha256()
    for path in sorted(paths):
        hashed.update(str(path.relative_to(base)).encode())
        hashed.update(b"\0")
        hashed.update(path.read_bytes())
    return hashed.hexdigest()


def metadata(seed: int, profile: str) -> dict[str, object]:
    project = Path(__file__).resolve().parents[2]
    repository = project.parents[1]
    if not (project / "pyproject.toml").exists():
        return {
            "schema_version": 1,
            "project": "resonance",
            "source_commit": None,
            "source_dirty": None,
            "source_scope": "installed-wheel",
            "source_content_sha256": digest(
                list(Path(__file__).parent.rglob("*.py")), Path(__file__).parent
            ),
            "root_contract_sha256": None,
            "lockfile_sha256": None,
            "python": sys.version,
            "os": platform.platform(),
            "cpu": platform.processor(),
            "memory_limit_bytes": None,
            "seed": seed,
            "profile": profile,
            "provenance_note": "Installed wheel: checkout/lock metadata unavailable",
        }
    sources = [
        p
        for p in project.rglob("*")
        if p.is_file()
        and not any(
            part
            in {
                ".venv",
                "dist",
                "artifacts",
                "results",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
                ".hypothesis",
            }
            for part in p.relative_to(project).parts
        )
        and p.name not in {"AGENT_STATUS.md", ".coverage", "coverage.xml"}
    ]
    roots = [
        repository / p
        for p in ["AGENTS.md", "ruff.toml", "portfolio.toml", "scripts/portfolio.py"]
        if (repository / p).exists()
    ]
    try:
        commit: str | None = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository, text=True
        ).strip()
        state = subprocess.check_output(
            ["git", "status", "--porcelain", "--", str(project)], cwd=repository, text=True
        )
        dirty: bool | None = bool(state.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit, dirty = None, None
    cpu = platform.processor()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        cpu = next(
            (
                line.split(":", 1)[1].strip()
                for line in cpuinfo.read_text().splitlines()
                if line.startswith("model name")
            ),
            cpu,
        )
    memory: int | None = None
    for file in (
        Path("/sys/fs/cgroup/memory.max"),
        Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    ):
        if file.exists() and file.read_text().strip().isdigit():
            memory = int(file.read_text().strip())
            break
    return {
        "schema_version": 1,
        "project": "resonance",
        "source_commit": commit,
        "source_dirty": dirty,
        "source_scope": "project",
        "source_content_sha256": digest(sources, project),
        "source_inputs": [str(p.relative_to(project)) for p in sorted(sources)],
        "source_digest_inputs": "all project files excluding caches, dist, artifacts, results, AGENT_STATUS and coverage outputs",
        "root_contract_sha256": digest(roots, repository),
        "root_contract_inputs": [str(p.relative_to(repository)) for p in sorted(roots)],
        "lockfile_sha256": hashlib.sha256((project / "uv.lock").read_bytes()).hexdigest(),
        "python": sys.version,
        "os": platform.platform(),
        "cpu": cpu or "unknown",
        "memory_limit_bytes": memory,
        "seed": seed,
        "profile": profile,
        "threads": {
            name: os.environ.get(name, "unconfigured")
            for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
        },
    }

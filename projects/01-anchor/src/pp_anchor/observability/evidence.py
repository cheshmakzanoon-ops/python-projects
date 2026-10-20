"""Source scope explicitly excludes generated evidence and local runtime state."""

import hashlib
import platform
import subprocess
import sys
from pathlib import Path

from pp_anchor.definitions.model import JSON


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_evidence(seed: int, profile: str, parameters: JSON) -> JSON:
    project = Path(__file__).resolve().parents[3]
    root = project.parents[1]
    digest = hashlib.sha256()
    selected = [project / "pyproject.toml", project / "uv.lock", project / ".python-version"]
    for folder in ("src", "tests", "benchmarks", "examples"):
        selected.extend(
            p
            for p in (project / folder).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        )
    for path in sorted(selected):
        if path.is_file():
            digest.update(str(path.relative_to(project)).encode() + b"\0" + path.read_bytes())
    contracts = hashlib.sha256()
    for name in (
        "CONTRIBUTING.md",
        "docs/REQUIREMENTS.md",
        "portfolio.toml",
        "ruff.toml",
        "scripts/portfolio.py",
    ):
        path = root / name
        if path.exists():
            contracts.update(name.encode() + b"\0" + path.read_bytes())

    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    cpu = platform.processor() or "unknown"
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
    for limit_name in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        limit = Path(limit_name)
        if limit.exists() and limit.read_text().strip().isdigit():
            memory = int(limit.read_text().strip())
            break
    return {
        "schema_version": 1,
        "project": "anchor",
        "source_commit": git("rev-parse", "HEAD"),
        "source_dirty": bool(git("status", "--porcelain", "--", str(project))),
        "source_scope": "project",
        "source_content_sha256": digest.hexdigest(),
        "root_contract_sha256": contracts.hexdigest(),
        "lockfile_sha256": file_hash(project / "uv.lock"),
        "python": sys.version,
        "os": platform.platform(),
        "cpu": cpu,
        "memory_limit_bytes": memory,
        "seed": seed,
        "dataset_id": hashlib.sha256(
            f"anchor-generated-v1:{seed}:{parameters}".encode()
        ).hexdigest(),
        "profile": profile,
        "parameters": parameters,
        "warmup_runs": 1,
        "measurement_runs": parameters.get("measurement_runs", 5),
    }

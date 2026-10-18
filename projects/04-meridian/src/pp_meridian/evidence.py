"""Source and installed-distribution provenance, with explicit unknown metadata."""

import hashlib
import platform
import subprocess
from pathlib import Path


def digest(paths: list[Path], root: Path) -> str:
    checksum = hashlib.sha256()
    for path in sorted(paths):
        checksum.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    return checksum.hexdigest()


def provenance() -> dict[str, object]:
    project = Path(__file__).resolve().parents[2]
    checkout = (project / "uv.lock").is_file() and (project / "src/pp_meridian").is_dir()
    if not checkout:
        project = Path(__file__).resolve().parent
    root = project.parents[1]
    if checkout:
        files = [
            p
            for directory in ["src", "tests", "benchmarks", "examples"]
            for p in (project / directory).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        ]
        files += [project / "pyproject.toml", project / "uv.lock", project / ".python-version"]
    else:
        files = [
            p
            for p in project.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        ]
    contracts = (
        [
            root / p
            for p in ["ruff.toml", "AGENTS.md", "portfolio.toml", "scripts/portfolio.py"]
            if (root / p).is_file()
        ]
        if checkout
        else []
    )
    revision: str | None = None
    dirty: bool | None = None
    if checkout:
        try:
            revision = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=10,
            ).strip()
            dirty = bool(
                subprocess.check_output(
                    [
                        "git",
                        "-C",
                        str(root),
                        "status",
                        "--porcelain",
                        "--",
                        *[str(p) for p in files + contracts],
                    ],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                ).strip()
            )
        except (OSError, subprocess.SubprocessError):
            revision, dirty = None, None
    cpu = platform.processor() or "unknown"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        cpu = next(
            (
                line.partition(":")[2].strip()
                for line in cpuinfo.read_text().splitlines()
                if line.startswith("model name")
            ),
            cpu,
        )
    memory: int | None = None
    cgroup = Path("/sys/fs/cgroup/memory.max")
    if cgroup.is_file() and (value := cgroup.read_text().strip()).isdigit():
        memory = int(value)
    return {
        "schema_version": 1,
        "project": "meridian",
        "source_commit": revision,
        "source_dirty": dirty,
        "source_scope": "project" if checkout else "installed-distribution",
        "packaging_context": "source-checkout" if checkout else "installed-wheel",
        "source_content_sha256": digest(files, project),
        "root_contract_sha256": digest(contracts, root) if checkout else None,
        "lockfile_sha256": hashlib.sha256((project / "uv.lock").read_bytes()).hexdigest()
        if checkout
        else None,
        "digest_inputs": "src/**,tests/**,benchmarks/**,examples/** excluding __pycache__/pyc; pyproject.toml; uv.lock; .python-version"
        if checkout
        else "installed package files excluding __pycache__/pyc",
        "metadata_limitations": None
        if checkout
        else "Installed wheel has no Git checkout or lockfile: revision, dirty state, root inputs, and lock metadata are unavailable; source hash identifies actual installed package files.",
        "root_digest_inputs": [str(p.relative_to(root)) for p in contracts],
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": cpu,
        "memory_limit_bytes": memory,
    }

"""Independently verified JSON and actual route map/timeline rendering."""

import hashlib
import json
import platform
import subprocess
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from pp_routecraft.domain.instance import Plan, RoutingInstance, SolveResult  # noqa: E402
from pp_routecraft.reporting.serialization import instance_dict  # noqa: E402
from pp_routecraft.validation.verifier import verify  # noqa: E402

OWNED_FILES = frozenset(
    {
        ".routecraft-owned",
        "instance.json",
        "plan.json",
        "result.json",
        "routes.svg",
        "timeline.svg",
        "replanned-instance.json",
        "replanned-plan.json",
        "replanned-routes.svg",
        "replanned-timeline.svg",
        "demo.json",
        "benchmark.json",
    }
)


def _validate_output_path(path: Path) -> None:
    if not path.is_absolute() or path == Path(path.anchor):
        raise ValueError("output must be an absolute, nonsymlink, owned directory")
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("refusing symlink output or ancestor")


def output_directory(path: Path) -> Path:
    _validate_output_path(path)
    if path.exists() and not path.is_dir():
        raise ValueError("output is not a directory")
    if path.exists() and any(path.iterdir()) and not (path / ".routecraft-owned").is_file():
        raise ValueError("refusing to overwrite an unowned directory")
    for name in OWNED_FILES:
        if (path / name).is_symlink():
            raise ValueError("refusing symlink in output directory")
    path.mkdir(parents=True, exist_ok=True)
    marker = path / ".routecraft-owned"
    if marker.exists() and marker.read_text() != "pp-routecraft schema=1\n":
        raise ValueError("invalid ownership marker")
    marker.write_text("pp-routecraft schema=1\n")
    return path


def clean_output(path: Path) -> None:
    _validate_output_path(path)
    if not (path / ".routecraft-owned").is_file():
        raise ValueError("clean-demo requires an explicitly owned absolute directory")
    if (path / ".routecraft-owned").read_text() != "pp-routecraft schema=1\n":
        raise ValueError("invalid ownership marker")
    for name in OWNED_FILES:
        target = path / name
        if target.is_symlink():
            raise ValueError("refusing symlink cleanup")
    for name in OWNED_FILES - {".routecraft-owned"}:
        target = path / name
        if target.is_file():
            target.unlink()
    (path / ".routecraft-owned").unlink()
    if not any(path.iterdir()):
        path.rmdir()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def render(instance: RoutingInstance, plan: Plan, output: Path, *, prefix: str = "") -> None:
    report = verify(instance, plan)
    if not report.valid:
        raise ValueError(f"cannot report an unverified plan: {report.errors}")
    positions = {s.id: (s.x, s.y) for s in instance.stops}
    positions[0] = (0.0, 0.0)
    figure, axes = plt.subplots(figsize=(10, 7))
    for route in plan.routes:
        if not route.stops:
            continue
        sequence = (0,) + route.stops + (0,)
        xs, ys = zip(*(positions[j] for j in sequence), strict=True)
        axes.plot(xs, ys, marker="o", markersize=3, label=f"Vehicle {route.vehicle_id}")
        for source, target in zip(sequence, sequence[1:], strict=False):
            a, b = positions[source], positions[target]
            axes.annotate("", xy=b, xytext=a, arrowprops={"arrowstyle": "->", "lw": 0.6})
    for job, (x, y) in positions.items():
        axes.annotate("Depot" if job == 0 else str(job), (x, y), fontsize=7)
    axes.set(
        title=f"Synthetic island routes — {plan.objective[0]} vehicles, {plan.objective[1]} travel units",
        xlabel="Synthetic x coordinate",
        ylabel="Synthetic y coordinate",
    )
    axes.set_aspect("equal", adjustable="datalim")
    if axes.get_legend_handles_labels()[0]:
        axes.legend(fontsize=7, ncol=2)
    figure.tight_layout()
    figure.savefig(output / f"{prefix}routes.svg")
    plt.close(figure)
    figure, axes = plt.subplots(figsize=(12, max(4, len(plan.routes) * 0.35)))
    state_map = {s.vehicle_id: s for s in instance.states}
    for lane, (vid, visits, returned) in enumerate(report.schedules):
        clock = next(v.start for v in instance.vehicles if v.id == vid)
        state = state_map.get(vid)
        for index, visit in enumerate(visits):
            if state and index == len(state.executed):
                if state.time > clock:
                    axes.broken_barh(
                        [(clock, state.time - clock)],
                        (lane - 0.3, 0.6),
                        facecolors="#a8a8a8",
                        hatch="//",
                    )
                clock = state.time
            axes.broken_barh(
                [(clock, max(0, visit.arrival - clock))],
                (lane - 0.3, 0.6),
                facecolors="#7da7d9",
                label="Travel" if lane == 0 and index == 0 else None,
            )
            axes.broken_barh(
                [(visit.arrival, visit.service_start - visit.arrival)],
                (lane - 0.3, 0.6),
                facecolors="#efc86b",
            )
            if visit.departure > visit.service_start:
                axes.broken_barh(
                    [(visit.service_start, visit.departure - visit.service_start)],
                    (lane - 0.3, 0.6),
                    facecolors="#4caa79",
                )
            else:
                axes.plot(visit.service_start, lane, marker="|", markersize=9, color="#4caa79")
            axes.text(visit.service_start, lane + 0.25, str(visit.stop_id), fontsize=6)
            clock = visit.departure
        if visits:
            if state and len(state.executed) == len(visits):
                if state.time > clock:
                    axes.broken_barh(
                        [(clock, state.time - clock)],
                        (lane - 0.3, 0.6),
                        facecolors="#a8a8a8",
                        hatch="//",
                    )
                clock = state.time
            axes.broken_barh(
                [(clock, max(0, returned - clock))], (lane - 0.3, 0.6), facecolors="#7da7d9"
            )
    axes.set(
        yticks=list(range(len(report.schedules))),
        yticklabels=[f"V{vid}" for vid, _, _ in report.schedules],
        xlabel="Integer time units",
        title="Verified service-start schedule, including depot returns",
    )
    axes.legend(
        handles=[
            Patch(facecolor="#7da7d9", label="Directed travel"),
            Patch(facecolor="#efc86b", label="Window waiting"),
            Patch(facecolor="#4caa79", label="Service (tick when duration is zero)"),
            Patch(facecolor="#a8a8a8", hatch="//", label="Delay at actual boundary"),
        ],
        fontsize=7,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=2,
    )
    figure.tight_layout()
    figure.savefig(output / f"{prefix}timeline.svg")
    plt.close(figure)


def save_result(instance: RoutingInstance, result: SolveResult, output: Path) -> None:
    if result.plan is not None and not verify(instance, result.plan).valid:
        raise ValueError("cannot publish unverified plan JSON")
    write_json(output / "instance.json", instance_dict(instance))
    write_json(output / "result.json", asdict(result))
    if result.plan is None:
        for name in ("plan.json", "routes.svg", "timeline.svg"):
            (output / name).unlink(missing_ok=True)
    else:
        write_json(output / "plan.json", asdict(result.plan))
        render(instance, result.plan, output)


def provenance(project: Path) -> dict[str, object]:
    root = project.parent.parent
    installed = not (project / "pyproject.toml").is_file()
    if installed:
        package = Path(__file__).resolve().parents[1]
        package_digest = hashlib.sha256()
        for path in sorted(package.rglob("*")):
            if path.is_file() and (path.suffix == ".py" or path.name == "py.typed"):
                package_digest.update(
                    str(path.relative_to(package)).encode() + b"\0" + path.read_bytes()
                )
        return {
            "source_commit": "unavailable-installed-wheel",
            "source_dirty": None,
            "source_scope": "installed-package",
            "source_content_sha256": package_digest.hexdigest(),
            "root_contract_sha256": None,
            "lockfile_sha256": None,
            "python": platform.python_version(),
            "os": platform.platform(),
            "cpu": platform.processor() or "unknown",
            "memory_limit_bytes": None,
            "provenance_note": "Installed package content hash; outer wheel verification records source commit and lockfile.",
        }
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=project, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--", "."],
                cwd=project,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit, dirty = "unavailable-export", False
    digest = hashlib.sha256()
    inputs = [project / p for p in ("pyproject.toml", "uv.lock", ".python-version", "README.md")]
    for folder in ("src", "tests", "benchmarks", "examples", "docs"):
        inputs.extend(
            p
            for p in (project / folder).rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and p.name != "VERIFICATION.md"
            and "evidence" not in p.parts
        )
    for path in sorted(inputs):
        if path.is_file():
            digest.update(str(path.relative_to(project)).encode() + b"\0" + path.read_bytes())
    root_digest = hashlib.sha256()
    for name in (
        "CONTRIBUTING.md",
        "docs/REQUIREMENTS.md",
        "ruff.toml",
        "portfolio.toml",
        "scripts/portfolio.py",
    ):
        path = root / name
        if path.exists():
            root_digest.update(name.encode() + b"\0" + path.read_bytes())
    lock = project / "uv.lock"
    return {
        "source_commit": commit,
        "source_dirty": dirty,
        "source_scope": "project",
        "source_content_sha256": digest.hexdigest(),
        "root_contract_sha256": root_digest.hexdigest(),
        "lockfile_sha256": hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else None,
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": platform.processor() or "unknown",
        "memory_limit_bytes": None,
    }

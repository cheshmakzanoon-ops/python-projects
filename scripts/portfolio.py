"""Portable dispatcher for ten independent uv projects. No shell interpolation."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import shutil
import signal
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manifest() -> list[dict[str, object]]:
    with (ROOT / "portfolio.toml").open("rb") as stream:
        return tomllib.load(stream)["projects"]


def execute(command: list[str], cwd: Path, timeout: int = 600) -> int:
    print(f"[{cwd.name}] {' '.join(command)}", flush=True)
    environment = os.environ.copy()
    environment.setdefault(
        "UV_CACHE_DIR",
        "/workspace/.cache/uv" if Path("/workspace").exists() else str(Path.home() / ".cache/uv"),
    )
    if Path("/workspace/.python").exists():
        environment.setdefault("UV_PYTHON_INSTALL_DIR", "/workspace/.python")
    cache = ROOT / ".local" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    environment.setdefault("MPLCONFIGDIR", str(cache / "matplotlib"))
    environment.setdefault("XDG_CACHE_HOME", str(cache))
    environment.setdefault("UV_LINK_MODE", "copy")
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        environment[name] = "1"
    try:
        process = subprocess.Popen(
            command, cwd=cwd, env=environment, start_new_session=os.name != "nt"
        )
        try:
            return process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
            raise
        finally:
            # A failed or successful parent may leave descendants alive; demos own their group.
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"Command failed: {error}", file=sys.stderr)
        return 1


def project_task(task: str, project: dict[str, object], profile: str = "ci") -> int:
    directory = ROOT / str(project["directory"])
    # Select one interpreter for the entire task, including builds and wheel checks.
    # Relying on uv's nearest .python-version here can silently disagree with setup.
    interpreter = os.environ.get("PORTFOLIO_PYTHON") or str(project["default_python"])
    base = ["uv", "run", "--locked", "--python", interpreter]
    if not (directory / "uv.lock").exists():
        print(f"{project['slug']}: incomplete: uv.lock missing", file=sys.stderr)
        return 2
    if task == "setup":
        commands = [
            [
                "uv",
                "sync",
                "--locked",
                "--python",
                interpreter,
            ]
        ]
    elif task == "check":
        commands = [
            base + list(project["format_arguments"]),
            base + list(project["lint_arguments"]),
            base + list(project["type_arguments"]),
            base + list(project["test_arguments"]),
            [
                "uv",
                "build",
                "--no-sources",
                "--python",
                interpreter,
            ],
            [
                sys.executable,
                str(ROOT / "scripts/wheel_smoke.py"),
                str(directory),
                str(project["package"]),
                interpreter,
            ],
        ]
    else:
        output = ROOT / ".local" / str(project["slug"]) / ("demo" if task == "clean-demo" else task)
        commands = [
            base + ["python", "-m", str(project["demo_module"]), task, "--output", str(output)]
        ]
        if task != "clean-demo":
            commands[0] += ["--seed", "1729"]
        if task == "benchmark":
            commands[0] += ["--profile", profile]
    for command in commands:
        result = execute(command, directory, 7200 if profile == "standard" else 600)
        if result:
            print(f"{project['slug']}: {task} failed ({result})", file=sys.stderr)
            return result
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "task",
        choices=[
            "list",
            "doctor",
            "setup",
            "check",
            "demo",
            "benchmark",
            "clean-demo",
            "verify-all",
            "docs",
            "integration",
        ],
    )
    parser.add_argument("project", nargs="?")
    parser.add_argument("--profile", choices=["ci", "standard"], default="ci")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    projects = manifest()
    if args.task == "list":
        for project in projects:
            print(f"{project['slug']:16} {project['directory']} [{project['status']}]")
        return 0
    if args.task == "doctor":
        print(f"Python dispatcher: {sys.version.split()[0]}; uv: {shutil.which('uv') or 'MISSING'}")
        missing = [
            str(p["slug"])
            for p in projects
            if not (ROOT / str(p["directory"]) / "uv.lock").exists()
        ]
        if missing:
            print("Incomplete projects: " + ", ".join(missing))
        return int(not shutil.which("uv") or bool(missing))
    if args.task == "verify-all":
        if not 1 <= args.jobs <= 4:
            parser.error("--jobs must be between 1 and 4")
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            results = list(executor.map(lambda p: project_task("check", p), projects))
        return int(any(results))
    if args.task == "docs":
        return execute([sys.executable, str(ROOT / "scripts/check_docs.py")], ROOT)
    if args.task == "integration":
        if args.project not in {"settlement", "stream-lake", "code-search"}:
            parser.error("select settlement, stream-lake, or code-search")
        return execute([sys.executable, str(ROOT / "integrations/run.py"), args.project], ROOT)
    selected = next((p for p in projects if p["slug"] == args.project), None)
    if selected is None:
        parser.error("select a project from `list`")
    return project_task(args.task, selected, args.profile)


if __name__ == "__main__":
    raise SystemExit(main())

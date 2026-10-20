"""Portable dispatcher for ten independent uv projects. No shell interpolation."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import shutil
import signal
import subprocess
import sys
import uuid
from collections.abc import Mapping
from pathlib import Path

from catalog import ProjectSpec, checkout_problems, load_projects, resolve_python
from test_results import read_junit

ROOT = Path(__file__).resolve().parents[1]


def manifest() -> list[ProjectSpec]:
    return load_projects(ROOT)


def execute(
    command: list[str],
    cwd: Path,
    timeout: int = 600,
    *,
    overrides: Mapping[str, str | None] | None = None,
) -> int:
    print(f"[{cwd.name}] {' '.join(command)}", flush=True)
    environment = os.environ.copy()
    for name, value in (overrides or {}).items():
        if value is None:
            environment.pop(name, None)
        else:
            environment[name] = value
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


def project_task(task: str, project: ProjectSpec, profile: str = "ci") -> int:
    directory = ROOT / str(project["directory"])
    # Select one interpreter for the entire task, including builds and wheel checks.
    # Relying on uv's nearest .python-version here can silently disagree with setup.
    interpreter = resolve_python(project, os.environ.get("PORTFOLIO_PYTHON") or None)
    # A compatibility check must not replace the editor's default environment.
    overrides: dict[str, str | None] = {
        "UV_PROJECT": str(directory),
        "UV_WORKING_DIR": str(directory),
        "PYTHONPATH": None,
        "PYTHONHOME": None,
        "PYTEST_ADDOPTS": None,
        "PYTEST_PLUGINS": None,
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": None,
    }
    if not os.environ.get("UV_PROJECT_ENVIRONMENT") and interpreter != project["default_python"]:
        overrides["UV_PROJECT_ENVIRONMENT"] = str(
            ROOT / ".local/venvs" / f"{project['slug']}-{interpreter}"
        )
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
        run_directory = ROOT / ".local/checks" / project["slug"] / interpreter / uuid.uuid4().hex
        build_directory = run_directory / "build"
        report = Path(os.environ.get("PORTFOLIO_CHECK_REPORT", str(run_directory / "pytest.xml")))
        if report.exists() or report.is_symlink():
            raise ValueError(
                "test report must be a fresh file; choose a new PORTFOLIO_CHECK_REPORT"
            )
        report.parent.mkdir(parents=True, exist_ok=True)
        commands = [
            base + list(project["format_arguments"]),
            base + list(project["lint_arguments"]),
            base + list(project["type_arguments"]),
            base + list(project["test_arguments"]) + ["--junitxml", str(report)],
            [
                "uv",
                "build",
                "--no-sources",
                "--python",
                interpreter,
                "--out-dir",
                str(build_directory),
            ],
            [
                sys.executable,
                str(ROOT / "scripts/wheel_smoke.py"),
                str(directory),
                str(project["package"]),
                interpreter,
                str(build_directory),
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
        result = execute(
            command, directory, 7200 if profile == "standard" else 600, overrides=overrides
        )
        if result:
            print(f"{project['slug']}: {task} failed ({result})", file=sys.stderr)
            return result
        if task == "check" and "--junitxml" in command:
            try:
                outcomes = read_junit(report)
            except ValueError as error:
                print(f"{project['slug']}: {error}", file=sys.stderr)
                return 1
            print(
                f"{project['slug']}: executed tests {outcomes.as_dict()}; report {report}",
                flush=True,
            )
            if not outcomes.ready:
                print("Required tests did not all execute and pass", file=sys.stderr)
                return 1
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
    try:
        projects = manifest()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.task == "list":
        for project in projects:
            print(f"{project['slug']:16} {project['directory']} [{project['status']}]")
        return 0
    if args.task == "doctor":
        print(f"Python dispatcher: {sys.version.split()[0]}; uv: {shutil.which('uv') or 'MISSING'}")
        problems = [
            f"{p['slug']}: {issue}" for p in projects for issue in checkout_problems(p, ROOT)
        ]
        for problem in problems:
            print(problem)
        return int(not shutil.which("uv") or bool(problems))
    if args.task == "verify-all":
        if os.environ.get("UV_PROJECT_ENVIRONMENT"):
            parser.error(
                "unset UV_PROJECT_ENVIRONMENT before verifying multiple independent projects"
            )
        if not 1 <= args.jobs <= 4:
            parser.error("--jobs must be between 1 and 4")
        try:
            for project in projects:
                resolve_python(project, os.environ.get("PORTFOLIO_PYTHON"))
        except ValueError as error:
            parser.error(str(error))
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            results = list(executor.map(lambda p: project_task("check", p), projects))
        return int(any(results))
    if args.task == "docs":
        return execute([sys.executable, str(ROOT / "scripts/check_docs.py")], ROOT)
    if args.task == "integration":
        if args.project not in {"settlement", "stream-lake", "code-search"}:
            parser.error("select settlement, stream-lake, or code-search")
        return execute(
            [sys.executable, str(ROOT / "integrations/run.py"), args.project],
            ROOT,
            overrides={
                name: None
                for name in (
                    "UV_PROJECT_ENVIRONMENT",
                    "UV_PROJECT",
                    "UV_WORKING_DIR",
                    "PYTHONPATH",
                    "PYTHONHOME",
                )
            },
        )
    selected = next((p for p in projects if p["slug"] == args.project), None)
    if selected is None:
        parser.error("select a project from `list`")
    try:
        return project_task(args.task, selected, args.profile)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())

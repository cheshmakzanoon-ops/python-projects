"""Run integration stages in independent product environments via public interfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import tomllib
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = {
    "stream-lake": [
        ("current", "02-stream-lake/current_stage.py"),
        ("quarry", "02-stream-lake/quarry_stage.py"),
    ],
    "settlement": [
        ("meridian", "01-settlement/meridian_stage.py"),
    ],
    "code-search": [
        ("pytrace", "03-code-search/pytrace_stage.py"),
        ("atlas", "03-code-search/atlas_stage.py"),
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("integration", choices=STAGES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = (
        args.output or ROOT / ".local/integrations" / args.integration / uuid.uuid4().hex
    ).resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("integration output must be empty; each execution owns fresh state")
    output.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    # Each stage owns its product environment; a caller's editor/source selectors
    # must neither redirect it nor let uv replace an unrelated environment.
    for name in (
        "UV_PROJECT_ENVIRONMENT",
        "UV_PROJECT",
        "UV_WORKING_DIR",
        "PYTHONPATH",
        "PYTHONHOME",
    ):
        environment.pop(name, None)
    if Path("/workspace").exists():
        environment.setdefault("UV_CACHE_DIR", "/workspace/.cache/uv")
        environment.setdefault("UV_PYTHON_INSTALL_DIR", "/workspace/.python")
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        environment[name] = "1"
    for slug in ("anchor", "meridian"):
        path = ROOT / f".local/services/{slug}.json"
        if path.is_file():
            environment.setdefault(
                f"{slug.upper()}_DATABASE_URL", json.loads(path.read_text())["url"]
            )
    with (ROOT / "portfolio.toml").open("rb") as stream:
        projects = {p["slug"]: p for p in tomllib.load(stream)["projects"]}
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    records = []
    for slug, stage in STAGES[args.integration]:
        path = ROOT / "integrations" / stage
        if not path.exists():
            print(f"Incomplete integration: missing {stage}", file=sys.stderr)
            return 2
        project = projects[slug]
        requested = environment.get("PORTFOLIO_PYTHON") or project["default_python"]
        interpreter = next(
            (
                version
                for version in project["required_python_versions"]
                if requested in (version, version.rsplit(".", 1)[0])
            ),
            None,
        )
        if interpreter is None:
            parser.error(f"{slug}: unsupported interpreter {requested!r}")
        directory = (ROOT / project["directory"]).resolve()
        stage_environment = environment.copy()
        stage_environment["PORTFOLIO_PYTHON"] = interpreter
        stage_environment.update(UV_PROJECT=str(directory), UV_WORKING_DIR=str(directory))
        stage_environment["UV_PROJECT_ENVIRONMENT"] = str(
            directory / ".venv"
            if interpreter == project["default_python"]
            else ROOT / ".local/venvs" / f"{slug}-{interpreter}"
        )
        command = ["uv", "run", "--locked", "--python", interpreter]
        command += ["python", str(path), "--output", str(output)]
        start = time.perf_counter()
        log = output / f"{slug}.log"
        with log.open("w") as stream:
            process = subprocess.Popen(
                command,
                cwd=directory,
                env=stage_environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
            )
            try:
                result = process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
                result = 124
            finally:
                if os.name != "nt":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        records.append(
            {
                "project": slug,
                "command": command,
                "exit_code": result,
                "seconds": time.perf_counter() - start,
                "stage_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
        if result:
            print(log.read_text(), file=sys.stderr)
            break
    passed = len(records) == len(STAGES[args.integration]) and all(
        r["exit_code"] == 0 for r in records
    )
    report = {
        "schema_version": 1,
        "integration": args.integration,
        "source_commit": commit,
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
        "status": "passed" if passed else "failed",
        "stages": records,
    }
    (output / "integration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{args.integration}: {report['status']}; evidence {output}")
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())

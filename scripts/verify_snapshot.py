"""Verify an immutable committed copy; retain exact command logs and source hashes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from evidence import ROOT, capture


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--project", action="append")
    parser.add_argument("--python", default="3.13.16")
    parser.add_argument("--checks", default="check,demo,benchmark")
    parser.add_argument("--profile", choices=["ci", "standard"], default="ci")
    parser.add_argument("--temp-root", type=Path, help="Writable scratch filesystem for clones")
    parser.add_argument("--integrations", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("verification output must be empty; choose a fresh evidence directory")
    args.output.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{args.commit}^{{commit}}"],
        cwd=ROOT,
        text=True,
    ).strip()
    if set(args.checks.split(",")) - {"check", "demo", "benchmark", "extended"}:
        parser.error("--checks accepts check,demo,benchmark,extended")
    if "extended" in args.checks.split(",") and args.project != ["strata"]:
        parser.error("extended requires exactly --project strata")
    environment = os.environ.copy()
    # An inherited project environment belongs to the caller's checkout. Reusing it
    # would test editable source outside the immutable copy and mix interpreters.
    for name in (
        "UV_PROJECT_ENVIRONMENT",
        "UV_PROJECT",
        "UV_WORKING_DIR",
        "PYTHONPATH",
        "PYTHONHOME",
    ):
        environment.pop(name, None)
    environment["PORTFOLIO_PYTHON"] = args.python
    # Concurrent interpreters share a server, never a Django test database.
    environment["MERIDIAN_TEST_DB_NAME"] = "pp_verify_" + uuid.uuid4().hex
    for name in ("UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR"):
        if name not in environment and Path("/workspace").exists():
            environment[name] = (
                "/workspace/.cache/uv" if name == "UV_CACHE_DIR" else "/workspace/.python"
            )
    for slug in ("anchor", "meridian"):
        service = ROOT / f".local/services/{slug}.json"
        if service.exists():
            metadata = json.loads(service.read_text())
            environment.setdefault(f"{slug.upper()}_DATABASE_URL", metadata["url"])
            if slug == "meridian":
                environment.setdefault("MERIDIAN_PG_CONTAINER", metadata["container"])
    reports = []
    with tempfile.TemporaryDirectory(prefix="portfolio-verify-", dir=args.temp_root) as folder:
        copy = Path(folder) / "source"
        # A disposable verification clone preserves Git provenance without sharing an index.
        subprocess.run(
            ["git", "clone", "--quiet", "--no-hardlinks", "--no-checkout", str(ROOT), str(copy)],
            check=True,
        )
        subprocess.run(["git", "checkout", "--quiet", "--detach", commit], cwd=copy, check=True)
        with (copy / "portfolio.toml").open("rb") as stream:
            projects = tomllib.load(stream)["projects"]
        if args.project:
            projects = [p for p in projects if p["slug"] in args.project]
            if {p["slug"] for p in projects} != set(args.project):
                parser.error("unknown project")
        for project in projects:
            scope = copy / project["directory"]
            before = capture(scope, copy)
            checks = []
            for check in args.checks.split(","):
                command = [sys.executable, "scripts/portfolio.py", check, project["slug"]]
                if check == "extended":
                    workload = [
                        "uv",
                        "run",
                        "--locked",
                        "--python",
                        args.python,
                        "--project",
                        str(scope),
                        "python",
                        str(scope / "benchmarks/extended_stateful.py"),
                        "--jobs",
                        "2",
                        "--output",
                        str(args.output / "strata-extended.json"),
                    ]
                    command = [
                        sys.executable,
                        "-c",
                        "import sys; from pathlib import Path; "
                        "sys.path.insert(0, 'scripts'); from portfolio import execute; "
                        "raise SystemExit(execute(sys.argv[1:], Path.cwd(), 7200))",
                        *workload,
                    ]
                if check == "benchmark":
                    command += ["--profile", args.profile]
                log = args.output / f"{project['slug']}-{args.python}-{check}.log"
                start = time.perf_counter()
                with log.open("w") as stream:
                    result = subprocess.run(
                        command,
                        cwd=copy,
                        env=environment,
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                        # The dispatcher bounds each executable and owns its process group.
                        # An outer SIGKILL timeout would bypass that cleanup.
                    )
                checks.append(
                    {
                        "command": command,
                        "exit_code": result.returncode,
                        "seconds": time.perf_counter() - start,
                        "log": log.name,
                    }
                )
                print(f"{project['slug']} {args.python} {check}: {result.returncode}", flush=True)
            after = capture(scope, copy)
            unchanged = (
                before["source_content_sha256"] == after["source_content_sha256"]
                and before["root_contract_sha256"] == after["root_contract_sha256"]
            )
            report = {
                "schema_version": 1,
                "project": project["slug"],
                "interpreter": args.python,
                "verified_at_utc": datetime.now(timezone.utc).isoformat(),
                **before,
                "source_unchanged_after": unchanged,
                "checks": checks,
                "status": "passed"
                if unchanged
                and not before["source_dirty"]
                and all(c["exit_code"] == 0 for c in checks)
                else "failed",
            }
            reports.append(report)
            # Keep compact actual outputs, never environments or databases.
            output = copy / ".local" / project["slug"]
            for filename in (
                "demo/report.json",
                "demo/demo.json",
                "demo/history.json",
                "demo/analysis.json",
                "benchmark/benchmark.json",
                "benchmark/report.json",
            ):
                artifact = output / filename
                if artifact.is_file():
                    (
                        args.output
                        / f"{project['slug']}-{args.python}-{filename.replace('/', '-')}"
                    ).write_bytes(artifact.read_bytes())
            # Drop only schemas named by product-owned markers before deleting the clone.
            if project["slug"] in {"anchor", "meridian"}:
                for kind in ("demo", "benchmark"):
                    owned = output / kind
                    if not owned.exists():
                        continue
                    command = [
                        "uv",
                        "run",
                        "--locked",
                        "--python",
                        args.python,
                        "python",
                        "-m",
                        f"{project['package']}.cli",
                        "clean-demo",
                        "--output",
                        str(owned),
                    ]
                    log = args.output / f"{project['slug']}-{args.python}-cleanup-{kind}.log"
                    with log.open("w") as stream:
                        result = subprocess.run(
                            command,
                            cwd=scope,
                            env=environment,
                            stdout=stream,
                            stderr=subprocess.STDOUT,
                            timeout=60,
                        )
                    checks.append(
                        {"command": command, "exit_code": result.returncode, "log": log.name}
                    )
                if any(c["exit_code"] for c in checks):
                    report["status"] = "failed"
            (args.output / f"{project['slug']}-{args.python}.json").write_text(
                json.dumps(report, indent=2) + "\n"
            )
        if args.integrations:
            for name in ("settlement", "stream-lake", "code-search"):
                destination = args.output / name
                command = [
                    sys.executable,
                    "integrations/run.py",
                    name,
                    "--output",
                    str(destination),
                ]
                with (args.output / f"integration-{name}.log").open("w") as stream:
                    result = subprocess.run(
                        command, cwd=copy, env=environment, stdout=stream, stderr=subprocess.STDOUT
                    )
                reports.append({"status": "passed" if result.returncode == 0 else "failed"})
                print(f"integration {name}: {result.returncode}", flush=True)
    return int(any(r["status"] != "passed" for r in reports))


if __name__ == "__main__":
    raise SystemExit(main())

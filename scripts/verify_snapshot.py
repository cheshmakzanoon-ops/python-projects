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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("verification output must be empty; choose a fresh evidence directory")
    args.output.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", f"{args.commit}^{{commit}}"], cwd=ROOT, text=True
    ).strip()
    if set(args.checks.split(",")) - {"check", "demo", "benchmark"}:
        parser.error("--checks accepts check,demo,benchmark")
    environment = os.environ.copy()
    environment["PORTFOLIO_PYTHON"] = args.python
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
    with tempfile.TemporaryDirectory(prefix="portfolio-verify-") as folder:
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
                "benchmark/benchmark.json",
                "benchmark/report.json",
            ):
                artifact = output / filename
                if artifact.is_file():
                    (
                        args.output
                        / f"{project['slug']}-{args.python}-{filename.replace('/', '-')}"
                    ).write_bytes(artifact.read_bytes())
            (args.output / f"{project['slug']}-{args.python}.json").write_text(
                json.dumps(report, indent=2) + "\n"
            )
    return int(any(r["status"] != "passed" for r in reports))


if __name__ == "__main__":
    raise SystemExit(main())

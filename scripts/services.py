"""Start/stop only named portfolio-owned, loopback-only PostgreSQL demo containers.

Local trust authentication is for synthetic isolated development data only.
The printed URL is not suitable for a shared or production database.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "postgres:17"


def run(*args: str) -> str:
    return subprocess.check_output(["docker", *args], text=True, timeout=180).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "down", "status"])
    parser.add_argument("project", choices=["anchor", "meridian"])
    args = parser.parse_args()
    name = f"pp-{args.project}-dev"
    if args.action == "down":
        listing = run("ps", "-a", "--filter", f"name=^/{name}$", "--format", "{{.Names}}")
        if listing == name:
            run("rm", "-f", name)
        return
    found = run("ps", "-a", "--filter", f"name=^/{name}$", "--format", "{{.Names}}")
    if not found:
        if args.action == "status":
            raise SystemExit(f"{name}: not running")
        run(
            "run",
            "-d",
            "--name",
            name,
            "--label",
            "pp.owner=portfolio",
            "-p",
            "127.0.0.1::5432",
            "-e",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "-e",
            f"POSTGRES_USER={args.project}",
            "-e",
            f"POSTGRES_DB={args.project}",
            IMAGE,
        )
    elif args.action == "up":
        run("start", name)
    for _ in range(60):
        check = subprocess.run(
            ["docker", "exec", name, "pg_isready", "-U", args.project],
            capture_output=True,
            timeout=5,
        )
        if check.returncode == 0:
            break
        time.sleep(0.25)
    else:
        raise SystemExit(f"{name}: PostgreSQL readiness failed")
    port = run("port", name, "5432/tcp").rsplit(":", 1)[-1]
    url = f"postgresql://{args.project}@127.0.0.1:{port}/{args.project}"
    output = ROOT / ".local/services"
    output.mkdir(parents=True, exist_ok=True)
    (output / f"{args.project}.json").write_text(json.dumps({"container": name, "url": url}) + "\n")
    print(f"{args.project.upper()}_DATABASE_URL={url}")


if __name__ == "__main__":
    main()

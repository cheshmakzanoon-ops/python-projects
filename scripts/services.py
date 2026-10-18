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
IMAGE = "postgres:17@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3"


def run(*args: str) -> str:
    return subprocess.check_output(["docker", *args], text=True, timeout=180).strip()


def verify_owner(name: str) -> None:
    """A matching name alone never grants permission to manage a container."""
    labels = json.loads(run("inspect", "--format", "{{json .Config.Labels}}", name))
    if not isinstance(labels, dict) or labels.get("pp.owner") != "portfolio":
        raise SystemExit(f"{name}: refusing to manage a container without pp.owner=portfolio")


def database_port(name: str, *, configured: bool = False) -> int:
    """Expose trust-authenticated development databases only through loopback."""
    field = ".HostConfig.PortBindings" if configured else ".NetworkSettings.Ports"
    ports = json.loads(run("inspect", "--format", "{{json " + field + "}}", name))
    bindings = ports.get("5432/tcp") if isinstance(ports, dict) else None
    if (
        not isinstance(bindings, list)
        or len(bindings) != 1
        or not isinstance(bindings[0], dict)
        or bindings[0].get("HostIp") != "127.0.0.1"
    ):
        raise SystemExit(f"{name}: PostgreSQL must have exactly one loopback port binding")
    if configured and bindings[0].get("HostPort") in {"", "0"}:
        # Docker retains an empty requested port when it allocated a host port dynamically.
        return 0
    try:
        port = int(bindings[0]["HostPort"])
    except (KeyError, TypeError, ValueError) as error:
        raise SystemExit(f"{name}: invalid PostgreSQL port binding") from error
    if not 1 <= port <= 65535:
        raise SystemExit(f"{name}: invalid PostgreSQL port binding")
    return port


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "down", "status"])
    parser.add_argument("project", choices=["anchor", "meridian"])
    args = parser.parse_args()
    name = f"pp-{args.project}-dev"
    found = run("ps", "-a", "--filter", f"name=^/{name}$", "--format", "{{.Names}}")
    if found:
        verify_owner(name)
        if args.action == "up":
            database_port(name, configured=True)
    if args.action == "down":
        if found:
            run("rm", "-f", "-v", name)
        (ROOT / ".local/services" / f"{args.project}.json").unlink(missing_ok=True)
        return
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
    port = database_port(name)
    url = f"postgresql://{args.project}@127.0.0.1:{port}/{args.project}"
    output = ROOT / ".local/services"
    output.mkdir(parents=True, exist_ok=True)
    (output / f"{args.project}.json").write_text(json.dumps({"container": name, "url": url}) + "\n")
    print(f"{args.project.upper()}_DATABASE_URL={url}")


if __name__ == "__main__":
    main()

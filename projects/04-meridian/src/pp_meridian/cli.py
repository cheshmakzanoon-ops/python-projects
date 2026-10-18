"""Operator CLI; generated demos live in an explicitly owned PostgreSQL schema."""

import argparse
import hashlib
import json
import os
import re
import secrets
from pathlib import Path
from typing import Any


def output_directory(path: str) -> Path:
    output = Path(path)
    if not output.is_absolute() or output.is_symlink():
        raise ValueError("output must be an absolute nonsymlink directory")
    output = output.resolve()
    project = Path(__file__).resolve().parents[2]
    if output == project or project in output.parents:
        raise ValueError("output must be outside project source")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()) and not (output / ".meridian-owned.json").is_file():
        raise ValueError("refusing a nonempty directory not owned by Meridian")
    return output


def initialize(output: Path) -> dict[str, Any]:
    import psycopg

    url = os.environ.get("MERIDIAN_DATABASE_URL")
    if not url:
        raise ValueError("MERIDIAN_DATABASE_URL is required; only PostgreSQL is supported")
    marker = output / ".meridian-owned.json"
    if marker.exists():
        raise ValueError("demo already exists; use clean-demo first")
    schema = "meridian_demo_" + secrets.token_hex(12)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
    ownership = {
        "schema_version": 1,
        "schema": schema,
        "database_sha256": hashlib.sha256(url.encode()).hexdigest(),
        "files": ["demo.json", "report.html", "benchmark.json"],
    }
    marker.write_text(json.dumps(ownership, indent=2))
    os.environ["MERIDIAN_SCHEMA"] = schema
    setup()
    from django.core.management import call_command

    call_command("migrate", interactive=False, verbosity=0)
    return ownership


def setup() -> None:
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pp_meridian.config.settings")
    django.setup()


def clean(output: Path) -> None:
    import psycopg

    marker = output / ".meridian-owned.json"
    if not marker.is_file():
        raise ValueError("no Meridian ownership marker")
    ownership = json.loads(marker.read_text())
    schema = ownership["schema"]
    url = os.environ.get("MERIDIAN_DATABASE_URL", "")
    if (
        not re.fullmatch(r"meridian_demo_[a-f0-9]{24}", schema)
        or ownership["database_sha256"] != hashlib.sha256(url.encode()).hexdigest()
    ):
        raise ValueError("database or schema ownership mismatch")
    expected = {"demo.json", "report.html", "benchmark.json"}
    if set(ownership["files"]) != expected:
        raise ValueError("invalid owned file manifest")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    for name in expected:
        target = output / name
        if target.is_symlink():
            raise ValueError("refusing symlink")
        target.unlink(missing_ok=True)
    marker.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["demo", "benchmark", "clean-demo"]:
        command = sub.add_parser(name)
        command.add_argument("--output", required=True)
        command.add_argument("--seed", type=int, default=1729)
        if name == "benchmark":
            command.add_argument("--profile", choices=["ci", "standard"], default="ci")
    sub.add_parser("serve").add_argument("--bind", default="127.0.0.1:8104")
    sub.add_parser("backup").add_argument("--output", required=True)
    restore_parser = sub.add_parser("restore")
    restore_parser.add_argument("--input", required=True)
    restore_parser.add_argument("--database", required=True)
    for name in ["audit", "replay"]:
        command = sub.add_parser(name)
        command.add_argument("--user", type=int, required=True)
        command.add_argument("--tenant", required=True)
    args = parser.parse_args()
    if args.command in {"backup", "restore"}:
        setup()
        from pp_meridian.persistence.snapshot import backup, restore

        if args.command == "backup":
            backup(Path(args.output))
        else:
            restore(Path(args.input), args.database)
        return
    if args.command == "serve":
        setup()
        from django.core.management import call_command

        call_command("runserver", args.bind, use_reloader=False)
        return
    if args.command in {"audit", "replay"}:
        setup()
        from uuid import UUID

        from pp_meridian.application.ledger import audit

        print(
            json.dumps(
                audit(args.user, UUID(args.tenant), rebuild=args.command == "replay"), indent=2
            )
        )
        return
    output = output_directory(args.output)
    if args.command == "clean-demo":
        clean(output)
        return
    initialize(output)
    if args.command == "demo":
        from pp_meridian.workloads import demo

        demo(output, args.seed)
    else:
        from pp_meridian.workloads import benchmark

        benchmark(output, args.seed, args.profile)


if __name__ == "__main__":
    main()

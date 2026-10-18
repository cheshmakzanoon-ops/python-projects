"""PostgreSQL native consistent snapshots; restore only into a newly created DB.

Uses the installed PostgreSQL client, or an explicitly named local development
container. Passwords are passed through environment bindings, never argv/logs.
"""

import os
import shutil
import subprocess
from pathlib import Path

import psycopg
from django.conf import settings
from psycopg import sql


def _command(program: str, database: str) -> tuple[list[str], dict[str, str]]:
    config = {k: str(v) for k, v in settings.DATABASES["default"].items()}
    environment = dict(os.environ)
    container = os.environ.get("MERIDIAN_PG_CONTAINER")
    if container:
        return [
            "docker",
            "exec",
            "-i",
            container,
            program,
            "-U",
            config["USER"],
            "-d",
            database,
        ], environment
    installed = shutil.which(program)
    if not installed:
        raise RuntimeError(
            f"{program} is required; install matching PostgreSQL clients or explicitly set MERIDIAN_PG_CONTAINER for the local owned service"
        )
    environment.update(
        PGHOST=config["HOST"],
        PGPORT=str(config["PORT"]),
        PGUSER=config["USER"],
        PGPASSWORD=config["PASSWORD"],
    )
    return [installed, "-d", database], environment


def backup(path: Path) -> None:
    if not path.is_absolute() or path.exists() or path.is_symlink():
        raise ValueError("backup requires a new absolute file path")
    command, environment = _command("pg_dump", str(settings.DATABASES["default"]["NAME"]))
    with path.open("xb") as stream:
        subprocess.run(
            [*command, "--format=custom", "--no-owner", "--no-acl"],
            stdout=stream,
            stderr=subprocess.PIPE,
            env=environment,
            check=True,
        )


def restore(path: Path, database: str) -> None:
    import re

    if not re.fullmatch(r"meridian_restore_[a-f0-9]{16}", database):
        raise ValueError("restore target must be a fresh meridian_restore_<16 hex> database")
    config = {k: str(v) for k, v in settings.DATABASES["default"].items()}
    with psycopg.connect(
        host=config["HOST"],
        port=config["PORT"],
        user=config["USER"],
        password=config["PASSWORD"],
        dbname="postgres",
        autocommit=True,
    ) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    command, environment = _command("pg_restore", database)
    with path.open("rb") as stream:
        subprocess.run(
            [*command, "--exit-on-error", "--no-owner", "--no-acl"],
            stdin=stream,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            check=True,
        )

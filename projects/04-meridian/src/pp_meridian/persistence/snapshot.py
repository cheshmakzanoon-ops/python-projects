"""PostgreSQL native consistent snapshots; restore only into a newly created DB.

Uses the installed PostgreSQL client, or an explicitly named local development
container. Passwords are passed through environment bindings, never argv/logs.
"""

import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from django.conf import settings
from psycopg import sql
from psycopg.conninfo import make_conninfo


def _connection_parameters(database: str) -> dict[str, str]:
    config = settings.DATABASES["default"]
    parameters = {
        str(key): str(value)
        for key, value in config.get("OPTIONS", {}).items()
        if key not in {"assume_role", "isolation_level", "pool", "server_side_binding"}
    }
    parameters.update(
        host=str(config["HOST"]),
        port=str(config["PORT"]),
        user=str(config["USER"]),
        password=str(config["PASSWORD"]),
        dbname=database,
    )
    return parameters


@contextmanager
def _command(program: str, database: str) -> Iterator[tuple[list[str], dict[str, str]]]:
    config = {k: str(v) for k, v in settings.DATABASES["default"].items()}
    environment = dict(os.environ)
    container = os.environ.get("MERIDIAN_PG_CONTAINER")
    if container:
        yield (
            [
                "docker",
                "exec",
                "-i",
                container,
                program,
                "-U",
                config["USER"],
                "-d",
                database,
            ],
            environment,
        )
        return
    installed = shutil.which(program)
    if not installed:
        raise RuntimeError(
            f"{program} is required; install matching PostgreSQL clients or explicitly set MERIDIAN_PG_CONTAINER for the local owned service"
        )
    parameters = _connection_parameters(database)
    environment["PGPASSWORD"] = parameters.pop("password")
    # A service file preserves every libpq option, including options without an
    # environment variable, without putting authentication values in argv.
    with tempfile.NamedTemporaryFile(
        mode="w", prefix="meridian-pg-", encoding="utf-8", delete_on_close=False
    ) as service:
        service.write("[meridian_snapshot]\n")
        for key, value in parameters.items():
            if "\n" in value or "\r" in value:
                raise ValueError("native PostgreSQL connection options cannot contain line breaks")
            service.write(f"{key}={value}\n")
        service.close()
        environment.update(PGSERVICEFILE=service.name, PGSERVICE="meridian_snapshot")
        yield [installed], environment


def backup(path: Path) -> None:
    if not path.is_absolute() or path.exists() or path.is_symlink():
        raise ValueError("backup requires a new absolute file path")
    with _command("pg_dump", str(settings.DATABASES["default"]["NAME"])) as (
        command,
        environment,
    ):
        stream = path.open("xb")
        try:
            with stream:
                subprocess.run(
                    [*command, "--format=custom", "--no-owner", "--no-acl"],
                    stdout=stream,
                    stderr=subprocess.PIPE,
                    env=environment,
                    check=True,
                )
        except BaseException:
            path.unlink(missing_ok=True)
            raise


def restore(path: Path, database: str) -> None:
    import re

    if not re.fullmatch(r"meridian_restore_[a-f0-9]{16}", database):
        raise ValueError("restore target must be a fresh meridian_restore_<16 hex> database")
    with _command("pg_restore", database) as (command, environment), path.open("rb") as stream:
        with psycopg.connect(
            make_conninfo(**_connection_parameters("postgres")), autocommit=True
        ) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        subprocess.run(
            [*command, "--single-transaction", "--exit-on-error", "--no-owner", "--no-acl"],
            stdin=stream,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            check=True,
        )

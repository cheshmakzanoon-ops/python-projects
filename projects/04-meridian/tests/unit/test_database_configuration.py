import subprocess
from configparser import ConfigParser
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from pp_meridian.config.database import database_config
from pp_meridian.persistence import snapshot


def test_database_url_preserves_transport_options_and_decodes_identifiers():
    config = database_config(
        "postgresql://test%40operator:synthetic%3Apassword@db.example:5433/ledger%20test"
        "?sslmode=verify-full&sslrootcert=%2Ftmp%2Froot.crt&connect_timeout=7"
        "&application_name=meridian&options=-c%20statement_timeout%3D5000"
    )
    assert config["USER"] == "test@operator"
    assert config["PASSWORD"] == "synthetic:password"
    assert config["NAME"] == "ledger test"
    assert config["OPTIONS"] == {
        "sslmode": "verify-full",
        "sslrootcert": "/tmp/root.crt",
        "connect_timeout": "7",
        "application_name": "meridian",
        "options": "-c statement_timeout=5000",
    }


def test_native_snapshot_preserves_connection_policy_without_password_in_arguments(monkeypatch):
    config = database_config(
        "postgresql://operator:synthetic@db.example:5433/ledger"
        "?sslmode=verify-full&sslrootcert=%2Ftmp%2Froot.crt&connect_timeout=7"
    )
    monkeypatch.setattr(snapshot, "settings", SimpleNamespace(DATABASES={"default": config}))
    monkeypatch.delenv("MERIDIAN_PG_CONTAINER", raising=False)
    monkeypatch.setattr(snapshot.shutil, "which", lambda program: f"/usr/bin/{program}")
    with snapshot._command("pg_dump", "restored_ledger") as (command, environment):
        assert command == ["/usr/bin/pg_dump"]
        service = Path(environment["PGSERVICEFILE"])
        assert service.stat().st_mode & 0o777 == 0o600
        config = ConfigParser(interpolation=None)
        config.read(service)
        parameters = config[environment["PGSERVICE"]]
        assert parameters["dbname"] == "restored_ledger"
        assert parameters["host"] == "db.example"
        assert parameters["sslmode"] == "verify-full"
        assert parameters["sslrootcert"] == "/tmp/root.crt"
        assert parameters["connect_timeout"] == "7"
        assert environment["PGPASSWORD"] == "synthetic"
    assert not service.exists()


def test_failed_backup_removes_partial_archive_without_overwriting_existing_file(
    monkeypatch, tmp_path
):
    @contextmanager
    def command(*_):
        yield ["pg_dump"], {}

    monkeypatch.setattr(snapshot, "_command", command)

    def failed_dump(*args, **kwargs):
        kwargs["stdout"].write(b"incomplete archive")
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(snapshot.subprocess, "run", failed_dump)
    path = tmp_path / "snapshot.dump"
    with pytest.raises(subprocess.CalledProcessError):
        snapshot.backup(path)
    assert not path.exists()
    path.write_bytes(b"preserve existing backup")
    with pytest.raises(ValueError):
        snapshot.backup(path)
    assert path.read_bytes() == b"preserve existing backup"

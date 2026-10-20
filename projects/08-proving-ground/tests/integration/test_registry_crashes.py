"""Kill real SQLite writers on both sides of the audit/deployment commit boundary."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from contextlib import closing

import pytest

from pp_proving_ground.registry.sqlite import Registry

WRITER = """
import os, sqlite3, sys
from pathlib import Path
from pp_proving_ground.artifacts.store import ArtifactStore
from pp_proving_ground.registry.sqlite import Registry
path, root, version, phase, rejected = sys.argv[1:]
registry = Registry(Path(path), ArtifactStore(Path(root)))
original = sqlite3.connect
class CrashConnection(sqlite3.Connection):
    def execute(self, sql, parameters=()):
        result = super().execute(sql, parameters)
        normalized = ' '.join(sql.upper().split())
        if ((phase == 'after_audit' and normalized.startswith('INSERT INTO AUDIT')) or
            (phase == 'after_deployment' and normalized.startswith('INSERT INTO DEPLOYMENT'))):
            os._exit(91)
        return result
    def commit(self):
        super().commit()
        if phase == 'after_commit':
            os._exit(91)
def connect(*args, **kwargs):
    kwargs['factory'] = CrashConnection
    return original(*args, **kwargs)
sqlite3.connect = connect
registry.promote(int(version), -1 if rejected == 'yes' else 0)
"""


@pytest.mark.parametrize("phase", ["after_audit", "after_deployment", "after_commit"])
def test_process_exit_preserves_atomic_accepted_transition(context, phase):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            WRITER,
            str(context.registry.path),
            str(context.store.root),
            str(context.model.version),
            phase,
            "no",
        ],
        env={
            **os.environ,
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        },
        timeout=20,
        capture_output=True,
    )
    assert result.returncode == 91, result.stderr.decode()
    reopened = Registry(context.registry.path, context.store)
    committed = phase == "after_commit"
    assert reopened.current().generation == int(committed)
    assert len(reopened.audit()) == int(committed)
    if committed:
        assert reopened.audit()[0]["accepted"] is True
    with closing(sqlite3.connect(context.registry.path)) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT COUNT(*) FROM deployment").fetchone()[0] == int(committed)
    # Recovery permits exactly one next generation, regardless of acknowledgement loss.
    reopened.promote(context.model.version, int(committed))
    assert reopened.current().generation == int(committed) + 1
    assert len(reopened.audit()) == int(committed) + 1


@pytest.mark.parametrize("phase", ["after_audit", "after_commit"])
def test_process_exit_of_rejection_never_creates_a_deployment(context, phase):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            WRITER,
            str(context.registry.path),
            str(context.store.root),
            str(context.model.version),
            phase,
            "yes",
        ],
        env={
            **os.environ,
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        },
        timeout=20,
        capture_output=True,
    )
    assert result.returncode == 91, result.stderr.decode()
    reopened = Registry(context.registry.path, context.store)
    assert reopened.current().generation == 0
    assert len(reopened.audit()) == int(phase == "after_commit")
    if reopened.audit():
        assert reopened.audit()[0]["accepted"] is False
        assert "registry generation comparison failed" in reopened.audit()[0]["reasons"]


def test_registration_snapshots_one_report_identity_under_caller_updates(
    context, tmp_path, monkeypatch
):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    import pp_proving_ground.registry.sqlite as module

    target = Registry(tmp_path / "snapshot.db", context.store)
    encoded, release = threading.Event(), threading.Event()
    real_canonical = module.canonical

    def paused(value):
        result = real_canonical(value)
        encoded.set()
        assert release.wait(10)
        return result

    monkeypatch.setattr(module, "canonical", paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(target.register, context.manifest.identity, context.report)
        assert encoded.wait(5)
        try:
            context.report.metrics["brier"] += 0.001
        finally:
            release.set()
        registered = pending.result(timeout=10)
    assert registered == target.versions()[0]
    assert registered.evaluation_digest == target.report(registered.version).identity
    assert registered.evaluation_digest != context.report.identity

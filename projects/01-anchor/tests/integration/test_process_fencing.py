"""Pause an actual process before its side effect; resume after takeover or cleanup."""

import asyncio
import json
import os
import subprocess
import sys
import time

import pytest

from pp_anchor import Definition, Step, drain


@pytest.mark.parametrize("cancel", [False, True])
def test_AN04_AN06_paused_process_cannot_recreate_or_ack(engine, dsn, tmp_path, cancel):
    run_id = engine.submit(
        Definition("paused", 1, (Step("publish", activity="publish", compensate="cleanup"),)),
        {},
        "paused",
    )
    ready, resume, outcome = (tmp_path / name for name in ("ready.json", "resume", "outcome.json"))
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pp_anchor.cli",
            "fault-worker",
            "--schema",
            engine.schema,
            "--ready-file",
            str(ready),
            "--mode",
            "before-effect",
            "--resume-file",
            str(resume),
            "--outcome-file",
            str(outcome),
        ],
        env={**os.environ, "ANCHOR_DATABASE_URL": dsn},
    )
    try:
        deadline = time.monotonic() + 30
        while not ready.exists():
            assert process.poll() is None and time.monotonic() < deadline
            time.sleep(0.01)
        if cancel:
            engine.cancel(run_id)
            asyncio.run(drain(engine))
        else:
            time.sleep(0.55)
            asyncio.run(drain(engine))
        resume.touch()
        process.wait(timeout=20)
        assert process.returncode == 0
        result = json.loads(outcome.read_text())
        assert result["finish"] == result["heartbeat"] == "StaleLeaseError"
        assert result["publish"] == ("ProviderFencedError" if cancel else "accepted")
        assert engine.status(run_id)["status"] == ("compensated" if cancel else "completed")
        with engine.transaction() as c:
            row = c.execute(
                "SELECT publications,fenced FROM provider_effects WHERE business_key=%s", (run_id,)
            ).fetchone()
        assert row == {"publications": 0 if cancel else 1, "fenced": cancel}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

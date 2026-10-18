import asyncio
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from pp_anchor import (
    ActivityRegistry,
    ConflictError,
    Definition,
    Engine,
    ProviderFencedError,
    StaleLeaseError,
    Step,
    Worker,
    drain,
    scheduler,
)
from pp_anchor.api.app import create_app


def one():
    return Definition("one", 1, (Step("a"),))


def test_AN02_process_crashes_and_ingress(engine, dsn):
    env = {**os.environ, "ANCHOR_DATABASE_URL": dsn}
    for stage in ("before_commit", "after_commit"):
        key = stage
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pp_anchor.cli",
                "fault-submit",
                "--schema",
                engine.schema,
                "--stage",
                stage,
                "--key",
                key,
            ],
            env=env,
            timeout=20,
        )
        assert result.returncode == -9
        definition = Definition("crash", 1, (Step("one"),))
        run_id = engine.submit(definition, {}, key)
        assert engine.submit(definition, {}, key) == run_id
        with engine.transaction() as c:
            rows = c.execute(
                "SELECT workflow_id FROM ingress_requests WHERE idempotency_key=%s", (key,)
            ).fetchall()
            assert rows == [{"workflow_id": run_id}]
            tasks = c.execute(
                "SELECT command_id FROM activity_tasks WHERE workflow_id=%s", (run_id,)
            ).fetchall()
            assert tasks == [{"command_id": "step:one"}]
        with pytest.raises(ConflictError):
            engine.submit(definition, {"different": True}, key)
    with ThreadPoolExecutor(8) as pool:
        ids = list(pool.map(lambda _: engine.submit(one(), {}, "concurrent"), range(20)))
    assert len(set(ids)) == 1


def test_AN03_kill_after_effect_before_ack(engine, dsn, tmp_path):
    definition = Definition("publish", 1, (Step("p", activity="publish", compensate="cleanup"),))
    run_id = engine.submit(definition, {"artifact": "synthetic"}, "kill-after-effect")
    marker = tmp_path / "ready.json"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pp_anchor.cli",
            "fault-worker",
            "--schema",
            engine.schema,
            "--ready-file",
            str(marker),
        ],
        env={**os.environ, "ANCHOR_DATABASE_URL": dsn},
    )
    try:
        deadline = time.monotonic() + 20
        while not marker.exists():
            assert process.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.01)
        first = json.loads(marker.read_text())
        assert first["attempt_number"] == 1
        process.kill()
        process.wait(timeout=5)
        time.sleep(0.55)
        asyncio.run(drain(engine))
        assert engine.status(run_id)["status"] == "completed"
        with engine.transaction() as c:
            row = c.execute(
                "SELECT publications FROM provider_effects WHERE business_key=%s", (run_id,)
            ).fetchone()
            attempts = c.execute(
                "SELECT status FROM activity_attempts WHERE workflow_id=%s ORDER BY attempt_number",
                (run_id,),
            ).fetchall()
        assert row == {"publications": 1}
        assert attempts == [{"status": "expired"}, {"status": "completed"}]
        assert engine.replay(run_id).status == "completed"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_AN04_epoch_and_expired_heartbeat(engine):
    run_id = engine.submit(one(), {}, "epoch")
    a = engine.claim(0.04)
    assert a
    time.sleep(0.06)
    with pytest.raises(StaleLeaseError):
        engine.heartbeat(a)
    b = engine.claim(5)
    assert b and b.lease_epoch == a.lease_epoch + 1
    with pytest.raises(StaleLeaseError):
        engine.finish(a, {"late": True})
    with pytest.raises(StaleLeaseError):
        engine.heartbeat(a)
    with pytest.raises(StaleLeaseError):
        engine.finish(a, error="late failure")
    engine.heartbeat(b)
    engine.finish(b, {})
    assert engine.status(run_id)["status"] == "completed"


def test_AN05_persisted_timers_restart_two_schedulers(engine, dsn):
    definition = Definition(
        "timers", 1, (Step("first", kind="timer", delay=60), Step("second", kind="timer", delay=60))
    )
    run_id = engine.submit(definition, {}, "timers")
    assert engine.tick() == 0
    with Engine(dsn, engine.schema) as restarted:
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: restarted.tick(advance_seconds=61), range(2)))
        assert sum(results) == 2
        assert restarted.tick(advance_seconds=61) == 0
    events = engine.history(run_id)
    assert [e.step for e in events if e.kind == "step_completed"].count("first") == 1
    assert engine.replay(run_id).status == "completed"


def test_AN06_early_signal_idempotency_and_fenced_late_publication(engine):
    definition = Definition(
        "signal",
        1,
        (
            Step("a"),
            Step("wait", kind="signal", signal="go", after=("a",)),
            Step("p", activity="publish", after=("wait",), compensate="cleanup"),
        ),
    )
    run_id = engine.submit(definition, {}, "signal")
    engine.signal(run_id, "go", {"ok": True}, "early")
    engine.signal(run_id, "go", {"ok": True}, "early")
    with pytest.raises(ConflictError):
        engine.signal(run_id, "go", {"ok": False}, "early")
    first = engine.claim()
    assert first
    engine.finish(first)
    paused = engine.claim()
    assert paused and paused.activity == "publish"
    engine.cancel(run_id)
    asyncio.run(drain(engine))
    assert engine.status(run_id)["status"] == "compensated"
    with pytest.raises(ProviderFencedError):
        engine.publish(run_id, {})
    with pytest.raises(StaleLeaseError):
        engine.finish(paused)
    with engine.transaction() as c:
        row = c.execute(
            "SELECT publications,fenced FROM provider_effects WHERE business_key=%s", (run_id,)
        ).fetchone()
    assert row == {"publications": 0, "fenced": True}


def test_AN06_completion_cancel_races(engine):
    for index in range(12):
        run_id = engine.submit(
            Definition("race", 1, (Step("p", activity="publish", compensate="cleanup"),)),
            {},
            f"race-{index}",
        )
        task = engine.claim()
        assert task

        def complete():
            try:
                engine.publish(run_id, {})
                engine.finish(task)
            except (StaleLeaseError, ProviderFencedError):
                pass

        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(complete), pool.submit(engine.cancel, run_id)]
            for future in futures:
                future.result()
        asyncio.run(drain(engine))
        state = engine.status(run_id)["status"]
        assert state in ("completed", "compensated")
        with engine.transaction() as c:
            effect = c.execute(
                "SELECT publications,fenced FROM provider_effects WHERE business_key=%s", (run_id,)
            ).fetchone()
        assert effect
        if state == "compensated":
            assert effect["fenced"] is True
        else:
            assert effect == {"publications": 1, "fenced": False}
        assert engine.replay(run_id).status == state


def test_AN07_cleanup_failure_unresolved_until_actual_success(engine):
    definition = Definition(
        "cleanup-fail",
        1,
        (
            Step("p", activity="publish", compensate="bad_cleanup", max_attempts=2, retry_delay=0),
            Step("fail", activity="fail", after=("p",), max_attempts=2, retry_delay=0),
        ),
    )
    run_id = engine.submit(definition, {}, "cleanup-fail")
    registry = ActivityRegistry()

    async def bad(context):
        return context.engine.cleanup(context.business_key, fail=True)

    registry.register("bad_cleanup", bad)
    worker = Worker(engine, registry)

    async def exhaust():
        while await worker.run_once():
            pass

    asyncio.run(exhaust())
    status = engine.status(run_id)
    assert status["status"] == "compensating"
    assert status["compensation"] == {"p": "failed"}
    assert any(e.kind == "retry_scheduled" for e in engine.history(run_id))
    assert any(e.kind == "compensation_retry" for e in engine.history(run_id))
    engine.retry_compensation(run_id)

    async def good(context):
        return context.engine.cleanup(context.business_key)

    registry.handlers["bad_cleanup"] = good
    asyncio.run(exhaust())
    assert engine.status(run_id)["status"] == "compensated"
    assert engine.replay(run_id).status == "compensated"


def test_AN08_two_schedulers_workers_faults_accounting(engine, dsn):
    definition = Definition(
        "stress",
        1,
        (
            Step("start", activity="flaky", retry_delay=0),
            Step("timer", kind="timer", delay=0, after=("start",)),
            Step("a", after=("timer",)),
            Step("b", after=("timer",)),
            Step("join", kind="join", after=("a", "b")),
        ),
    )
    ids = [engine.submit(definition, {"i": i}, f"load-{i}") for i in range(30)]
    registry = ActivityRegistry()

    async def flaky(context):
        if context.task.attempt_number == 1:
            raise RuntimeError("seeded transient")
        return {"ok": True}

    registry.register("flaky", flaky)

    async def exercise(other):
        stop = asyncio.Event()
        async with asyncio.timeout(60), asyncio.TaskGroup() as group:
            group.create_task(scheduler(engine, stop))
            group.create_task(scheduler(other, stop))
            group.create_task(Worker(engine, registry, concurrency=3).run(stop))
            group.create_task(Worker(other, registry, concurrency=3).run(stop))
            try:
                while True:
                    statuses = await asyncio.gather(
                        *(asyncio.to_thread(engine.status, run_id) for run_id in ids)
                    )
                    if all(s["status"] == "completed" for s in statuses):
                        return
                    await asyncio.sleep(0.02)
            finally:
                stop.set()

    with Engine(dsn, engine.schema) as other:
        asyncio.run(exercise(other))
    with engine.transaction() as c:
        pending = c.execute(
            "SELECT count(*) AS count FROM activity_tasks WHERE status<>'completed'"
        ).fetchone()
        counts = c.execute(
            "SELECT count(*) AS count,count(DISTINCT workflow_id) AS runs FROM activity_tasks"
        ).fetchone()
    assert pending == {"count": 0}
    assert counts == {"count": 90, "runs": 30}
    assert all(engine.replay(run_id).status == "completed" for run_id in ids)


def test_api_validation_pagination_health(engine):
    with TestClient(create_app(engine)) as client:
        assert client.get("/health").json() == {"status": "alive"}
        assert client.get("/ready").json() == {"status": "ready"}
        request = {"definition": one().to_dict(), "payload": {}, "idempotency_key": "http"}
        response = client.post("/runs", json=request)
        assert response.status_code == 201
        run_id = response.json()["workflow_id"]
        assert client.post("/runs", json=request).json() == response.json()
        assert (
            client.post("/runs", json={**request, "payload": {"changed": True}}).status_code == 409
        )
        assert client.get("/runs/no-such-run").status_code == 404
        assert client.get(f"/runs/{run_id}/history?limit=0").status_code == 422
        page = client.get(f"/runs/{run_id}/history?limit=1").json()
        assert len(page["events"]) == 1 and page["next_after"] == 1
        assert (
            client.post(
                f"/runs/{run_id}/signals",
                json={"name": "go", "payload": {}, "idempotency_key": "signal"},
            ).status_code
            == 200
        )
        assert client.post(f"/runs/{run_id}/cancel").status_code == 200
        assert client.get(f"/runs/{run_id}").json()["status"] == "failed"
        assert client.post("/runs", content=b"x" * 1048577).status_code == 413

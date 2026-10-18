import asyncio

import pytest
from fastapi.testclient import TestClient

from pp_anchor import ActivityRegistry, ConflictError, Definition, Engine, Step, Worker, drain
from pp_anchor.api.app import create_app
from pp_anchor.persistence.engine import AdmissionError


def test_admission_and_idempotency_during_overload(engine, dsn):
    with Engine(dsn, engine.schema, max_active_runs=1) as limited:
        definition = Definition("limited", 1, (Step("wait", kind="signal", signal="go"),))
        run_id = limited.submit(definition, {}, "first")
        assert limited.submit(definition, {}, "first") == run_id
        with pytest.raises(AdmissionError):
            limited.submit(definition, {}, "second")
        with TestClient(create_app(limited)) as client:
            response = client.post(
                "/runs",
                json={
                    "definition": definition.to_dict(),
                    "payload": {},
                    "idempotency_key": "third",
                },
            )
            assert response.status_code == 429
        limited.cancel(run_id)
        assert limited.submit(definition, {}, "second") != run_id
    with pytest.raises(ValueError):
        Engine(dsn, "bad;drop")
    with pytest.raises(ValueError):
        Engine(dsn, "anchor", max_active_runs=0)


def test_signals_conflicts_closed_state_and_size(engine):
    definition = Definition("wait", 1, (Step("wait", kind="signal", signal="go"),))
    run_id = engine.submit(definition, {}, "signal")
    engine.signal(run_id, "unrelated", {"v": 1}, "first")
    with pytest.raises(ConflictError):
        engine.signal(run_id, "unrelated", {"v": 2}, "other-key")
    with pytest.raises(ValueError):
        engine.signal(run_id, "", {}, "invalid")
    with pytest.raises(ValueError):
        engine.signal(run_id, "large", {"x": "x" * 1048577}, "large")
    engine.signal(run_id, "go", {}, "go")
    assert engine.status(run_id)["status"] == "completed"
    assert engine.signal(run_id, "go", {}, "go") == run_id
    with pytest.raises(ConflictError):
        engine.signal(run_id, "more", {}, "closed")
    assert engine.cancel(run_id)["status"] == "completed"
    with pytest.raises(ValueError):
        engine.submit(definition, {"x": "x" * 1048577}, "large")
    with pytest.raises(ValueError):
        engine.submit(definition, {}, "")
    with TestClient(create_app(engine)) as client:
        assert (
            client.post("/runs", json={"definition": {}, "idempotency_key": "invalid"}).status_code
            == 422
        )


def test_missing_runs_claim_exhaustion_and_provider_conflicts(engine):
    with pytest.raises(KeyError):
        engine.history("missing")
    assert engine.claim() is None
    with pytest.raises(ValueError):
        engine.claim(0)
    run_id = engine.submit(Definition("exhaust", 1, (Step("x", max_attempts=1),)), {}, "exhaust")
    task = engine.claim(0.001)
    assert task
    import time

    time.sleep(0.01)
    assert engine.claim() is None
    assert engine.status(run_id)["status"] == "failed"
    assert engine.publish("business", {"x": 1})["publications"] == 1
    with pytest.raises(ConflictError):
        engine.publish("business", {"x": 2})
    with pytest.raises(ValueError):
        engine.heartbeat(task, 0)


def test_real_heartbeat_retains_long_activity_and_cancellation(engine):
    run_id = engine.submit(Definition("slow", 1, (Step("slow", activity="slow"),)), {}, "slow")
    registry = ActivityRegistry()

    async def slow(context):
        await asyncio.sleep(1.5)
        return {"ok": True}

    registry.register("slow", slow)
    with pytest.raises(ValueError):
        registry.register("slow", slow)
    with pytest.raises(ValueError):
        Worker(engine, concurrency=0)

    async def run():
        worker = Worker(engine, registry, lease_seconds=1)
        task = asyncio.create_task(worker.run_once())
        await asyncio.sleep(1.1)
        assert await asyncio.to_thread(engine.claim) is None
        assert await task

    asyncio.run(run())
    assert engine.status(run_id)["status"] == "completed"
    assert engine.metrics()["ready_to_start_p95_seconds"] >= 0
    run_id = engine.submit(Definition("cancel", 1, (Step("slow", activity="slow"),)), {}, "cancel")

    async def cancel():
        worker = Worker(engine, registry)
        task = asyncio.create_task(worker.run_once())
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())
    assert engine.status(run_id)["status"] == "running"
    engine.cancel(run_id)
    asyncio.run(drain(engine))


def test_oversized_result_not_acknowledged_and_no_heartbeat_mode(engine):
    run_id = engine.submit(Definition("result", 1, (Step("x"),)), {}, "result")
    task = engine.claim()
    assert task
    with pytest.raises(ValueError):
        engine.finish(task, {"huge": "x" * 1048577})
    engine.finish(task, {})
    assert engine.status(run_id)["status"] == "completed"
    run_id = engine.submit(Definition("nohb", 1, (Step("x"),)), {}, "nohb")
    assert asyncio.run(Worker(engine, heartbeat=False).run_once())
    assert engine.status(run_id)["status"] == "completed"


def test_empty_error_is_a_failed_attempt(engine):
    run_id = engine.submit(
        Definition("empty-error", 1, (Step("x", max_attempts=1),)), {}, "empty-error"
    )
    task = engine.claim()
    assert task
    engine.finish(task, error="")
    assert engine.status(run_id)["status"] == "failed"
    assert engine.history(run_id)[-1].kind == "step_failed"
    with engine.transaction() as c:
        assert c.execute(
            "SELECT status FROM activity_attempts WHERE workflow_id=%s", (run_id,)
        ).fetchone() == {"status": "failed"}


@pytest.mark.parametrize("result", [{"huge": "x" * 1048577}, {"nan": float("nan")}])
@pytest.mark.parametrize("heartbeat", [False, True])
def test_invalid_activity_result_retries_without_stopping_worker(engine, result, heartbeat):
    run_id = engine.submit(
        Definition(
            "invalid-result", 1, (Step("x", activity="invalid", max_attempts=2, retry_delay=0),)
        ),
        {},
        "invalid-result",
    )
    registry = ActivityRegistry()

    async def invalid(context):
        return result

    registry.register("invalid", invalid)
    worker = Worker(engine, registry, heartbeat=heartbeat)
    assert asyncio.run(worker.run_once())
    assert engine.status(run_id)["status"] == "running"
    assert engine.history(run_id)[-1].kind == "retry_scheduled"
    assert asyncio.run(worker.run_once())
    assert engine.status(run_id)["status"] == "failed"
    assert engine.history(run_id)[-1].kind == "step_failed"


def test_maximum_length_internal_chain_completes_without_recursion(engine):
    steps = tuple(
        Step(f"join_{i}", kind="join", after=(f"join_{i - 1}",) if i else ()) for i in range(1000)
    )
    run_id = engine.submit(Definition("long-chain", 1, steps), {}, "long-chain")
    state = engine.replay(run_id)
    assert state.status == "completed"
    assert state.done == {step.name for step in steps}
    history = engine.history(run_id)
    assert len(history) == 1001
    assert [event.step for event in history[1:]] == [step.name for step in steps]
    assert history[-1].commands == ("terminal:completed",)

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from pp_anchor import ActivityRegistry, ConflictError, Definition, Engine, Step, Worker, drain
from pp_anchor.api.app import create_app
from pp_anchor.persistence.engine import AdmissionError


@pytest.mark.parametrize("text", ["\x00", "\ud800"])
def test_http_rejects_nonrepresentable_payload_text_without_database_error(engine, text):
    definition = Definition("json-boundary", 1, (Step("work"),))
    request = {
        "definition": definition.to_dict(),
        "payload": {"text": text},
        "idempotency_key": "invalid-json-text",
    }
    with TestClient(create_app(engine), raise_server_exceptions=False) as client:
        response = client.post(
            "/runs",
            content=json.dumps(request).encode(),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422, response.text
    assert engine.metrics()["runs"] == {}


def test_http_signal_payload_is_validated_before_database_write(engine):
    run_id = engine.submit(
        Definition("json-signal", 1, (Step("wait", kind="signal", signal="go"),)), {}, "signal-run"
    )
    before = engine.history(run_id)
    with TestClient(create_app(engine), raise_server_exceptions=False) as client:
        response = client.post(
            f"/runs/{run_id}/signals",
            content=b'{"name":"go","payload":{"text":"\\u0000"},"idempotency_key":"signal"}',
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422
    assert engine.history(run_id) == before


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


def test_history_pagination_matches_full_history_and_bounds_query(engine):
    definition = Definition("page", 1, tuple(Step(f"s{i}", kind="join") for i in range(7)))
    run_id = engine.submit(definition, {}, "page")
    full = engine.history(run_id)
    assert len(full) == 8
    collected = []
    after = 0
    with TestClient(create_app(engine)) as client:
        while True:
            response = client.get(f"/runs/{run_id}/history", params={"after": after, "limit": 3})
            assert response.status_code == 200
            page = response.json()
            if not page["events"]:
                assert page["next_after"] == after
                break
            assert len(page["events"]) <= 3
            collected.extend(page["events"])
            after = page["next_after"]
    assert [event["seq"] for event in collected] == [event.seq for event in full]
    assert engine.history(run_id, after=2, limit=3) == full[2:5]
    assert engine.history(run_id, after=full[-1].seq, limit=3) == []


@pytest.mark.parametrize("after,limit", [(-1, 1), (True, 1), (0, 0), (0, 1001), (0, 1.5)])
def test_invalid_history_windows_are_rejected(engine, after, limit):
    with pytest.raises(ValueError):
        engine.history("unused", after=after, limit=limit)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 0, True, 10**1000])
def test_invalid_lease_cannot_mutate_task(engine, value):
    run_id = engine.submit(Definition("lease", 1, (Step("x"),)), {}, "lease")
    with pytest.raises(ValueError):
        engine.claim(value)
    task = engine.claim()
    assert task is not None
    with pytest.raises(ValueError):
        engine.heartbeat(task, value)
    with pytest.raises(ValueError):
        Worker(engine, lease_seconds=value)
    engine.finish(task)
    assert engine.status(run_id)["status"] == "completed"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True, 10**1000])
def test_invalid_timer_clock_offset_is_rejected(engine, value):
    with pytest.raises(ValueError):
        engine.tick(advance_seconds=value)


def test_unknown_http_request_fields_are_rejected(engine):
    with TestClient(create_app(engine)) as client:
        response = client.post(
            "/runs",
            json={
                "definition": Definition("strict", 1, (Step("x"),)).to_dict(),
                "idempotency_key": "strict",
                "paylod": {"important": "misspelled"},
            },
        )
    assert response.status_code == 422
    assert engine.metrics()["runs"] == {}


def test_maximum_retry_policy_remains_representable_in_database(engine):
    run_id = engine.submit(
        Definition("retry-cap", 1, (Step("x", max_attempts=32, retry_delay=31536000),)),
        {},
        "retry-cap",
    )
    for attempt in range(1, 33):
        task = engine.claim()
        assert task is not None and task.attempt_number == attempt
        engine.finish(task, error="still unavailable")
        event = engine.history(run_id)[-1]
        assert event.data["retry_delay"] == (31536000 if attempt < 32 else 0)
        if attempt < 32:
            # Exercise every allowed attempt without waiting on the real deadline.
            with engine.transaction() as c:
                c.execute(
                    "UPDATE activity_tasks SET available_at=clock_timestamp() WHERE workflow_id=%s",
                    (run_id,),
                )
    assert engine.status(run_id)["status"] == "failed"

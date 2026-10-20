"""Rollback must respect resource causality, including real provider constraints."""

import asyncio

import pytest

from pp_anchor import ActivityRegistry, Definition, Step, Worker
from pp_anchor.replay.reducer import DivergenceError


def test_dependent_cleanup_cannot_overtake_inflight_descendant(engine):
    definition = Definition(
        "resources",
        1,
        (
            Step("allocate", compensate="release", max_attempts=1),
            Step("publish", after=("allocate",), compensate="unpublish", max_attempts=1),
            Step("hold", after=("publish",), kind="signal", signal="retain"),
        ),
    )
    run_id = engine.submit(definition, {}, "resources")
    with engine.transaction() as connection:
        connection.execute(
            "CREATE TABLE resources(name text PRIMARY KEY, parent text REFERENCES resources)"
        )
        connection.execute(
            "INSERT INTO resources VALUES ('allocation',NULL),('publication','allocation')"
        )
    engine.finish(engine.claim())
    engine.finish(engine.claim())
    engine.cancel(run_id)

    def remove(name):
        with engine.transaction() as connection:
            connection.execute("DELETE FROM resources WHERE name=%s", (name,))

    async def exercise():
        started, release = asyncio.Event(), asyncio.Event()
        registry = ActivityRegistry()

        async def unpublish(context):
            started.set()
            await release.wait()
            await asyncio.to_thread(remove, "publication")
            return {}

        async def release_allocation(context):
            await asyncio.to_thread(remove, "allocation")
            return {}

        registry.register("unpublish", unpublish)
        registry.register("release", release_allocation)
        worker = Worker(engine, registry)
        descendant = asyncio.create_task(worker.run_once())
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            # A second worker must not release the FK parent while the child
            # cleanup is still in flight, even though both have pending undo.
            assert not await worker.run_once()
        finally:
            release.set()
            await descendant
        assert await worker.run_once()

    asyncio.run(exercise())
    assert engine.status(run_id)["status"] == "compensated"
    with engine.transaction() as connection:
        assert (
            connection.execute("SELECT count(*) AS count FROM resources").fetchone()["count"] == 0
        )


def test_timer_batch_loads_history_once_per_transaction(engine, monkeypatch):
    import psycopg

    run_id = engine.submit(
        Definition(
            "timer-batch", 1, tuple(Step(str(i), kind="timer", delay=60) for i in range(32))
        ),
        {},
        "timer-batch",
    )
    original = psycopg.Connection.execute
    reads = []

    def observed(connection, query, *args, **kwargs):
        if isinstance(query, str) and query.startswith("SELECT * FROM history_events"):
            reads.append(query)
        return original(connection, query, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(psycopg.Connection, "execute", observed)
        assert engine.tick(advance_seconds=61) == 32
    assert len(reads) == 1, "one run-row transaction must reuse its reconstructed reducer state"
    assert engine.replay(run_id).status == "completed"


def test_unknown_persisted_event_schema_is_never_silently_replayed(engine):
    run_id = engine.submit(Definition("versioned", 1, (Step("x"),)), {}, "versioned")
    with engine.transaction() as connection:
        connection.execute(
            "UPDATE history_events SET schema_version=999 WHERE workflow_id=%s", (run_id,)
        )
    with pytest.raises(DivergenceError, match="version"):
        engine.replay(run_id)


def test_failed_descendant_blocks_ancestors_but_not_independent_cleanup(engine):
    run_id = engine.submit(
        Definition(
            "fork",
            1,
            (
                Step("parent", compensate="undo", max_attempts=1),
                Step("left", after=("parent",), compensate="undo", max_attempts=1),
                Step("right", after=("parent",), compensate="undo", max_attempts=1),
                Step("hold", kind="signal", signal="hold", after=("left", "right")),
            ),
        ),
        {},
        "fork",
    )
    for _ in range(3):
        engine.finish(engine.claim())
    engine.cancel(run_id)
    first, second = engine.claim(), engine.claim()
    assert {first.step, second.step} == {"left", "right"}
    engine.finish(first, error="provider unavailable")
    engine.finish(second)
    assert engine.claim() is None
    assert engine.status(run_id)["compensation"]["parent"] == "blocked"
    engine.retry_compensation(run_id)
    repaired = engine.claim()
    assert repaired.step == first.step and repaired.lease_epoch > first.lease_epoch
    engine.finish(repaired)
    ancestor = engine.claim()
    assert ancestor.step == "parent"
    engine.finish(ancestor)
    assert engine.replay(run_id).status == "compensated"


def test_legacy_inflight_run_continues_without_rewriting_its_history(engine):
    run_id = engine.submit(
        Definition(
            "legacy",
            1,
            (
                Step("parent", compensate="undo"),
                Step("child", after=("parent",), compensate="undo"),
            ),
        ),
        {},
        "legacy",
    )
    with engine.transaction() as connection:
        connection.execute(
            "UPDATE history_events SET schema_version=1 WHERE workflow_id=%s", (run_id,)
        )
    engine.finish(engine.claim())
    held = engine.claim()
    engine.cancel(run_id)
    child = engine.claim()
    assert child.step == "child"
    assert engine.claim() is None
    engine.finish(child)
    parent = engine.claim()
    assert parent.step == "parent"
    engine.finish(parent)
    from pp_anchor import StaleLeaseError

    with pytest.raises(StaleLeaseError):
        engine.finish(held)
    assert {event.schema_version for event in engine.history(run_id)} == {1}
    assert engine.replay(run_id).status == "compensated"


def test_cancellation_closes_inflight_attempt_accounting(engine):
    run_id = engine.submit(
        Definition("cancel", 1, (Step("x", compensate="cleanup"),)), {}, "cancel-accounting"
    )
    task = engine.claim()
    engine.cancel(run_id)
    with engine.transaction() as connection:
        attempt = connection.execute(
            "SELECT status,finished_at IS NOT NULL AS finished FROM activity_attempts WHERE workflow_id=%s AND command_id=%s",
            (run_id, task.command_id),
        ).fetchone()
    assert attempt == {"status": "cancelled", "finished": True}


def test_projection_failure_rolls_back_history_tasks_and_replay_cache(engine, monkeypatch):
    import psycopg

    run_id = engine.submit(
        Definition(
            "atomic", 1, (Step("work"), Step("timer", after=("work",), kind="timer", delay=60))
        ),
        {},
        "atomic",
    )
    task = engine.claim()
    committed = engine.history(run_id)
    execute = psycopg.Connection.execute

    def fail_projection(connection, query, *args, **kwargs):
        if isinstance(query, str) and query.startswith("INSERT INTO timers"):
            raise RuntimeError("injected after history append, before timer projection")
        return execute(connection, query, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(psycopg.Connection, "execute", fail_projection)
        with pytest.raises(RuntimeError, match="injected"):
            engine.finish(task)
    assert engine.history(run_id) == committed
    with engine.transaction() as connection:
        assert (
            connection.execute(
                "SELECT status FROM activity_tasks WHERE workflow_id=%s", (run_id,)
            ).fetchone()["status"]
            == "running"
        )
        assert (
            connection.execute(
                "SELECT count(*) AS count FROM timers WHERE workflow_id=%s", (run_id,)
            ).fetchone()["count"]
            == 0
        )
    engine.finish(task)
    assert engine.tick(advance_seconds=61) == 1
    assert engine.replay(run_id).status == "completed"


@pytest.mark.parametrize(
    "damage",
    [
        "DELETE FROM history_events WHERE event_seq=1",
        "UPDATE workflow_runs SET event_seq=999",
        "UPDATE workflow_runs SET terminal_status='completed'",
    ],
)
def test_committed_projection_history_disagreement_is_rejected(engine, damage):
    run_id = engine.submit(Definition("damaged", 1, (Step("work"),)), {}, "damaged")
    with engine.transaction() as connection:
        connection.execute(damage)
    with pytest.raises(DivergenceError, match="projection"):
        engine.status(run_id)
    with pytest.raises(DivergenceError, match="projection"):
        engine.replay(run_id)


def test_reader_uses_one_snapshot_when_writer_commits_between_run_and_history(
    engine, dsn, monkeypatch
):
    from pp_anchor import Engine

    run_id = engine.submit(Definition("snapshot", 1, (Step("work"),)), {}, "snapshot")
    task = engine.claim()
    old_sequence = engine.status(run_id)["event_seq"]
    original = engine._events
    with Engine(dsn, engine.schema) as writer:

        def interleaved(connection, *args, **kwargs):
            writer.finish(task)
            return original(connection, *args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(engine, "_events", interleaved)
            snapshot = engine.status(run_id)
    assert snapshot["status"] == "running" and snapshot["event_seq"] == old_sequence
    assert engine.status(run_id)["status"] == "completed"


def test_process_death_mid_projection_leaves_one_recoverable_committed_attempt(
    engine, dsn, tmp_path
):
    import json
    import os
    import signal
    import subprocess
    import sys
    import textwrap
    from dataclasses import asdict

    run_id = engine.submit(
        Definition(
            "killed-transition",
            1,
            (Step("work"), Step("timer", kind="timer", delay=60, after=("work",))),
        ),
        {},
        "killed-transition",
    )
    first = engine.claim(30)
    committed = engine.history(run_id)
    marker = tmp_path / "inside-projection"
    code = textwrap.dedent("""
        import json,os,signal,sys
        from pathlib import Path
        import psycopg
        from pp_anchor import Engine
        from pp_anchor.persistence.engine import Task
        with Engine(os.environ['ANCHOR_DATABASE_URL'], sys.argv[1]) as engine:
            execute = psycopg.Connection.execute
            def crash(connection, query, *args, **kwargs):
                if isinstance(query, str) and query.startswith('INSERT INTO timers'):
                    Path(sys.argv[3]).write_text('history inserted; projection not committed')
                    os.kill(os.getpid(), signal.SIGKILL)
                return execute(connection, query, *args, **kwargs)
            psycopg.Connection.execute = crash
            engine.finish(Task(**json.loads(sys.argv[2])))
    """)
    result = subprocess.run(
        [sys.executable, "-c", code, engine.schema, json.dumps(asdict(first)), str(marker)],
        env={**os.environ, "ANCHOR_DATABASE_URL": dsn},
        timeout=20,
    )
    assert result.returncode == -signal.SIGKILL and marker.exists()
    assert engine.history(run_id) == committed
    with engine.transaction() as connection:
        connection.execute(
            "UPDATE activity_tasks SET lease_expiry=clock_timestamp()-interval '1 second' WHERE workflow_id=%s",
            (run_id,),
        )
    recovered = engine.claim()
    assert recovered.lease_epoch == first.lease_epoch + 1
    engine.finish(recovered)
    assert engine.tick(advance_seconds=61) == 1
    assert engine.replay(run_id).status == "completed"
    assert (
        sum(
            event.kind == "step_completed" and event.step == "work"
            for event in engine.history(run_id)
        )
        == 1
    )
    with engine.transaction() as connection:
        statuses = connection.execute(
            "SELECT status FROM activity_attempts WHERE workflow_id=%s ORDER BY attempt_number",
            (run_id,),
        ).fetchall()
    assert statuses == [{"status": "expired"}, {"status": "completed"}]

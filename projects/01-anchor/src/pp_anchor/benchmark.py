"""Seeded five-activity workloads; correctness is independently counted in SQL."""

import asyncio
import resource
import statistics
import time

from pp_anchor import ActivityContext, ActivityRegistry, Definition, Engine, Step, Worker, scheduler
from pp_anchor.definitions.model import JSON


async def workload(engine: Engine, count: int, concurrency: int, repetition: int) -> JSON:
    definition = Definition(
        "benchmark", 1, tuple(Step(f"s{i}", after=(f"s{i - 1}",) if i else ()) for i in range(5))
    )
    registry = ActivityRegistry()

    async def measured_activity(context: ActivityContext) -> JSON:
        if (
            context.task.step == "s2"
            and int(str(context.task.payload["index"])) % 20 == 0
            and context.task.attempt_number == 1
        ):
            raise RuntimeError("Seeded transient at fixed workload identity")
        return {"ok": True}

    registry.handlers["identity"] = measured_activity
    started = time.perf_counter()
    # Admission is included in throughput, so offered and completed load remain explicit.
    for index in range(count):
        await asyncio.to_thread(
            engine.submit, definition, {"index": index}, f"bench-{repetition}-{index}"
        )
    admission_seconds = time.perf_counter() - started
    stop = asyncio.Event()
    async with asyncio.timeout(1800), asyncio.TaskGroup() as group:
        group.create_task(Worker(engine, registry, concurrency=concurrency).run(stop))
        group.create_task(scheduler(engine, stop))
        group.create_task(scheduler(engine, stop))
        try:
            while True:
                with engine.transaction() as c:
                    row = c.execute(
                        "SELECT count(*) AS count FROM workflow_runs WHERE terminal_status='completed'"
                    ).fetchone()
                if row and int(str(row["count"])) == count:
                    break
                await asyncio.sleep(0.02)
        finally:
            stop.set()
    elapsed = time.perf_counter() - started
    with engine.transaction() as c:
        attempts = c.execute("SELECT count(*) AS count FROM activity_attempts").fetchone()
        orphan = c.execute(
            "SELECT count(*) AS count FROM activity_tasks WHERE status NOT IN ('completed','cancelled')"
        ).fetchone()
    assert attempts and attempts["count"] == count * 5 + (count + 19) // 20
    assert orphan and orphan["count"] == 0
    return {
        "elapsed_seconds": elapsed,
        "admission_seconds": admission_seconds,
        "offered_workflows": count,
        "completed_workflows": count,
        "activities": count * 5,
        "execution_attempts": attempts["count"],
        "injected_failures": (count + 19) // 20,
        "admitted_queue_depth": count,
        "workflows_per_second": count / elapsed,
        "metrics": engine.metrics(),
    }


def run_benchmark(dsn: str, schema: str, parameters: JSON) -> JSON:
    from pp_anchor.cli import drop_schema

    count, concurrency = (
        int(str(parameters["workflows"])),
        int(str(parameters["worker_concurrency"])),
    )
    runs: list[JSON] = []
    measurement_runs = int(str(parameters.get("measurement_runs", 5)))
    for repetition in range(1 + measurement_runs):
        with Engine(dsn, schema) as engine:
            result = asyncio.run(
                workload(
                    engine, min(count, 10) if repetition == 0 else count, concurrency, repetition
                )
            )
        drop_schema(dsn, schema)
        if repetition:
            runs.append(result)
    with Engine(dsn, schema) as engine:
        run_id = engine.submit(
            Definition("future-timer-probe", 1, (Step("future", kind="timer", delay=86400),)),
            {},
            "timer-probe",
        )
        memory_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        timer_start = time.perf_counter()
        with engine.transaction() as c:
            c.execute(
                "INSERT INTO timers(workflow_id,command_id,step,due_at) SELECT %s,'probe:'||i,'future',clock_timestamp()+interval '1 day' FROM generate_series(1,99999) i",
                (run_id,),
            )
        tick_start = time.perf_counter()
        fired = engine.tick()
        tick_elapsed = time.perf_counter() - tick_start
        with engine.transaction() as c:
            row = c.execute("SELECT count(*) AS count FROM timers").fetchone()
        assert row and row["count"] == 100000 and fired == 0
        memory_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        timer_result: JSON = {
            "timers": 100000,
            "loaded_seconds": time.perf_counter() - timer_start,
            "idle_tick_seconds": tick_elapsed,
            "fired": fired,
            "maxrss_growth_kib": memory_after - memory_before,
            "fixture": "isolated bulk future timer projection; no suspended timer coroutines",
        }
    drop_schema(dsn, schema)
    with Engine(dsn, schema) as engine:
        recovery_id = engine.submit(
            Definition("recovery-probe", 1, (Step("publish", activity="publish"),)), {}, "recovery"
        )
        abandoned = engine.claim(0.1)
        assert abandoned is not None
        engine.publish(recovery_id, {})
        recovery_start = time.perf_counter()
        time.sleep(0.11)
        assert asyncio.run(Worker(engine).run_once())
        recovery_seconds = time.perf_counter() - recovery_start
        assert engine.replay(recovery_id).status == "completed"
        with engine.transaction() as c:
            effect = c.execute(
                "SELECT publications FROM provider_effects WHERE business_key=%s", (recovery_id,)
            ).fetchone()
        assert effect and effect["publications"] == 1
    drop_schema(dsn, schema)
    throughputs = [float(str(r["workflows_per_second"])) for r in runs]
    return {
        "status": "passed",
        "metrics": {
            "repetitions": runs,
            "median_workflows_per_second": statistics.median(throughputs),
            "min_workflows_per_second": min(throughputs),
            "maxrss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "future_timer_probe": timer_result,
            "lease_recovery_seconds": recovery_seconds,
        },
        "correctness_checks": {
            "all_accepted_completed": True,
            "five_activities_per_run": True,
            "orphan_tasks": 0,
            "future_timers_remain_durable": True,
        },
    }

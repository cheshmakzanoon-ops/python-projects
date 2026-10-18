"""Safe local CLI; all generated state belongs to an explicit output directory."""

import asyncio
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import psycopg
import typer
from psycopg import sql

from pp_anchor import Definition, Engine, Step, Worker, scheduler
from pp_anchor.definitions.model import JSON
from pp_anchor.examples import definition_json, export_definition, export_registry
from pp_anchor.observability.evidence import source_evidence

app = typer.Typer(no_args_is_help=True)


def database_url() -> str:
    dsn = os.environ.get("ANCHOR_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        raise typer.BadParameter("Set ANCHOR_DATABASE_URL to an accessible PostgreSQL database")
    return dsn


def output_directory(output: Path) -> Path:
    if not output.is_absolute() or output == Path("/"):
        raise ValueError("--output must name an absolute owned directory")
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("Symlink output paths are forbidden")
    output.mkdir(parents=True, exist_ok=True)
    if list(output.iterdir()):
        raise ValueError("Output directory must be empty; use clean-demo on previous owned state")
    return output


def owned(output: Path, kind: str) -> tuple[Path, str]:
    output = output_directory(output)
    schema = f"anchor_{kind}_{uuid.uuid4().hex[:20]}"
    (output / ".anchor-owned.json").write_text(
        json.dumps({"schema_version": 1, "schema": schema, "kind": kind, "output": str(output)})
    )
    return output, schema


def drop_schema(dsn: str, schema: str) -> None:
    if not re.fullmatch(r"anchor_(demo|bench)_[0-9a-f]{20}", schema):
        raise ValueError("Refusing to remove a schema outside owned demo namespace")
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))


async def wait_terminal(
    engine: Engine, run_id: str, worker: Worker, *, timeout: float = 30
) -> None:
    async with asyncio.timeout(timeout):
        stop = asyncio.Event()
        async with asyncio.TaskGroup() as group:
            group.create_task(worker.run(stop))
            group.create_task(scheduler(engine, stop))
            try:
                while engine.status(run_id)["status"] in ("running", "compensating"):
                    await asyncio.sleep(0.02)
            finally:
                stop.set()


@app.command()
def demo(output: Annotated[Path, typer.Option()], seed: int = 1729) -> None:
    output, schema = owned(output, "demo")
    dsn = database_url()
    with Engine(dsn, schema) as engine:
        run_id = engine.submit(export_definition(), {"rows": 60, "seed": seed}, f"demo-{seed}")
        engine.signal(run_id, "approve", {"approved": True}, "approval")
        registry = export_registry(output)
        worker = Worker(engine, registry, concurrency=4, lease_seconds=0.5)

        # Run preceding stages; explicitly stop before provider task and execute it in a killable process.
        async def prepare() -> None:
            async with asyncio.timeout(30):
                while True:
                    await asyncio.to_thread(engine.tick)
                    with engine.transaction() as c:
                        row = c.execute(
                            "SELECT 1 FROM activity_tasks WHERE workflow_id=%s AND activity='publish'",
                            (run_id,),
                        ).fetchone()
                    if row:
                        return
                    await asyncio.gather(*(worker.run_once() for _ in range(4)))
                    await asyncio.sleep(0.01)

        asyncio.run(prepare())
        ready = output / "effect-recorded.json"
        command = [
            sys.executable,
            "-m",
            "pp_anchor.cli",
            "fault-worker",
            "--schema",
            schema,
            "--ready-file",
            str(ready),
            "--mode",
            "effect",
        ]
        process = subprocess.Popen(command)
        try:
            deadline = time.monotonic() + 30
            while not ready.exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Fault worker did not reach provider boundary")
                time.sleep(0.01)
            recovery_start = time.perf_counter()
            process.kill()
            process.wait(timeout=5)
            time.sleep(0.55)
            asyncio.run(wait_terminal(engine, run_id, worker))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        state = engine.replay(run_id)
        with engine.transaction() as c:
            provider = c.execute(
                "SELECT publications,fenced FROM provider_effects WHERE business_key=%s", (run_id,)
            ).fetchone()
        if state.status != "completed" or provider != {"publications": 1, "fenced": False}:
            raise RuntimeError("Demo recovery correctness check failed")
        history = engine.history(run_id)
        report: JSON = {
            "schema_version": 1,
            "workflow_id": run_id,
            "schema": schema,
            "seed": seed,
            "status": state.status,
            "provider": provider,
            "worker_killed": True,
            "replay_verified": True,
            "recovery_seconds": time.perf_counter() - recovery_start,
            "events": [asdict(e) for e in history],
            "metrics": engine.metrics(),
        }
        (output / "history.json").write_text(json.dumps(report, indent=2, default=str))
        timeline = "\n".join(f"{e.seq:03d} {e.kind:24s} {e.step:16s} {e.data}" for e in history)
        (output / "timeline.txt").write_text(timeline + "\n")
        typer.echo(timeline)
        typer.echo(
            f"Completed {run_id}; one publication; killed worker recovered; replay verified."
        )


@app.command("fault-worker", hidden=True)
def fault_worker(
    schema: Annotated[str, typer.Option()],
    ready_file: Annotated[Path, typer.Option()],
    mode: str = "effect",
    resume_file: Path | None = None,
    outcome_file: Path | None = None,
) -> None:
    with Engine(database_url(), schema) as engine:
        task = engine.claim(0.5)
        if task is None:
            raise RuntimeError("No activity to fault")
        if mode == "effect":
            engine.publish(task.workflow_id, task.payload)
        ready_file.write_text(json.dumps(asdict(task)))
        if resume_file is not None:
            deadline = time.monotonic() + 30
            while not resume_file.exists():
                if time.monotonic() > deadline:
                    raise TimeoutError("Paused test worker was not resumed")
                time.sleep(0.01)
            outcomes: dict[str, str] = {}
            for operation, action in (
                ("publish", lambda: engine.publish(task.workflow_id, task.payload)),
                ("heartbeat", lambda: engine.heartbeat(task)),
                ("finish", lambda: engine.finish(task)),
            ):
                try:
                    action()
                except Exception as exc:
                    outcomes[operation] = type(exc).__name__
                else:
                    outcomes[operation] = "accepted"
            if outcome_file is None:
                raise ValueError("Resuming requires outcome file")
            outcome_file.write_text(json.dumps(outcomes))
            return
        while True:
            time.sleep(1)


@app.command("fault-submit", hidden=True)
def fault_submit(
    schema: Annotated[str, typer.Option()],
    stage: Annotated[str, typer.Option()],
    key: str = "crash",
) -> None:
    def hook(point: str) -> None:
        if point == stage:
            os.kill(os.getpid(), signal.SIGKILL)

    with Engine(database_url(), schema) as engine:
        engine.submit(Definition("crash", 1, (Step("one"),)), {}, key, crash_hook=hook)


@app.command("clean-demo")
def clean_demo(output: Annotated[Path, typer.Option()]) -> None:
    if not output.is_absolute() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("Absolute non-symlink owned output required")
    marker = output / ".anchor-owned.json"
    if not marker.is_file():
        raise ValueError("No Anchor ownership marker; refusing deletion")
    value = json.loads(marker.read_text())
    if value.get("output") != str(output) or value.get("schema_version") != 1:
        raise ValueError("Ownership marker does not match directory")
    allowed = {
        ".anchor-owned.json",
        "effect-recorded.json",
        "dataset.zip",
        "history.json",
        "timeline.txt",
        "benchmark.json",
        "partition-0.csv",
        "partition-1.csv",
        "partition-2.csv",
    }
    if any(p.name not in allowed or not p.is_file() or p.is_symlink() for p in output.iterdir()):
        raise ValueError("Unknown files in owned directory; refusing deletion")
    drop_schema(database_url(), value["schema"])
    for path in output.iterdir():
        path.unlink()
    output.rmdir()
    typer.echo("Removed only owned Anchor demo state")


@app.command()
def submit(definition: Path, payload: Path, key: str, schema: str = "anchor") -> None:
    with Engine(database_url(), schema) as engine:
        typer.echo(engine.submit(definition_json(definition), json.loads(payload.read_text()), key))


@app.command()
def inspect(run_id: str, schema: str = "anchor") -> None:
    with Engine(database_url(), schema) as engine:
        typer.echo(json.dumps(engine.status(run_id)))


@app.command("replay")
def replay_command(run_id: str, schema: str = "anchor") -> None:
    with Engine(database_url(), schema) as engine:
        typer.echo(f"Replay verified: {engine.replay(run_id).status}")


@app.command("worker")
def worker_command(schema: str = "anchor", concurrency: int = 4) -> None:
    with Engine(database_url(), schema) as engine:
        asyncio.run(Worker(engine, concurrency=concurrency).run(asyncio.Event()))


@app.command("scheduler")
def scheduler_command(schema: str = "anchor") -> None:
    with Engine(database_url(), schema) as engine:
        asyncio.run(scheduler(engine, asyncio.Event()))


@app.command("backup")
def backup_command(path: Path, schema: str = "anchor") -> None:
    from pp_anchor.persistence.snapshot import backup

    with Engine(database_url(), schema) as engine:
        backup(engine, path)
    typer.echo("Version-one snapshot written")


@app.command("restore")
def restore_command(path: Path, schema: str = "anchor") -> None:
    from pp_anchor.persistence.snapshot import restore

    with Engine(database_url(), schema) as engine:
        restore(engine, path)
    typer.echo("Snapshot restored into empty target")


@app.command()
def serve(schema: str = "anchor", port: int = 8101) -> None:
    import uvicorn

    from pp_anchor.api.app import create_app

    with Engine(database_url(), schema) as engine:
        uvicorn.run(create_app(engine), host="127.0.0.1", port=port)


@app.command()
def benchmark(
    output: Annotated[Path, typer.Option()],
    profile: str = "ci",
    seed: int = 1729,
    concurrency: int = 8,
) -> None:
    from pp_anchor.benchmark import run_benchmark

    if profile not in ("ci", "standard"):
        raise ValueError("profile must be ci or standard")
    output, schema = owned(output, "bench")
    parameters: JSON = {
        "workflows": 100 if profile == "ci" else 5000,
        "measurement_runs": 5 if profile == "ci" else 1,
        "repetition_justification": "Five ci measurements; one full standard measurement because the full durable workload takes tens of minutes on this host",
        "activities_per_workflow": 5,
        "schedulers": 2,
        "worker_concurrency": concurrency,
        "threads": 1,
        "future_timers": 100000,
        "durability": "PostgreSQL synchronous_commit=on; fsync=on",
    }
    report = source_evidence(seed, profile, parameters)
    report.update(run_benchmark(database_url(), schema, parameters))
    after = source_evidence(seed, profile, parameters)
    if (
        report["source_content_sha256"] != after["source_content_sha256"]
        or report["root_contract_sha256"] != after["root_contract_sha256"]
    ):
        raise RuntimeError("Source changed during benchmark; discard measurements")
    (output / "benchmark.json").write_text(json.dumps(report, indent=2, default=str))
    typer.echo(json.dumps(report["metrics"], indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()

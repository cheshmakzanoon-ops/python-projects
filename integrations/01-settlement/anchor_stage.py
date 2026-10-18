"""Kill after a real ledger commit, retry a stable key, then compensate another run."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

import psycopg
from pp_anchor import ActivityContext, ActivityRegistry, Definition, Engine, Step, Worker
from psycopg import sql


def request(output: Path, path: str, key: str, payload: dict) -> dict:
    configuration = json.loads((output / "local-connection.json").read_text())
    credentials = base64.b64encode(
        f"{configuration['username']}:{configuration['password']}".encode()
    ).decode()
    operation = Request(
        configuration["base_url"] + path,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Basic " + credentials,
            "X-Tenant-ID": configuration["tenant_id"],
            "Idempotency-Key": key,
        },
        method="POST",
    )
    # Loopback requests deliberately bypass outbound network proxies.
    with build_opener(ProxyHandler({})).open(operation, timeout=10) as response:
        result = json.load(response)
    with (output / "http-requests.ndjson").open("a") as stream:
        stream.write(
            json.dumps(
                {"path": path, "idempotency_key": key, "payload": payload, "response": result},
                sort_keys=True,
            )
            + "\n"
        )
    return result


def registry(output: Path, pause: bool = False) -> ActivityRegistry:
    handlers = ActivityRegistry()

    async def posting(context: ActivityContext) -> dict[str, object]:
        configuration = json.loads((output / "local-connection.json").read_text())
        result = await asyncio.to_thread(
            request,
            output,
            "/api/v1/journals",
            context.business_key + ":post",
            configuration["journal"],
        )
        if pause:
            (output / "commit-received.json").write_text(json.dumps(result))
            await asyncio.sleep(3600)
        return {"journal_id": result["id"]}

    async def reversing(context: ActivityContext) -> dict[str, object]:
        original = await posting(context)
        result = await asyncio.to_thread(
            request,
            output,
            f"/api/v1/journals/{original['journal_id']}/reversal",
            context.business_key + ":reverse",
            {},
        )
        return {"reversal_id": result["id"]}

    handlers.register("ledger_post", posting)
    handlers.register("ledger_reverse", reversing)
    return handlers


async def complete(engine: Engine, output: Path, run_id: str) -> None:
    worker = Worker(engine, registry(output), lease_seconds=0.25, heartbeat=False)
    async with asyncio.timeout(60):
        while engine.status(run_id)["status"] in {"running", "compensating"}:
            await asyncio.to_thread(engine.tick)
            if not await worker.run_once():
                await asyncio.sleep(0.02)


def run(output: Path, mode: str, schema: str | None) -> None:
    dsn = os.environ["ANCHOR_DATABASE_URL"]
    if mode == "worker":
        assert schema is not None
        with Engine(dsn, schema) as engine:
            asyncio.run(
                Worker(
                    engine, registry(output, pause=True), lease_seconds=0.25, heartbeat=False
                ).run_once()
            )
        return
    schema = "anchor_integration_" + uuid.uuid4().hex[:20]
    try:
        with Engine(dsn, schema) as engine:
            definition = Definition("settlement", 1, (Step("post", "ledger_post"),))
            run_id = engine.submit(definition, {}, "settlement-recovery")
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--output",
                str(output),
                "--mode",
                "worker",
                "--schema",
                schema,
            ]
            child = subprocess.Popen(command)
            try:
                deadline = time.monotonic() + 30
                ready = output / "commit-received.json"
                while not ready.exists():
                    if child.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("worker did not reach committed HTTP effect boundary")
                    time.sleep(0.02)
                original = json.loads(ready.read_text())
                child.kill()
                child.wait(timeout=5)
                time.sleep(0.30)
                asyncio.run(complete(engine, output, run_id))
                state = engine.replay(run_id)
                assert state.status == "completed"
                attempts = [asdict(e) for e in engine.history(run_id)]
                requests = [
                    json.loads(line)
                    for line in (output / "http-requests.ndjson").read_text().splitlines()
                ]
                original_requests = [
                    r for r in requests if r["idempotency_key"] == run_id + ":post"
                ]
                assert len(original_requests) == 2
                assert {r["response"]["id"] for r in original_requests} == {original["id"]}
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
            compensation_definition = Definition(
                "reversal-after-confirmation",
                1,
                (
                    Step("post", "ledger_post", compensate="ledger_reverse"),
                    Step("later-failure", "fail", after=("post",), max_attempts=1),
                ),
            )
            compensated = engine.submit(compensation_definition, {}, "settlement-compensation")
            asyncio.run(complete(engine, output, compensated))
            final = engine.replay(compensated)
            assert final.status == "compensated" and final.compensation == {"post": "completed"}
            report = {
                "first_run": run_id,
                "first_journal_id": original["id"],
                "worker_was_killed_after_commit": True,
                "first_status": state.status,
                "first_history": attempts,
                "compensation_run": compensated,
                "compensation_status": final.status,
                "compensation_history": [asdict(e) for e in engine.history(compensated)],
            }
            (output / "anchor-evidence.json").write_text(json.dumps(report, indent=2) + "\n")
    finally:
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=["coordinator", "worker"], default="coordinator")
    parser.add_argument("--schema")
    args = parser.parse_args()
    run(args.output, args.mode, args.schema)

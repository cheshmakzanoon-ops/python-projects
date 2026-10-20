"""Bounded scheduler diagnostic; one sample per width, no capacity claim."""

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import psycopg
from psycopg import sql

from pp_anchor import Definition, Engine, Step
from pp_anchor.observability.evidence import source_evidence


def measure(dsn: str, width: int) -> dict[str, object]:
    schema = "anchor_probe_" + uuid.uuid4().hex[:20]
    try:
        with Engine(dsn, schema) as engine:
            run_id = engine.submit(
                Definition(
                    "due-timer-batch",
                    1,
                    tuple(Step(str(i), kind="timer", delay=1) for i in range(width)),
                ),
                {},
                "batch",
            )
            original = psycopg.Connection.execute
            history_reads = 0

            def observed(connection, query, *args, **kwargs):
                nonlocal history_reads
                if isinstance(query, str) and query.startswith("SELECT * FROM history_events"):
                    history_reads += 1
                return original(connection, query, *args, **kwargs)

            with patch.object(psycopg.Connection, "execute", observed):
                started = time.perf_counter()
                fired = engine.tick(advance_seconds=2)
                elapsed = time.perf_counter() - started
            state = engine.replay(run_id)
            assert fired == width and state.status == "completed" and len(state.done) == width
            assert history_reads == 1
            with engine.transaction() as connection:
                unfired = connection.execute(
                    "SELECT count(*) AS count FROM timers WHERE NOT fired"
                ).fetchone()["count"]
            assert unfired == 0
            return {
                "timers": width,
                "seconds": elapsed,
                "history_reads": history_reads,
                "events": state.seq,
                "unfired": unfired,
                "status": state.status,
            }
    finally:
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    widths = [32, 128, 512, 1000]
    parameters = {
        "widths": widths,
        "measurement_runs": 1,
        "timing_scope": "tick eligibility, one run transition batch and commit; excludes submission and final replay",
    }
    report = source_evidence(1729, "transaction-batch", parameters)
    report["measurements"] = [measure(os.environ["ANCHOR_DATABASE_URL"], width) for width in widths]
    report["limitations"] = (
        "One sample per width on a shared host. Demonstrates bounded history loading and exact completion, not a throughput or latency guarantee."
    )
    after = source_evidence(1729, "transaction-batch", parameters)
    assert report["source_content_sha256"] == after["source_content_sha256"]
    report["source_unchanged"] = True
    with arguments.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(report["measurements"], indent=2))


if __name__ == "__main__":
    main()

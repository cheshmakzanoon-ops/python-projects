"""PostgreSQL transaction adapter. All mutations lock the run before its projections."""

import hashlib
import math
import re
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.resources import files
from typing import cast

import psycopg
from psycopg import Connection, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from pp_anchor.definitions.model import JSON, Definition, canonical, validate_activity_result
from pp_anchor.history.events import HistoryEvent
from pp_anchor.persistence.transition import RunTransaction
from pp_anchor.replay.reducer import DivergenceError, WorkflowState, replay

Row = dict[str, object]


def validate_lease_seconds(value: float) -> None:
    """Reject unusable leases before they can strand a running task in PostgreSQL."""
    if type(value) not in (int, float) or not 0 < value <= 31536000 or not math.isfinite(value):
        raise ValueError("lease_seconds must be finite seconds in (0, 31536000]")


def retry_delay(base: float, attempt: int) -> float:
    """Cap before exponentiation; operator retry batches can exceed 1,024 attempts."""
    if base == 0:
        return 0.0
    exponent = attempt - 1
    if exponent >= math.log2(31536000) - math.log2(base):
        return 31536000.0
    return min(math.ldexp(base, exponent), 31536000.0)


class AdmissionError(RuntimeError):
    pass


class ConflictError(ValueError):
    pass


class StaleLeaseError(RuntimeError):
    pass


class ProviderFencedError(RuntimeError):
    pass


@dataclass(frozen=True)
class Task:
    workflow_id: str
    command_id: str
    step: str
    activity: str
    attempt_number: int
    lease_epoch: int
    compensation: bool
    payload: JSON


class Engine:
    """An isolated schema is the ownership boundary; never use a sibling's schema."""

    def __init__(
        self,
        dsn: str,
        schema: str = "anchor",
        *,
        max_connections: int = 12,
        max_active_runs: int = 10000,
    ) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,50}", schema):
            raise ValueError("schema must be a simple lowercase identifier")
        if max_active_runs < 1:
            raise ValueError("max_active_runs must be positive")
        self.max_active_runs = max_active_runs
        self.dsn, self.schema = dsn, schema
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
            )
            connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            # Serialize migrations across independently starting scheduler/worker processes.
            with connection.transaction():
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (f"anchor:migrate:{schema}",),
                )
                connection.execute(
                    files("pp_anchor.persistence").joinpath("schema.sql").read_text()
                )
        self.pool: ConnectionPool[Connection[Row]] = ConnectionPool(
            dsn,
            min_size=0,
            open=True,
            max_size=max_connections,
            kwargs={"row_factory": dict_row, "options": f"-c search_path={schema}"},
        )

    def close(self) -> None:
        self.pool.close()

    def __enter__(self) -> "Engine":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[Connection[Row]]:
        with self.pool.connection() as connection, connection.transaction():
            yield connection

    def _run(self, c: Connection[Row], run_id: str, *, lock: bool = False) -> Row:
        row = c.execute(
            "SELECT * FROM workflow_runs WHERE workflow_id=%s" + (" FOR UPDATE" if lock else ""),
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return row

    def _events(
        self, c: Connection[Row], run_id: str, *, after: int = 0, limit: int | None = None
    ) -> list[HistoryEvent]:
        rows = c.execute(
            "SELECT * FROM history_events WHERE workflow_id=%s AND event_seq>%s ORDER BY event_seq LIMIT %s",
            (run_id, after, limit),
        ).fetchall()
        return [
            HistoryEvent(
                int(str(r["event_seq"])),
                str(r["kind"]),
                str(r["step"]),
                cast(JSON, r["data"]),
                tuple(cast(list[str], r["command_ids"])),
                int(str(r["schema_version"])),
            )
            for r in rows
        ]

    def _append(
        self, c: Connection[Row], run_id: str, kind: str, step: str = "", data: JSON | None = None
    ) -> None:
        RunTransaction(self, c, run_id).append(kind, step, data)

    def _state(
        self, c: Connection[Row], row: Row, definition: Definition | None = None
    ) -> WorkflowState:
        """Verify a coherent run projection/history snapshot before using it."""
        stored = Definition.from_dict(cast(JSON, row["definition"]))
        if stored.digest != row["definition_digest"]:
            raise DivergenceError("run definition differs from its pinned digest")
        state = replay(definition or stored, self._events(c, str(row["workflow_id"])))
        if state.seq != row["event_seq"] or state.status != row["terminal_status"]:
            raise DivergenceError("run projection disagrees with its committed history")
        return state

    def _ingress(self, c: Connection[Row], kind: str, key: str, request: object) -> str | None:
        if not key or len(key) > 200:
            raise ValueError("idempotency key must contain 1–200 characters")
        digest = hashlib.sha256(canonical(request).encode()).hexdigest()
        c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"{kind}:{key}",))
        row = c.execute(
            "SELECT * FROM ingress_requests WHERE kind=%s AND idempotency_key=%s", (kind, key)
        ).fetchone()
        if row:
            if row["canonical_request_hash"] != digest:
                raise ConflictError("Idempotency key reused with different canonical payload")
            return str(row["workflow_id"])
        return None

    def submit(
        self,
        definition: Definition,
        payload: JSON,
        idempotency_key: str,
        *,
        crash_hook: Callable[[str], None] | None = None,
    ) -> str:
        request = {"definition": definition.to_dict(), "payload": payload}
        if len(canonical(request).encode()) > 1_048_576:
            raise ValueError("Submission exceeds 1 MiB")
        with self.transaction() as c:
            existing = self._ingress(c, "submit", idempotency_key, request)
            if existing:
                return existing
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"anchor:admission:{self.schema}",),
            )
            active = c.execute(
                "SELECT count(*) AS count FROM workflow_runs WHERE terminal_status IN ('running','compensating')"
            ).fetchone()
            if active and int(str(active["count"])) >= self.max_active_runs:
                raise AdmissionError("Active workflow admission capacity exhausted")
            run_id = str(uuid.uuid4())
            digest = hashlib.sha256(canonical(request).encode()).hexdigest()
            c.execute(
                "INSERT INTO workflow_runs(workflow_id,definition,definition_version,definition_digest,payload) VALUES(%s,%s,%s,%s,%s)",
                (
                    run_id,
                    Jsonb(definition.to_dict()),
                    definition.version,
                    definition.digest,
                    Jsonb(payload),
                ),
            )
            c.execute(
                "INSERT INTO ingress_requests VALUES(%s,%s,%s,%s)",
                ("submit", idempotency_key, digest, run_id),
            )
            self._append(c, run_id, "started", data={"digest": definition.digest})
            if crash_hook:
                crash_hook("before_commit")
        if crash_hook:
            crash_hook("after_commit")
        return run_id

    def status(self, run_id: str) -> JSON:
        with self.transaction() as c:
            c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = self._run(c, run_id)
            state = self._state(c, row)
            return {
                "workflow_id": run_id,
                "status": state.status,
                "event_seq": state.seq,
                "done": sorted(state.done),
                "compensation": state.compensation,
                "definition_digest": row["definition_digest"],
            }

    def history(
        self, run_id: str, *, after: int = 0, limit: int | None = None
    ) -> list[HistoryEvent]:
        """Read ordered events; optional SQL pagination bounds fetched rows.

        The default returns the complete history for replay/export callers.
        HTTP callers must supply a bounded limit.
        """
        if type(after) is not int or after < 0:
            raise ValueError("after must be a non-negative integer")
        if limit is not None and (type(limit) is not int or not 1 <= limit <= 1000):
            raise ValueError("limit must be an integer in 1..1000")
        with self.transaction() as c:
            self._run(c, run_id)
            return self._events(c, run_id, after=after, limit=limit)

    def replay(self, run_id: str, definition: Definition | None = None) -> WorkflowState:
        with self.transaction() as c:
            c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = self._run(c, run_id)
            return self._state(c, row, definition)

    def signal(self, run_id: str, name: str, payload: JSON, idempotency_key: str) -> str:
        if not isinstance(name, str) or not 1 <= len(name) <= 100:
            raise ValueError("Signal name must contain 1..100 characters")
        request: JSON = {"name": name, "payload": payload}
        if len(canonical(request).encode()) > 1_048_576:
            raise ValueError("Signal exceeds 1 MiB")
        with self.transaction() as c:
            kind = f"signal:{run_id}"
            existing = self._ingress(c, kind, idempotency_key, request)
            if existing:
                return existing
            row = self._run(c, run_id, lock=True)
            if row["terminal_status"] != "running":
                raise ConflictError("Signals require a running workflow")
            old = c.execute(
                "SELECT payload FROM signals WHERE workflow_id=%s AND name=%s", (run_id, name)
            ).fetchone()
            if old and old["payload"] != payload:
                raise ConflictError("Signal name already delivered with different payload")
            c.execute(
                "INSERT INTO signals VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                (run_id, name, Jsonb(payload)),
            )
            c.execute(
                "INSERT INTO ingress_requests VALUES(%s,%s,%s,%s)",
                (
                    kind,
                    idempotency_key,
                    hashlib.sha256(canonical(request).encode()).hexdigest(),
                    run_id,
                ),
            )
            transition = RunTransaction(self, c, run_id)
            transition.append("signal", data=request)
            state = transition.state
            definition = state.definition
            for step in definition.steps:
                if (
                    step.kind == "signal"
                    and step.signal == name
                    and step.name in state.scheduled
                    and step.name not in state.done
                ):
                    transition.append("step_completed", step.name, {"source": "signal"})
        return run_id

    def cancel(self, run_id: str) -> JSON:
        with self.transaction() as c:
            row = self._run(c, run_id, lock=True)
            if row["terminal_status"] == "running":
                self._append(c, run_id, "cancelled")
        return self.status(run_id)

    def claim(self, lease_seconds: float = 5) -> Task | None:
        validate_lease_seconds(lease_seconds)
        with self.transaction() as c:
            row = c.execute("""SELECT r.* FROM workflow_runs r WHERE r.terminal_status IN ('running','compensating') AND EXISTS (
                SELECT 1 FROM activity_tasks t WHERE t.workflow_id=r.workflow_id AND
                ((t.status='pending' AND t.available_at<=clock_timestamp()) OR
                 (t.status='running' AND t.lease_expiry<=clock_timestamp())))
                ORDER BY r.created_at FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
            if row is None:
                return None
            run_id = str(row["workflow_id"])
            transition = RunTransaction(self, c, run_id)
            transition.sync_compensations()
            task = c.execute(
                """SELECT * FROM activity_tasks WHERE workflow_id=%s AND
                ((status='pending' AND available_at<=clock_timestamp()) OR
                 (status='running' AND lease_expiry<=clock_timestamp()))
                 ORDER BY available_at,command_id FOR UPDATE SKIP LOCKED LIMIT 1""",
                (run_id,),
            ).fetchone()
            if task is None:
                return None
            number, epoch = int(str(task["attempt_number"])) + 1, int(str(task["lease_epoch"])) + 1
            if task["status"] == "running":
                c.execute(
                    "UPDATE activity_attempts SET status='expired',finished_at=clock_timestamp() WHERE workflow_id=%s AND command_id=%s AND lease_epoch=%s",
                    (run_id, task["command_id"], task["lease_epoch"]),
                )
            if number > int(str(task["max_attempts"])):
                c.execute(
                    "UPDATE activity_tasks SET status='failed' WHERE workflow_id=%s AND command_id=%s",
                    (run_id, task["command_id"]),
                )
                transition.append(
                    "compensation_failed" if task["compensation"] else "step_failed",
                    str(task["step"]),
                    {"error": "lease attempts exhausted"},
                )
                return None
            c.execute(
                "UPDATE activity_tasks SET status='running',attempt_number=%s,lease_epoch=%s,lease_expiry=clock_timestamp()+%s*interval '1 second' WHERE workflow_id=%s AND command_id=%s",
                (number, epoch, lease_seconds, run_id, task["command_id"]),
            )
            c.execute(
                "INSERT INTO activity_attempts(workflow_id,command_id,attempt_number,lease_epoch,status,ready_delay) VALUES(%s,%s,%s,%s,'running',GREATEST(0,extract(epoch FROM (clock_timestamp()-%s::timestamptz))))",
                (run_id, task["command_id"], number, epoch, task["available_at"]),
            )
            transition.append(
                "activity_claimed",
                str(task["step"]),
                {"epoch": epoch, "attempt": number, "command_id": task["command_id"]},
            )
            return Task(
                run_id,
                str(task["command_id"]),
                str(task["step"]),
                str(task["activity"]),
                number,
                epoch,
                bool(task["compensation"]),
                cast(JSON, row["payload"]),
            )

    def _active(self, c: Connection[Row], task: Task) -> Row:
        self._run(c, task.workflow_id, lock=True)
        row = c.execute(
            "SELECT *,lease_expiry>clock_timestamp() AS lease_valid FROM activity_tasks WHERE workflow_id=%s AND command_id=%s FOR UPDATE",
            (task.workflow_id, task.command_id),
        ).fetchone()
        if (
            row is None
            or row["status"] != "running"
            or row["lease_epoch"] != task.lease_epoch
            or not row["lease_valid"]
            or row["attempt_number"] != task.attempt_number
            or row["step"] != task.step
            or row["activity"] != task.activity
            or row["compensation"] != task.compensation
        ):
            raise StaleLeaseError("Lease expired, superseded, or cancelled")
        return row

    def heartbeat(self, task: Task, lease_seconds: float = 5) -> None:
        validate_lease_seconds(lease_seconds)
        with self.transaction() as c:
            self._active(c, task)
            c.execute(
                "UPDATE activity_tasks SET lease_expiry=clock_timestamp()+%s*interval '1 second' WHERE workflow_id=%s AND command_id=%s",
                (lease_seconds, task.workflow_id, task.command_id),
            )

    def finish(self, task: Task, result: JSON | None = None, error: str | None = None) -> None:
        validate_activity_result(result)
        with self.transaction() as c:
            row = self._active(c, task)
            failed = error is not None
            retry = failed and task.attempt_number < int(str(row["max_attempts"]))
            status = "pending" if retry else ("failed" if failed else "completed")
            # Bound the actual exponential delay as well as its configured base.
            # Valid 32-attempt definitions must never overflow PostgreSQL timestamps.
            delay = retry_delay(float(str(row["retry_delay"])), task.attempt_number)
            c.execute(
                "UPDATE activity_tasks SET status=%s,available_at=clock_timestamp()+%s*interval '1 second',lease_expiry=NULL WHERE workflow_id=%s AND command_id=%s",
                (status, delay if retry else 0, task.workflow_id, task.command_id),
            )
            c.execute(
                "UPDATE activity_attempts SET status=%s,finished_at=clock_timestamp() WHERE workflow_id=%s AND command_id=%s AND lease_epoch=%s",
                (
                    "failed" if failed else "completed",
                    task.workflow_id,
                    task.command_id,
                    task.lease_epoch,
                ),
            )
            kind = "retry_scheduled" if retry else ("step_failed" if failed else "step_completed")
            if task.compensation:
                kind = (
                    "compensation_retry"
                    if retry
                    else ("compensation_failed" if failed else "compensation_completed")
                )
            self._append(
                c,
                task.workflow_id,
                kind,
                task.step,
                {
                    "result": result or {},
                    "error": error,
                    "retry_delay": delay if retry else 0,
                    "attempt": task.attempt_number,
                },
            )

    def retry_compensation(self, run_id: str) -> None:
        with self.transaction() as c:
            self._run(c, run_id, lock=True)
            rows = c.execute(
                "UPDATE activity_tasks SET status='pending',max_attempts=attempt_number+3,available_at=clock_timestamp() WHERE workflow_id=%s AND compensation AND status='failed' RETURNING step",
                (run_id,),
            ).fetchall()
            transition = RunTransaction(self, c, run_id)
            for row in rows:
                transition.append("compensation_retry", str(row["step"]))

    def tick(self, *, advance_seconds: float = 0, limit: int = 1000) -> int:
        """Test-only clock injection applies to timer eligibility; DB owns all lease time."""
        if (
            type(advance_seconds) not in (int, float)
            or not 0 <= advance_seconds <= 31536000
            or not math.isfinite(advance_seconds)
        ):
            raise ValueError("advance_seconds must be finite seconds in 0..31536000")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer in 1..1000")
        count = 0
        for _ in range(limit):
            with self.transaction() as c:
                row = c.execute(
                    """SELECT r.workflow_id FROM workflow_runs r WHERE r.terminal_status='running' AND EXISTS (
                    SELECT 1 FROM timers t WHERE t.workflow_id=r.workflow_id AND NOT t.fired
                    AND t.due_at<=clock_timestamp()+%s*interval '1 second')
                    ORDER BY r.created_at FOR UPDATE SKIP LOCKED LIMIT 1""",
                    (advance_seconds,),
                ).fetchone()
                if row is None:
                    break
                run_id = str(row["workflow_id"])
                timers = c.execute(
                    "UPDATE timers SET fired=true WHERE workflow_id=%s AND NOT fired AND due_at<=clock_timestamp()+%s*interval '1 second' RETURNING step",
                    (run_id, advance_seconds),
                ).fetchall()
                transition = RunTransaction(self, c, run_id)
                for timer in timers:
                    transition.append("step_completed", str(timer["step"]), {"source": "timer"})
                    count += 1
        return count

    def publish(self, business_key: str, payload: JSON) -> JSON:
        with self.transaction() as c:
            c.execute(
                "INSERT INTO provider_effects(business_key,payload,publications) VALUES(%s,%s,1) ON CONFLICT DO NOTHING",
                (business_key, Jsonb(payload)),
            )
            row = c.execute(
                "SELECT * FROM provider_effects WHERE business_key=%s FOR UPDATE", (business_key,)
            ).fetchone()
            assert row is not None
            if row["fenced"]:
                raise ProviderFencedError("Provider has a terminal cleanup fence")
            if row["payload"] != payload:
                raise ConflictError("Provider business key reused with different payload")
            return {"business_key": business_key, "publications": row["publications"]}

    def cleanup(self, business_key: str, *, fail: bool = False) -> JSON:
        with self.transaction() as c:
            c.execute(
                "INSERT INTO provider_effects(business_key,payload,fenced,cleanup_attempts) VALUES(%s,%s,true,1) ON CONFLICT(business_key) DO UPDATE SET fenced=true,cleanup_attempts=provider_effects.cleanup_attempts+1",
                (business_key, Jsonb({})),
            )
        if fail:
            raise RuntimeError("Injected cleanup failure after provider fence")
        return {"cleaned": True}

    def metrics(self) -> JSON:
        with self.transaction() as c:
            tasks = c.execute(
                "SELECT status,count(*) AS count FROM activity_tasks GROUP BY status"
            ).fetchall()
            runs = c.execute(
                "SELECT terminal_status,count(*) AS count FROM workflow_runs GROUP BY terminal_status"
            ).fetchall()
            row = c.execute(
                "SELECT count(*) FILTER(WHERE attempt_number>1) AS retries, coalesce(percentile_cont(0.95) WITHIN GROUP(ORDER BY extract(epoch FROM (started_at-r.created_at))),0) AS created_delay_p95, coalesce(percentile_cont(0.95) WITHIN GROUP(ORDER BY ready_delay),0) AS ready_delay_p95, count(*) FILTER(WHERE a.status='expired') AS expired_leases FROM activity_attempts a JOIN workflow_runs r USING(workflow_id)"
            ).fetchone()
            size = c.execute(
                "SELECT coalesce(sum(pg_total_relation_size(c.oid)),0)::bigint AS bytes FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname=current_schema()"
            ).fetchone()
            return {
                "tasks": {str(r["status"]): r["count"] for r in tasks},
                "runs": {str(r["terminal_status"]): r["count"] for r in runs},
                "retries": row["retries"] if row else 0,
                "created_to_start_p95_seconds": float(str(row["created_delay_p95"])) if row else 0,
                "ready_to_start_p95_seconds": float(str(row["ready_delay_p95"])) if row else 0,
                "expired_leases": row["expired_leases"] if row else 0,
                "database_size_bytes": int(str(size["bytes"])) if size else 0,
            }

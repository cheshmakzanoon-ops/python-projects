"""One run-row lock, one replay, and atomic history/projection writes per transaction."""

from typing import TYPE_CHECKING

from psycopg import Connection
from psycopg.types.json import Jsonb

from pp_anchor.definitions.model import JSON
from pp_anchor.history.events import HistoryEvent
from pp_anchor.replay.reducer import decide

if TYPE_CHECKING:
    from pp_anchor.persistence.engine import Engine, Row


class RunTransaction:
    """Transaction-local reducer state; never retain beyond the caller's commit.

    The owning transaction holds the run row before reading its history. A failed
    projection or append rolls back every event and task change in this object.
    """

    def __init__(self, engine: "Engine", connection: Connection["Row"], run_id: str) -> None:
        self.engine, self.connection, self.run_id = engine, connection, run_id
        row = engine._run(connection, run_id, lock=True)
        self.state = engine._state(connection, row)
        self.definition = self.state.definition

    def sync_compensations(self) -> None:
        if not self.state.compensation:
            return
        self.connection.execute(
            "UPDATE activity_tasks SET status=CASE WHEN step=ANY(%s) THEN 'pending' ELSE 'blocked' END WHERE workflow_id=%s AND compensation AND status IN ('pending','blocked')",
            (list(self.state.rollback_ready()), self.run_id),
        )

    def append(self, kind: str, step: str = "", data: JSON | None = None) -> None:
        c, run_id, state = self.connection, self.run_id, self.state
        by_name = state.graph.steps
        # Preserve depth-first history order without a Python frame per internal step.
        # The run lock protects this state and all projections until the transaction commits.
        pending = [(kind, step, data)]
        while pending:
            kind, step, data = pending.pop()
            event = HistoryEvent(
                state.seq + 1, kind, step, data or {}, schema_version=state.history_schema_version
            )
            commands = decide(state, event)
            c.execute(
                "INSERT INTO history_events(workflow_id,event_seq,kind,step,data,command_ids,schema_version) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    run_id,
                    event.seq,
                    kind,
                    step,
                    Jsonb(event.data),
                    Jsonb([x.command_id for x in commands]),
                    event.schema_version,
                ),
            )
            c.execute(
                "UPDATE workflow_runs SET event_seq=%s,terminal_status=%s WHERE workflow_id=%s",
                (event.seq, state.status, run_id),
            )
            if kind in ("cancelled", "step_failed"):
                c.execute(
                    "UPDATE activity_tasks SET status='cancelled' WHERE workflow_id=%s AND NOT compensation AND status IN ('pending','running')",
                    (run_id,),
                )
                c.execute(
                    "UPDATE activity_attempts a SET status='cancelled',finished_at=clock_timestamp() FROM activity_tasks t WHERE a.workflow_id=t.workflow_id AND a.command_id=t.command_id AND a.lease_epoch=t.lease_epoch AND t.workflow_id=%s AND NOT t.compensation AND t.status='cancelled' AND a.status='running'",
                    (run_id,),
                )
                # Fence first, even when the actual cleanup later fails. Late effects cannot resurrect.
                c.execute(
                    "INSERT INTO provider_effects(business_key,payload,fenced) VALUES(%s,%s,true) ON CONFLICT(business_key) DO UPDATE SET fenced=true",
                    (run_id, Jsonb({})),
                )
            immediate: list[str] = []
            for command in commands:
                if command.kind in ("Complete", "Fail"):
                    continue
                item = by_name[command.step]
                if command.kind in ("ScheduleActivity", "Compensate"):
                    c.execute(
                        "INSERT INTO activity_tasks(workflow_id,command_id,step,activity,compensation,max_attempts,retry_delay) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (
                            run_id,
                            command.command_id,
                            item.name,
                            item.compensate if command.kind == "Compensate" else item.activity,
                            command.kind == "Compensate",
                            item.max_attempts,
                            item.retry_delay,
                        ),
                    )
                elif command.kind == "StartTimer":
                    c.execute(
                        "INSERT INTO timers(workflow_id,command_id,step,due_at) VALUES(%s,%s,%s,clock_timestamp()+%s*interval '1 second') ON CONFLICT DO NOTHING",
                        (run_id, command.command_id, item.name, item.delay),
                    )
                elif command.kind == "AwaitSignal":
                    if c.execute(
                        "SELECT 1 FROM signals WHERE workflow_id=%s AND name=%s",
                        (run_id, item.signal),
                    ).fetchone():
                        immediate.append(item.name)
                elif command.kind == "Join":
                    immediate.append(item.name)
            pending.extend(
                ("step_completed", name, {"source": "internal"}) for name in reversed(immediate)
            )

        self.sync_compensations()

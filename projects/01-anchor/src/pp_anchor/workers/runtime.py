"""Bounded asyncio workers; external execution is explicitly at least once."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from pp_anchor.definitions.model import JSON
from pp_anchor.persistence.engine import Engine, StaleLeaseError, Task

Activity = Callable[["ActivityContext"], Awaitable[JSON]]


@dataclass(frozen=True)
class ActivityContext:
    engine: Engine
    task: Task

    @property
    def business_key(self) -> str:
        return self.task.workflow_id


async def identity(context: ActivityContext) -> JSON:
    return {"step": context.task.step, "input": context.task.payload}


async def publish(context: ActivityContext) -> JSON:
    return await asyncio.to_thread(
        context.engine.publish, context.business_key, context.task.payload
    )


async def cleanup(context: ActivityContext) -> JSON:
    return await asyncio.to_thread(context.engine.cleanup, context.business_key)


async def fail(context: ActivityContext) -> JSON:
    raise RuntimeError("Injected later-stage failure")


@dataclass
class ActivityRegistry:
    handlers: dict[str, Activity] = field(
        default_factory=lambda: {
            "identity": identity,
            "publish": publish,
            "cleanup": cleanup,
            "fail": fail,
        }
    )

    def register(self, name: str, handler: Activity) -> None:
        if name in self.handlers:
            raise ValueError(f"Activity {name} already registered")
        self.handlers[name] = handler


class Worker:
    def __init__(
        self,
        engine: Engine,
        registry: ActivityRegistry | None = None,
        *,
        concurrency: int = 4,
        lease_seconds: float = 5,
        heartbeat: bool = True,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be positive")
        self.engine = engine
        self.registry = registry or ActivityRegistry()
        self.concurrency, self.lease_seconds, self.heartbeat_enabled = (
            concurrency,
            lease_seconds,
            heartbeat,
        )

    async def _heartbeat(self, task: Task) -> None:
        while True:
            await asyncio.sleep(self.lease_seconds / 3)
            await asyncio.to_thread(self.engine.heartbeat, task, self.lease_seconds)

    async def run_once(self) -> bool:
        task = await asyncio.to_thread(self.engine.claim, self.lease_seconds)
        if task is None:
            return False

        async def execute() -> None:
            try:
                handler = self.registry.handlers[task.activity]
                result = await handler(ActivityContext(self.engine, task))
            except Exception as exc:
                await asyncio.to_thread(
                    self.engine.finish, task, None, f"{type(exc).__name__}: {exc}"
                )
            else:
                await asyncio.to_thread(self.engine.finish, task, result)

        try:
            if self.heartbeat_enabled:
                async with asyncio.TaskGroup() as group:
                    heartbeat_task = group.create_task(self._heartbeat(task))
                    try:
                        await execute()
                    finally:
                        heartbeat_task.cancel()
            else:
                await execute()
        except StaleLeaseError:
            pass
        except ExceptionGroup as errors:
            # Only stale fencing is recoverable. Preserve all other worker failures.
            remainder = errors.subgroup(
                lambda error: not isinstance(error, (StaleLeaseError, ExceptionGroup))
            )
            if remainder:
                raise remainder
        return True

    async def run(self, stop: asyncio.Event, *, idle_sleep: float = 0.01) -> None:
        async def slot() -> None:
            while not stop.is_set():
                if not await self.run_once():
                    await asyncio.sleep(idle_sleep)

        async with asyncio.TaskGroup() as group:
            for _ in range(self.concurrency):
                group.create_task(slot())


async def drain(engine: Engine, *, concurrency: int = 4, timeout: float = 30) -> None:
    """Run ready work until idle. Future timers and missing signals remain pending."""
    worker = Worker(engine, concurrency=concurrency)
    async with asyncio.timeout(timeout):
        while True:
            await asyncio.to_thread(engine.tick)
            done = await asyncio.gather(*(worker.run_once() for _ in range(concurrency)))
            if not any(done):
                with engine.transaction() as c:
                    pending = c.execute(
                        "SELECT count(*) AS count FROM activity_tasks WHERE status IN ('pending','running')"
                    ).fetchone()
                if pending and int(str(pending["count"])) > 0:
                    await asyncio.sleep(0.02)
                    continue
                return

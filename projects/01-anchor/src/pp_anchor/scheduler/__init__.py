"""Polling durable timers with bounded state, independent of worker execution."""

import asyncio

from pp_anchor.persistence.engine import Engine


async def scheduler(engine: Engine, stop: asyncio.Event, *, poll_seconds: float = 0.02) -> None:
    while not stop.is_set():
        await asyncio.to_thread(engine.tick)
        await asyncio.sleep(poll_seconds)

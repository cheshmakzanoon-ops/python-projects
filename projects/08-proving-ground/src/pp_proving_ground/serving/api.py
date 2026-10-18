"""Loopback-only demo API; no authentication and no model-upload endpoint."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from pp_proving_ground.serving.service import ServingProcess, Unavailable


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    records: Annotated[list[dict[str, float | None]], Field(min_length=1, max_length=1000)]


def create_app(process: ServingProcess, auto_refresh: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async def watch_generations() -> None:
            last_attempted = -1
            while True:
                requested = process.registry.current().generation
                if requested != last_attempted:
                    last_attempted = requested
                    await asyncio.to_thread(process.refresh)
                await asyncio.sleep(0.1)

        watcher = asyncio.create_task(watch_generations()) if auto_refresh else None
        try:
            yield
        finally:
            if watcher is not None:
                watcher.cancel()
                with suppress(asyncio.CancelledError):
                    await watcher

    app = FastAPI(
        lifespan=lifespan,
        title="Proving Ground",
        description="Local synthetic equipment model lifecycle",
    )

    @app.middleware("http")
    async def bounded_body(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > 2 * 1024 * 1024:
                return JSONResponse({"detail": "request body exceeds 2 MiB"}, status_code=413)
        request._body = bytes(payload)
        return await call_next(request)

    @app.post("/refresh")
    async def refresh() -> dict[str, Any]:
        await asyncio.to_thread(process.refresh)
        return process.readiness()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/ready")
    def ready() -> JSONResponse:
        report = process.readiness()
        return JSONResponse(report, status_code=200 if report["ready"] else 503)

    @app.get("/models")
    def versions(
        limit: Annotated[int, Field(ge=1, le=100)] = 20, after: Annotated[int, Field(ge=0)] = 0
    ) -> list[dict[str, Any]]:
        return [asdict(v) for v in process.registry.versions() if v.version > after][:limit]

    @app.get("/deployment")
    def deployment() -> dict[str, Any]:
        return {"requested": asdict(process.registry.current()), "serving": process.readiness()}

    @app.post("/predict")
    def predict(request: PredictRequest) -> dict[str, Any]:
        try:
            return asdict(process.predict_records(request.records))
        except Unavailable as error:
            raise HTTPException(503, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    return app

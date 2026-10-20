"""Loopback control plane. No authentication; never expose beyond trusted local users."""

from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from pp_anchor.api.body_limit import BodyLimitMiddleware
from pp_anchor.definitions.model import Definition
from pp_anchor.persistence.engine import AdmissionError, ConflictError, Engine


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition: dict[str, object]
    payload: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=200)


class SignalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    payload: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=200)


def create_app(engine: Engine) -> FastAPI:
    app = FastAPI(title="Anchor local control API", version="1")

    app.add_middleware(BodyLimitMiddleware)

    @app.exception_handler(AdmissionError)
    async def admission(request: Request, exc: AdmissionError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=429)

    @app.exception_handler(ConflictError)
    async def conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing(request: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse({"detail": "Run not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.post("/runs", status_code=201)
    def submit(request: SubmitRequest) -> dict[str, str]:
        run_id = engine.submit(
            Definition.from_dict(request.definition), request.payload, request.idempotency_key
        )
        return {"workflow_id": run_id}

    @app.post("/runs/{run_id}/signals")
    def signal(run_id: str, request: SignalRequest) -> dict[str, str]:
        return {
            "workflow_id": engine.signal(
                run_id, request.name, request.payload, request.idempotency_key
            )
        }

    @app.post("/runs/{run_id}/cancel")
    def cancel(run_id: str) -> dict[str, object]:
        return engine.cancel(run_id)

    @app.get("/runs/{run_id}")
    def status(run_id: str) -> dict[str, object]:
        return engine.status(run_id)

    @app.get("/runs/{run_id}/history")
    def history(run_id: str, after: int = 0, limit: int = 100) -> dict[str, object]:
        if after < 0 or not 1 <= limit <= 1000:
            raise HTTPException(422, "after >= 0 and 1 <= limit <= 1000 required")
        page = [asdict(e) for e in engine.history(run_id, after=after, limit=limit)]
        return {"events": page, "next_after": page[-1]["seq"] if page else after}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        with engine.transaction() as c:
            c.execute("SELECT 1")
        return {"status": "ready"}

    return app

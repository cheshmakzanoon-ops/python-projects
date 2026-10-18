"""Authenticated local HTTP adapter and a focused browser search view."""

import dataclasses
import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from pp_atlas import CorruptSegment, Document, Engine, Principal


@dataclass(frozen=True)
class Identity:
    principal: Principal
    admin: bool = False


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=256)
    title: str = Field(max_length=1024)
    text: str = Field(max_length=2_000_000)
    acl: list[str] = Field(default_factory=lambda: ["*"], max_length=128)
    metadata: dict[str, str] = Field(default_factory=dict, max_length=32)


class ACLInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subjects: list[str] = Field(max_length=128)


def create_app(engine: Engine, tokens: dict[str, Identity]) -> FastAPI:
    """Bind opaque bearer credentials to server-side identities; no caller groups.

    Put the local service behind TLS if crossing a trusted loopback boundary.
    Token values must come from deployment configuration, never URL parameters.
    """
    if not tokens or any(len(token) < 16 for token in tokens):
        raise ValueError("configure at least one bearer token of >=16 characters")
    app = FastAPI(title="Atlas", version="0.1.0")
    bearer = HTTPBearer(auto_error=False)

    def identity(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> Identity:
        if credentials:
            for token, value in tokens.items():
                if secrets.compare_digest(token, credentials.credentials):
                    return value
        raise HTTPException(
            401, "valid bearer credential required", headers={"WWW-Authenticate": "Bearer"}
        )

    def admin(who: Annotated[Identity, Depends(identity)]) -> Identity:
        if not who.admin:
            raise HTTPException(403, "tenant administrator required")
        return who

    @app.middleware("http")
    async def bound_body(request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Starlette caches the bounded body for the downstream Pydantic adapter.
        body = bytearray()
        async for block in request.stream():
            body.extend(block)
            if len(body) > 2_100_000:
                return JSONResponse({"detail": "request body exceeds limit"}, status_code=413)
        request._body = bytes(body)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid(_: Request, error: ValueError) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(CorruptSegment)
    async def corrupt(_: Request, error: CorruptSegment) -> JSONResponse:
        return JSONResponse(
            {"detail": "index integrity failure; administrator intervention required"},
            status_code=503,
        )

    @app.exception_handler(KeyError)
    async def missing(_: Request, error: KeyError) -> JSONResponse:
        return JSONResponse({"detail": "document unavailable"}, status_code=404)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/ready")
    def ready(who: Annotated[Identity, Depends(identity)]) -> dict[str, object]:
        return engine.inspect(who.principal.tenant)

    @app.get("/search")
    def search(
        who: Annotated[Identity, Depends(identity)], q: str = "", limit: int = 10, offset: int = 0
    ) -> dict[str, object]:
        return dataclasses.asdict(engine.search(who.principal, q, limit=limit, offset=offset))

    @app.get("/documents/{document_id}")
    def fetch(document_id: str, who: Annotated[Identity, Depends(identity)]) -> dict[str, object]:
        document = engine.fetch(who.principal, document_id)
        # Readers receive content/metadata; ACL subjects are an admin concern.
        return {
            "id": document.id,
            "title": document.title,
            "text": document.text,
            "metadata": document.metadata,
        }

    @app.get("/export")
    def export(
        who: Annotated[Identity, Depends(identity)], limit: int = 100, offset: int = 0
    ) -> dict[str, object]:
        if not 1 <= limit <= 100 or not 0 <= offset <= 10_000:
            raise ValueError("invalid limit/offset")
        documents = engine.export(who.principal)
        return {
            "total": len(documents),
            "documents": [
                {"id": d.id, "title": d.title, "text": d.text, "metadata": d.metadata}
                for d in documents[offset : offset + limit]
            ],
        }

    @app.post("/documents", status_code=201)
    def upsert(document: DocumentInput, who: Annotated[Identity, Depends(admin)]) -> dict[str, str]:
        revision = engine.upsert(
            who.principal.tenant,
            Document(
                document.id,
                document.title,
                document.text,
                frozenset(document.acl),
                document.metadata,
            ),
        )
        return {"id": document.id, "revision": revision}

    @app.delete("/documents/{document_id}")
    def delete(document_id: str, who: Annotated[Identity, Depends(admin)]) -> dict[str, bool]:
        return {"deleted": engine.delete(who.principal.tenant, document_id)}

    @app.put("/documents/{document_id}/acl")
    def acl(
        document_id: str, value: ACLInput, who: Annotated[Identity, Depends(admin)]
    ) -> dict[str, bool]:
        engine.set_acl(who.principal.tenant, document_id, value.subjects)
        return {"updated": True}

    @app.put("/groups/{subject}")
    def groups(
        subject: str, value: ACLInput, who: Annotated[Identity, Depends(admin)]
    ) -> dict[str, bool]:
        engine.set_groups(who.principal.tenant, subject, value.subjects)
        return {"updated": True}

    @app.post("/merge")
    def merge(who: Annotated[Identity, Depends(admin)]) -> dict[str, int]:
        return {"generation": engine.merge(who.principal.tenant)}

    @app.get("/", response_class=HTMLResponse)
    def view() -> str:
        return """<!doctype html><html lang=en><meta charset=utf-8><title>Atlas search</title>
<style>body{font:18px system-ui;max-width:850px;margin:3rem auto;padding:1rem}input{padding:.7rem}article{border-top:1px solid #ccc;padding:1rem}mark{background:#ffe48b}</style>
<h1>Atlas</h1><p>Search your authorized technical knowledge base.</p>
<form id=f><input id=token type=password placeholder='Access token' required autocomplete=off>
<input id=q placeholder='Query or &quot;exact phrase&quot;' size=35><button>Search</button></form>
<p id=status role=status></p><main id=results></main><script>
const form=document.getElementById('f'), results=document.getElementById('results');
const statusLabel=document.getElementById('status'), token=document.getElementById('token');
const query=document.getElementById('q');
form.onsubmit=async e=>{e.preventDefault();results.replaceChildren();
try {
const response=await fetch('/search?q='+encodeURIComponent(query.value),{headers:{Authorization:'Bearer '+token.value}});
const data=await response.json();statusLabel.textContent=response.ok?data.total+' results':data.detail;
for(const hit of data.hits||[]){const a=document.createElement('article'),h=document.createElement('h2'),p=document.createElement('p');h.textContent=hit.title+' · '+hit.score.toFixed(3);p.innerHTML=hit.snippet;a.append(h,p);results.append(a);}
}catch(error){statusLabel.textContent='Search unavailable. Check the local service.';}};
</script></html>"""

    return app

# Local HTTP API

Start `uv run --locked anchor serve --port 8101` with `ANCHOR_DATABASE_URL`
set to a dedicated PostgreSQL database. The service binds to `127.0.0.1`.
Interactive request schemas are available at `/docs`; the OpenAPI document is at
`/openapi.json`. This API has no authentication or authorization. Any client able
to connect can submit, inspect, signal or cancel workflows. Keep it on loopback
and do not forward its port to untrusted users.

## Operations

| Method and path | Behavior |
| --- | --- |
| `POST /runs` | Submit a definition and payload; return `201` with `workflow_id`. |
| `POST /runs/{workflow_id}/signals` | Persist a named signal for a running workflow. |
| `POST /runs/{workflow_id}/cancel` | Request cancellation; return current state. |
| `GET /runs/{workflow_id}` | Return reducer-derived state and definition digest. |
| `GET /runs/{workflow_id}/history?after=0&limit=100` | Return an ordered SQL-bounded event page and `next_after`. |
| `GET /health` | Report process liveness without checking the database. |
| `GET /ready` | Execute a database query; readiness does not guarantee free worker capacity. |

Submission body:

```json
{
  "definition": {
    "name": "approval",
    "version": 1,
    "steps": [{"name": "wait", "kind": "signal", "signal": "approve"}]
  },
  "payload": {"report": "synthetic-export"},
  "idempotency_key": "export-2026-001"
}
```

Signal body:

```json
{"name": "approve", "payload": {"approved": true}, "idempotency_key": "approval-001"}
```

Use a new business key for a new logical request. Repeating a submission or signal
with the same key and canonical payload returns the original workflow identity.
Reusing a key with different content returns `409`. Signal keys are scoped to the
workflow; submission keys are scoped to the engine schema. Unknown top-level
request fields are rejected to expose misspelled fields rather than discard input.
Submission and signal bodies must be UTF-8 JSON with unique object members and
finite numbers. Null characters, unpaired Unicode surrogates, and structures beyond
64 container levels are rejected before routing or persistence. These inputs return
`422`, including requests deep enough to exhaust an ordinary JSON parser's recursion.
The same text and nesting limits apply to SDK canonicalization and activity results.

For history, pass the previous response's `next_after` as the next `after`. The
cursor is an event sequence, so newly appended events do not shift older pages.
An empty page leaves `next_after` unchanged. `after` must be non-negative and
`limit` must be between 1 and 1,000. Pagination bounds fetched history rows in SQL;
state inspection still replays a complete history.

## Failure and resource boundaries

| Status | Meaning and response |
| --- | --- |
| `400` | Invalid, duplicate or inconsistent `Content-Length`; correct request framing. |
| `404` | The workflow does not exist in this engine schema. |
| `409` | Idempotency conflict, conflicting signal payload or signal sent to a terminal workflow. |
| `413` | Body exceeds 1 MiB, including chunked requests. |
| `422` | Invalid JSON encoding, values, shape, definition or pagination; inspect `detail`. |
| `429` | Active-run admission is exhausted; apply bounded client retry/backoff. |

The body limit is applied at the ASGI boundary before routing. The client must
also set connection and read timeouts: the engine does not provide a public-network
slow-client defense. Configure process and reverse-proxy limits if adapting the
transport for another trusted environment. Do not expose this API by adding only
a proxy; authenticated identity, authorization, TLS, audit policy and operational
limits need a separate deployment design.

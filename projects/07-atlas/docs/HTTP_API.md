# HTTP and browser guide

Atlas serves a local search workspace at `http://127.0.0.1:8107/`. Start it with
`uv run --locked atlas serve --root /absolute/index --port 8107` after configuring
`ATLAS_TOKEN_BINDINGS` as described in [operations](OPERATIONS.md). This is a static
bearer-identity adapter for a trusted local environment. It is not a public identity
provider or a substitute for deployment authentication, TLS and operational limits.

## Search workspace

Enter the administrator-provided token under **Connection**, then a query. Leaving
the query empty browses your authorized collection. Matching terms appear in context;
document-type counts summarize only authorized matches. Use **Next** and **Previous**
to move through ten-result pages, or **Read document** to fetch the current document.
The reader is a keyboard-accessible dialog; Escape returns to the invoking control.

Words match conjunctively. `wal recovery` requires both words; `"wal recovery"`
requires adjacent words in that order. `type:runbook`, `tag:NAME`, `source:NAME`
and `id:IDENTIFIER` are exact metadata/identity filters. Filters narrow the collection
used for ranking statistics. Repeated unquoted terms contribute once. A query can
contain at most 4,096 UTF-8 bytes, 32 tokens, eight filters and 16 tokens per phrase.

The page distinguishes loading, empty results, rejected credentials and service
failures. New searches cancel superseded requests. Changing or clearing a token
immediately discards prior results and reader content, and page exit clears the token.
Neither browser storage nor URL parameters hold credentials. The token control has
no form field name; if JavaScript is unavailable, search stays disabled instead of
submitting a password through a native form. Search assets load from the same service,
with no external font, script or analytics request.

Source snippets retain only escaped text and controlled highlights. Full documents
are displayed as text; indexed HTML or Markdown cannot execute in the reader.
Permissions are checked again when reading a hit. An earlier search result does not
grant future access after revocation.

## Request contract

Send `Authorization: Bearer TOKEN` for every authenticated request. The server binds
that credential to a tenant, subject and boolean administrator role. Request bodies
cannot override a tenant or supply their own memberships.

| Method and path | Access | Behavior |
| --- | --- | --- |
| `GET /search?q=QUERY&limit=10&offset=0` | Reader | Current authorized hits, term explanations, counts and facets. |
| `GET /documents/{id}` | Reader | Current title, text and metadata; excludes ACL subjects. |
| `GET /export?limit=100&offset=0` | Reader | Authorized total and one ID-ordered document page. |
| `GET /ready` | Reader | Validate tenant index; return only readiness status. |
| `POST /documents` | Administrator | Upsert one document and return its revision. |
| `DELETE /documents/{id}` | Administrator | Delete a current document. |
| `PUT /documents/{id}/acl` | Administrator | Replace its ACL with `{"subjects": [...]}`. |
| `PUT /groups/{subject}` | Administrator | Replace memberships with `{"subjects": [...]}`. |
| `POST /merge` | Administrator | Publish a merged generation. |
| `GET /health` | Public | Process liveness; no index or credential checks. |

Document IDs are opaque strings, including slash-containing names. URL-encode the
entire ID when constructing a document path. IDs are never interpreted as filesystem
paths. Missing and forbidden documents both return `404`.

Search/export `limit` is 1–100 and `offset` is 0–10,000. Each response pins one coherent
generation and ACL snapshot; totals and content use the same snapshot. Offset pages
can shift after a write or permission change. Export constructs only the requested
page of public document records, although the current-generation index itself remains
materialized in memory. It is not a streaming full-index export interface.

## Errors and privacy

| Status | Meaning |
| --- | --- |
| `400` | Invalid query, pagination or HTTP body framing. |
| `401` | Missing or rejected bearer credential; response includes `WWW-Authenticate`. |
| `403` | Authenticated identity lacks the tenant administrator role. |
| `404` | Document unavailable to this principal. |
| `413` | Request exceeds the 2,100,000-byte body limit, including chunked JSON. |
| `422` | Invalid request schema or an unexpected document field. |
| `503` | Segment integrity failure; administrator intervention is needed. |

Responses send `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, framing
denial and content-type sniffing protection. The search workspace enforces a
Content Security Policy that permits only its local scripts, styles and connections.
The default interactive FastAPI documentation is a separate developer interface.

Searches use GET URLs, so query text can appear in server access logs. Use appropriate
log redaction and retention if adapting the service for sensitive documents. Index
and ACL revision numbers describe tenant-level publication state; the product does
not promise to conceal every timing or revision side channel. Library and CLI callers
are trusted to select a verified `Principal`; bearer checks apply at the HTTP boundary.

## Browser verification

The current view was exercised in headless Chromium at 1,280-pixel desktop and
390-pixel mobile widths. Functional checks covered authorized pagination, encoded
document IDs, document reading/Escape, escaped source HTML, empty/error states,
connection clearing, disabled-script fallback, concurrent query cancellation and
absence of browser storage or external requests. Automated axe checks found no
WCAG 2 A/AA or WCAG 2.1 AA violations in initial, results, reader-dialog and mobile
states. These checks supplement manual keyboard review; they are not a complete
accessibility conformance audit.

The [README screenshot](images/search-desktop.png) is a real Chromium capture of
the included quality corpus with `"wal recovery" type:runbook`. It contains synthetic
documents and no credential values. [Verification records](VERIFICATION.md) distinguish
current checks from historical benchmark and relevance measurements.

The optional browser regression harness starts its own disposable synthetic index
and tests these states against real HTTP. It requires Node.js, Chromium, Playwright
and `@axe-core/playwright` as development tools; they are not runtime dependencies.
Install the Node tools outside the checkout, then run from this project directory:

```sh
npm install --prefix /tmp/atlas-browser-tools --no-save playwright @axe-core/playwright
NODE_PATH=/tmp/atlas-browser-tools/node_modules uv run --locked python tests/browser/check_browser.py
```

The harness uses `/usr/bin/chromium` when present, or Playwright's installed Chromium.
Set `ATLAS_CHROMIUM_PATH` to select another Chromium executable. It reports functional
results and axe violations as JSON, exits nonzero on failure and stops its own server.

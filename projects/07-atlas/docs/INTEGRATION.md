# Integration contract

Atlas is a standalone package. Integrations use `Engine`, `Document` and `Principal`
or the authenticated HTTP API, with explicit JSON exchange files. They must not
import sibling source directories or share another product's virtual environment.
No external service or credential is needed for the Python API or CLI.

## Code-analysis findings

The code-search integration transforms PyTrace's diagnostic JSON into Atlas documents.
Use a stable finding identity as the document ID and replace that ID when its source
content changes. Deletion must call `Engine.delete`; omitting a document from a later
batch does not delete an existing revision. Flush/merge never substitutes for deletion.

Derive `Principal` from a verified caller identity, then configure tenant-local group
membership through `set_groups`. Caller-provided tenant or group claims are not an
authentication mechanism. HTTP adapters bind opaque bearer credentials to server-side
principals and administrator roles. The `admin` field must be an actual JSON boolean.

## Snapshot and visibility semantics

Search, fetch and export pin a coherent catalog/ACL snapshot when they begin. A
request already in progress can finish under that snapshot. Every request beginning
after a revocation commits sees the changed ACL. Recheck permission when opening a
search result; an earlier search hit does not grant future document access.

Hidden documents do not affect visible scores, facets, counts or snippets. Index and
ACL revision numbers identify tenant-level publication state, so the interface does
not claim to conceal every timing or revision side channel.

`export_page(principal, limit=100, offset=0)` returns an authorized total and one
ID-ordered tuple of documents from the same snapshot. Offset pages can shift between
requests after index or permission changes. For a complete coherent offline backup,
stop writers and copy the entire index root as described in the runbook.

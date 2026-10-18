"""Index only current code evidence and enforce tenant/ACL visibility before ranking."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from pp_atlas import Document, Engine, Principal


def document(row: dict) -> Document:
    return Document(
        row["id"],
        row["title"],
        row["text"],
        acl=frozenset({"group:operators"} if row["restricted"] else {"*"}),
        metadata={"type": "diagnostic", "tag": "pytrace", "source": row["finding"]["path"]},
    )


def visible_projection(result) -> dict:
    # Generation/ACL revisions are provenance, not user-visible ranking statistics.
    return {
        "total": result.total,
        "facets": result.facets,
        "visible_documents": result.visible_documents,
        "hits": [
            {"id": hit.id, "score": hit.score, "snippet": hit.snippet, "title": hit.title}
            for hit in result.hits
        ],
    }


def run(output: Path) -> None:
    initial = json.loads((output / "documents-initial.json").read_text())
    updated = json.loads((output / "documents-updated.json").read_text())
    hidden_changed = json.loads((output / "documents-hidden-changed.json").read_text())
    obsolete = json.loads((output / "delete-ids.json").read_text())
    engine = Engine(output / "search")
    tenant = "code-evidence"
    reader, operator = Principal(tenant, "reader"), Principal(tenant, "operator")
    engine.set_groups(tenant, "operator", ["operators"])
    engine.upsert_many(tenant, [document(row) for row in initial])
    initial_shell = engine.search(reader, "PT001")
    assert initial_shell.total == 1
    private_id = next(row["id"] for row in initial if row["restricted"])
    assert engine.search(reader, "PT002").total == 0
    assert engine.search(operator, "PT002").total == 1
    try:
        engine.fetch(reader, private_id)
    except (PermissionError, KeyError):
        pass
    else:
        raise AssertionError("direct document route leaked restricted evidence")
    assert private_id not in {row.id for row in engine.export(reader)}
    # Updating the code requires explicit removal of obsolete finding documents.
    engine.upsert_many(tenant, [document(row) for row in updated])
    for identity in obsolete:
        assert engine.delete(tenant, identity)
    assert engine.search(reader, "PT001").total == 0
    for identity in obsolete:
        try:
            engine.fetch(reader, identity)
        except (PermissionError, KeyError):
            pass
        else:
            raise AssertionError("obsolete source finding remained fetchable")
    filtered = engine.search(reader, "PT003 tag:pytrace source:public_service.py")
    evidence = engine.search(reader, "blocking async")
    assert filtered.total == evidence.total == 1
    before = visible_projection(engine.search(reader, "PT003"))
    # Publish only modified hidden evidence; the public document remains exactly unchanged.
    for row in hidden_changed:
        if row["restricted"]:
            engine.upsert(tenant, document(row))
    after = visible_projection(engine.search(reader, "PT003"))
    assert after == before
    engine.merge(tenant)
    assert visible_projection(engine.search(reader, "PT003")) == before
    # Tenant isolation also applies when another namespace contains identical terms.
    engine.upsert("another-tenant", Document("other-secret", "PT003", "blocking async PT003"))
    assert visible_projection(engine.search(reader, "PT003")) == before
    # Populate an operator cache entry, revoke, and immediately observe the ACL change.
    assert engine.search(operator, "PT002").total == 1
    engine.set_groups(tenant, "operator", [])
    assert engine.search(operator, "PT002").total == 0
    report = {
        "initial_shell": asdict(initial_shell),
        "after_fix_shell_count": 0,
        "source_filter_query": asdict(filtered),
        "evidence_query": asdict(evidence),
        "public_before_hidden_update": before,
        "public_after_hidden_update": after,
        "obsolete_ids_deleted": obsolete,
        "restricted_direct_fetch_denied": True,
        "exports_authorized": True,
        "revocation_observed_next_request": True,
        "cross_tenant_isolated": True,
        "merge_preserved_ranking": True,
    }
    (output / "atlas-evidence.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)

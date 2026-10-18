"""Analyze trusted authored fixtures, export current evidence documents and deletions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pp_pytrace import analyze

PUBLIC_INITIAL = """import subprocess as sp
import time as clock

def handler():
    command = input()
    sp.run(command, shell=True)

async def poll():
    clock.sleep(1)
"""
PUBLIC_UPDATED = PUBLIC_INITIAL.replace(
    "sp.run(command, shell=True)", 'sp.run(["echo", command], shell=False)'
)
PRIVATE_INITIAL = """def query(cursor):
    key = input()
    cursor.execute("SELECT value FROM readings WHERE key = '" + key + "'")
"""
PRIVATE_UPDATED = PRIVATE_INITIAL.replace("SELECT value", "SELECT restricted_measurement")


def documents(report: dict, source: Path) -> list[dict]:
    result = []
    for finding in report["diagnostics"]:
        if finding["rule_id"] not in {"PT001", "PT002", "PT003"}:
            continue
        selected = (source / finding["path"]).resolve(strict=True)
        if not selected.is_relative_to(source.resolve()):
            raise ValueError("finding source path escapes selected fixture root")
        lines = selected.read_text().splitlines()
        sink_line = finding["sink_location"]["line"]
        excerpt = " ".join(lines[max(0, sink_line - 2) : sink_line + 1])
        result.append(
            {
                "id": finding["path"] + ":" + finding["id"],
                "title": finding["rule_id"] + " " + finding["path"],
                "text": " ".join(
                    [
                        finding["rule_id"],
                        finding["path"],
                        finding["message"],
                        excerpt,
                        *[e["message"] for e in finding["evidence"]],
                    ]
                ),
                "restricted": finding["path"] == "private_service.py",
                "finding": finding,
            }
        )
    return result


def run(output: Path) -> None:
    source = output / "trusted-services"
    source.mkdir()
    public, private = source / "public_service.py", source / "private_service.py"
    public.write_text(PUBLIC_INITIAL)
    private.write_text(PRIVATE_INITIAL)
    cache = output / "analysis-cache.json"
    initial = analyze(source, cache).to_dict()
    initial_docs = documents(initial, source)
    assert {f["rule_id"] for f in initial["diagnostics"]} >= {"PT001", "PT002", "PT003"}
    assert len(initial_docs) == 3
    public.write_text(PUBLIC_UPDATED)
    updated = analyze(source, cache).to_dict()
    updated_docs = documents(updated, source)
    assert {d["finding"]["rule_id"] for d in updated_docs} == {"PT002", "PT003"}
    private.write_text(PRIVATE_UPDATED)
    hidden_changed = analyze(source, cache).to_dict()
    hidden_docs = documents(hidden_changed, source)
    assert [d for d in updated_docs if not d["restricted"]] == [
        d for d in hidden_docs if not d["restricted"]
    ]
    assert [d["text"] for d in updated_docs if d["restricted"]] != [
        d["text"] for d in hidden_docs if d["restricted"]
    ]
    for name, report, docs in (
        ("initial", initial, initial_docs),
        ("updated", updated, updated_docs),
        ("hidden-changed", hidden_changed, hidden_docs),
    ):
        (output / f"analysis-{name}.json").write_text(json.dumps(report, indent=2) + "\n")
        (output / f"documents-{name}.json").write_text(json.dumps(docs, indent=2) + "\n")
    deletions = sorted({d["id"] for d in initial_docs} - {d["id"] for d in updated_docs})
    assert deletions, "fix must remove the obsolete shell diagnostic document"
    (output / "delete-ids.json").write_text(json.dumps(deletions, indent=2) + "\n")
    (output / "pytrace-evidence.json").write_text(
        json.dumps(
            {
                "initial_risks": 3,
                "updated_risks": 2,
                "removed_document_ids": deletions,
                "target_programs_executed": False,
                "source_to_document_identity": "relative path + stable diagnostic ID",
                "judged_queries": {
                    "PT001": "public shell finding initially; absent after update",
                    "PT002": "restricted SQL finding; operators only",
                    "PT003": "public async blocking finding throughout",
                },
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)

"""Preserve Current's keys/revisions while checking pinned historical snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pp_quarry import Conflict, Contract, Field, Lakehouse, Snapshot


def map_delivery(row: dict) -> dict:
    aggregate = row["payload"]
    return {
        "source_namespace": f"current:{row['job_id']}:{row['operator_id']}",
        "key": row["logical_result_key"],
        "version": row["revision"],
        "operation": "upsert",
        "payload": {
            "device": aggregate["key"],
            "day": "1970-01-01",
            "value": aggregate["sum"],
            "aggregate": aggregate,
        },
    }


def run(output: Path) -> None:
    deliveries = json.loads((output / "deliveries.json").read_text())
    events = [map_delivery(row) for row in deliveries]
    contract = Contract(
        fields={
            "device": Field("string"),
            "day": Field("string"),
            "value": Field("number"),
            "aggregate": Field("json"),
        }
    )
    snapshots = []
    with Lakehouse(output / "lake") as lake:
        historical = None
        try:
            for index, event in enumerate(events):
                path = output / f"delivery-{index}.ndjson"
                path.write_text(json.dumps(event, sort_keys=True) + "\n")
                snapshot = lake.ingest(path, contract)
                snapshots.append(snapshot)
                if index == 0:
                    historical = Snapshot(lake.root, snapshot)
                with Snapshot(lake.root, snapshot) as current:
                    rows = list(current.rows("facts"))
                    assert len(rows) == 1
                    assert rows[0]["version"] == (1 if index < 2 else 2)
                    assert json.loads(rows[0]["payload"])["value"] == (10 if index < 2 else 17)
                assert historical is not None
                assert json.loads(next(historical.rows("facts"))["payload"])["value"] == 10
            # Independent full-rebuild reduction: greatest explicit revision per identity.
            oracle = {}
            for event in events:
                identity = event["source_namespace"], event["key"]
                if identity not in oracle or event["version"] > oracle[identity]["version"]:
                    oracle[identity] = event
            with Snapshot(lake.root) as current:
                actual = {
                    (r["namespace"], r["key"]): {
                        "version": r["version"],
                        "payload": json.loads(r["payload"]),
                    }
                    for r in current.rows("facts")
                }
            assert actual == {
                key: {"version": row["version"], "payload": row["payload"]}
                for key, row in oracle.items()
            }
            # Historical equal-version conflict must still fail after a newer update.
            conflicting = dict(events[0], payload={**events[0]["payload"], "value": 999})
            bad = output / "conflict.ndjson"
            bad.write_text(json.dumps(conflicting) + "\n")
            try:
                lake.ingest(bad, contract)
            except Conflict:
                pass
            else:
                raise AssertionError("historical revision conflict was silently accepted")
            report = {
                "mapping": "Current(job_id,operator_id,key,revision) → Quarry(namespace,key,version)",
                "snapshots": snapshots,
                "initial_sum": 10,
                "latest_sum": 17,
                "historical_sum": 10,
                "full_rebuild_matches": True,
                "historical_conflict_rejected": True,
                "manifests": [lake.manifest(s) for s in snapshots],
            }
            (output / "quarry-evidence.json").write_text(json.dumps(report, indent=2) + "\n")
        finally:
            if historical is not None:
                historical.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)

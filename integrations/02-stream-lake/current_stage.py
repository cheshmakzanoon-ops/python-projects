"""Emit a late-corrected aggregate and retry trace through Current's public SDK."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from pp_current import Config, Engine, Journal, Record, canonical


def run(output: Path) -> None:
    records = [
        Record("source", 0, 0, 8000, "device-1", 10),
        Record("source", 0, 1, 10000, kind="watermark"),
        Record("source", 0, 2, 9000, "device-1", 7),
        Record("source", 0, 3, 25000, kind="watermark"),
    ]
    config = Config((canonical(["source", 0]),), size=10000, slide=5000, lateness=10000)
    journal = Journal(output / "stream.sqlite")
    engine = Engine(config, job_id="stream-lake")
    versions = []
    try:
        for batch in (records[:2], records[2:]):
            for record in journal.admit(batch):
                engine.apply(record)
            journal.publish(engine)
            selected = [
                r
                for r in journal.export()
                if r["operator_id"] == "tumbling"
                and json.loads(str(r["logical_result_key"])) == ["device-1", 0, 10000]
            ]
            assert len(selected) == 1
            versions.append(selected[0])
        first, second = versions
        assert first["revision"] == 1 and first["payload"]["sum"] == 10
        assert second["revision"] == 2 and second["payload"]["sum"] == 17
        assert engine.dispositions == {"on-time": 1, "accepted-late": 1, "rejected-late": 0}
        # Same offset is one admission, even after the correction was checkpointed.
        assert journal.admit([records[0]])[0].ingress_ordinal == 1
        restored = journal.recover(config)
        assert restored.position == engine.position
        trace = [first, first, second, first]
        (output / "deliveries.json").write_text(json.dumps(trace, indent=2) + "\n")
        (output / "source-trace.json").write_text(
            json.dumps([asdict(r) for r in records], indent=2) + "\n"
        )
        (output / "current-evidence.json").write_text(
            json.dumps(
                {
                    "window": [0, 10000],
                    "expected_initial_sum": 10,
                    "expected_corrected_sum": 17,
                    "dispositions": engine.dispositions,
                    "delivery_revisions": [r["revision"] for r in trace],
                },
                indent=2,
            )
            + "\n"
        )
    finally:
        journal.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)

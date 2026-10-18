"""Operator CLI and a two-owner-phase crash demonstration."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from pp_strata import Database
from pp_strata.evidence import provenance
from pp_strata.io import durable_mkdir
from pp_strata.workloads import benchmark

MARKER = ".strata-owned-output"
OWNED = {
    "catalog",
    "crash-db",
    "backup",
    "restored",
    "workload",
    "churn",
    "demo.json",
    "timeline.txt",
    "benchmark.json",
}


def output_directory(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("output must be an absolute, nonsymlink path")
    path = path.resolve()
    if path.exists() and any(path.iterdir()):
        marker = path / MARKER
        if (
            marker.is_symlink()
            or not marker.is_file()
            or marker.read_text() != "pp-strata-output-v1\n"
        ):
            raise ValueError("nonempty output is not owned by Strata")
    if any((path / name).is_symlink() for name in OWNED):
        raise ValueError("refusing symbolic link in owned output")
    durable_mkdir(path)
    (path / MARKER).write_text("pp-strata-output-v1\n")
    return path


def clean_output(raw: str) -> None:
    path = Path(raw)
    if not path.is_absolute() or path.is_symlink() or not path.exists():
        raise ValueError("clean requires an existing absolute nonsymlink output")
    marker = path / MARKER
    if marker.is_symlink() or not marker.is_file() or marker.read_text() != "pp-strata-output-v1\n":
        raise ValueError("refusing to clean an unowned directory")
    # Only fixed owned direct children; unrelated caller files survive.
    for name in OWNED:
        child = path / name
        if child.is_symlink():
            raise ValueError("refusing symbolic link in owned output")
    for name in OWNED:
        child = path / name
        if child.is_dir():
            shutil.rmtree(child)
        elif child.exists():
            child.unlink()
    marker.unlink()
    if not any(path.iterdir()):
        path.rmdir()


def crash_worker(path: Path) -> None:
    def kill(name: str) -> None:
        if name == "after_wal_sync" and db.sequence == 10:
            os._exit(81)

    with Database.open(path, failpoint=kill) as db:
        for index in range(10):
            with db.begin() as tx:
                tx.put(f"ack:{index}".encode(), b"durable")
            print(json.dumps({"acknowledged": index, "sequence": db.sequence}), flush=True)
        with db.begin() as tx:
            tx.put(b"uncertain:a", b"complete")
            tx.put(b"uncertain:b", b"complete")
    raise RuntimeError("controlled kill was not reached")


def demo(output: Path, seed: int) -> dict[str, object]:
    if any((output / name).exists() for name in ("catalog", "crash-db", "backup", "restored")):
        raise ValueError("demo state already exists; run clean-demo first")
    timeline: list[str] = []
    with Database.open(output / "catalog") as db:
        with db.begin() as tx:
            for index in range(20):
                tx.put(f"catalog:{index:04}".encode(), f"edition-1:{seed}:{index}".encode())
        with db.snapshot() as old:
            old_rows = list(old.scan())
            timeline.append(
                f"snapshot sequence={old.sequence} contains {len(old_rows)} catalog entries"
            )
            with db.begin() as tx:
                tx.delete(b"catalog:0000")
                tx.put(b"catalog:0001", b"edition-2")
            db.flush()
            db.compact()
            assert list(old.scan()) == old_rows
            timeline.append("overwrite, delete, flush, compaction: old snapshot remains unchanged")
            db.backup(output / "backup", snapshot=old)
            historical_sequence = old.sequence
        with db.snapshot() as current:
            assert current.get(b"catalog:0000") is None
            assert current.get(b"catalog:0001") == b"edition-2"
        inspection = db.inspect()
    Database.restore(output / "backup", output / "restored")
    with Database.open(output / "restored") as db, db.snapshot() as snap:
        assert list(snap.scan()) == old_rows
    timeline.append("closed all original owner handles; historical backup restored and verified")
    process = subprocess.run(
        [sys.executable, "-m", "pp_strata.cli", "_crash-worker", str(output / "crash-db")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if process.returncode != 81:
        raise RuntimeError(f"crash worker failed: {process.returncode} {process.stderr}")
    acknowledgements = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(acknowledgements) == 10
    timeline.append(
        "subprocess acknowledged 10 durable commits, then terminated after the next WAL fsync"
    )
    with Database.open(output / "crash-db") as db, db.snapshot() as snap:
        assert all(snap.get(f"ack:{i}".encode()) == b"durable" for i in range(10))
        assert snap.get(b"uncertain:a") == snap.get(b"uncertain:b") == b"complete"
        recovered_sequence = db.sequence
        db.verify()
    timeline.append(
        f"new owner recovered sequence={recovered_sequence}; all acknowledgements retained; uncertain batch is complete"
    )
    (output / "timeline.txt").write_text("\n".join(timeline) + "\n")
    return {
        **provenance(),
        "seed": seed,
        "status": "passed",
        "historical_snapshot_sequence": historical_sequence,
        "catalog_inspection": inspection,
        "acknowledged_transactions": len(acknowledgements),
        "recovered_sequence": recovered_sequence,
        "checks": {
            "snapshot_survives_compaction": True,
            "backup_restores_historical_snapshot": True,
            "all_acknowledged_transactions_recover": True,
            "unacknowledged_batch_atomic": True,
        },
        "timeline": timeline,
        "durability_boundary": "POSIX fsync/rename and controlled process termination; no power-loss claim",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Strata snapshot-isolated byte storage")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("demo", "benchmark"):
        command = commands.add_parser(name)
        command.add_argument("--output", required=True)
        command.add_argument("--seed", type=int, default=1729)
        if name == "benchmark":
            command.add_argument("--profile", choices=("ci", "standard"), default="ci")
    commands.add_parser("clean-demo").add_argument("--output", required=True)
    for name in ("inspect", "verify", "compact", "_crash-worker"):
        commands.add_parser(name).add_argument("path", type=Path)
    for name in ("backup", "restore"):
        command = commands.add_parser(name)
        command.add_argument("path", type=Path)
        command.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.command == "clean-demo":
        clean_output(args.output)
        print("Removed Strata-owned output.")
        return
    if args.command == "_crash-worker":
        crash_worker(args.path)
        return
    if args.command in ("demo", "benchmark"):
        output = output_directory(args.output)
        if args.command == "demo":
            report = demo(output, args.seed)
            destination = output / "demo.json"
        else:
            if any((output / name).exists() for name in ("workload", "churn")):
                raise ValueError("benchmark state already exists; run clean-demo first")
            report = benchmark(output, args.profile, args.seed)
            destination = output / "benchmark.json"
        destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": report["status"], "report": str(destination)}))
    elif args.command == "restore":
        print(json.dumps(Database.restore(args.path, args.destination), indent=2))
    else:
        with Database.open(args.path) as db:
            if args.command == "compact":
                db.compact()
                result = db.inspect()
            elif args.command == "backup":
                result = db.backup(args.destination)
            elif args.command == "verify":
                result = db.verify()
            else:
                result = db.inspect()
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

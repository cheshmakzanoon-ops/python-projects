"""Catalog-driven orphan recovery and explicit pin-aware retention."""

from __future__ import annotations

import json
from typing import Any

from pp_quarry.execution.engine import Lakehouse
from pp_quarry.storage.files import manifest_path
from pp_quarry.storage.manifest import validate_manifest


def _references(lake: Lakehouse) -> set[str]:
    referenced: set[str] = set()
    for row in lake.db.execute("SELECT manifest FROM snapshots"):
        manifest = validate_manifest(json.loads(row[0]), lake.config.buckets)
        for nodes in manifest["partitions"].values():
            for entry in nodes.values():
                # Never use a malformed manifest to classify a live file as
                # an orphan. Missing or unsafe references require diagnosis.
                path = manifest_path(lake.root, entry["path"])
                referenced.add(path.relative_to(lake.root).as_posix())
    return referenced


def recover(lake: Lakehouse, *, retain: int | None = None) -> dict[str, Any]:
    if retain is not None and (type(retain) is not int or retain < 1):
        raise ValueError("retain must be an integer >=1")
    lake.db.execute("BEGIN IMMEDIATE")
    try:
        if retain is not None:
            kept = set(lake.snapshots()[-retain:])
            kept.update(r[0] for r in lake.db.execute("SELECT snapshot FROM pins"))
            for snapshot in lake.snapshots():
                if snapshot not in kept:
                    lake.db.execute("DELETE FROM snapshots WHERE id=?", (snapshot,))
        _references(lake)
        # Retention deletion is durable before unlink: a crash must never roll back
        # catalog rows whose files were already removed. Reacquire the writer lock
        # and recompute references to include any intervening publication.
        lake.db.commit()
        lake.db.execute("BEGIN IMMEDIATE")
        referenced = _references(lake)
        removed = []
        for path in (lake.root / "data").iterdir():
            if path.is_symlink() or not path.is_file() or path.suffix != ".parquet":
                raise ValueError("unexpected file in owned data directory; refusing deletion")
            if path.relative_to(lake.root).as_posix() not in referenced:
                path.unlink()
                removed.append(path.name)
        lake.db.commit()
        return {
            "removed_orphans": removed,
            "snapshots": lake.snapshots(),
            "active_pins": lake.db.execute("SELECT count(*) FROM pins").fetchone()[0],
        }
    except BaseException:
        lake.db.rollback()
        raise

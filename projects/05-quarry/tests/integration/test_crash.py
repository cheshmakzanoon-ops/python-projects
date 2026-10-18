from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from pp_quarry import Config, Lakehouse, Snapshot, recover
from tests.conftest import event, source


@pytest.mark.parametrize(
    "boundary,committed", [("after_files", False), ("before_commit", False), ("after_commit", True)]
)
def test_real_process_death_at_publication(tmp_path: Path, boundary: str, committed: bool) -> None:
    path = source(tmp_path, [event()])
    root = tmp_path / "lake"
    with Lakehouse(root, Config(buckets=2)):
        pass
    code = "from pp_quarry import Lakehouse; import sys; Lakehouse(sys.argv[1]).ingest(sys.argv[2],fault=sys.argv[3])"
    proc = subprocess.run(
        [sys.executable, "-c", code, str(root), str(path), boundary],
        env={**os.environ, "QUARRY_HARD_CRASH": "1"},
        timeout=30,
        capture_output=True,
    )
    assert proc.returncode == 91, proc.stderr.decode()
    with Lakehouse(root) as lake:
        assert bool(lake.snapshots()) is committed
        assert lake.db.execute("SELECT count(*) FROM sources").fetchone()[0] == int(committed)
        recover(lake)
        lake.ingest(path)
        lake.validate()
        with Snapshot(root) as pinned:
            assert next(pinned.rows())["value"] == 3

import asyncio
import uuid
import zipfile

import psycopg
import pytest
from psycopg import sql

from pp_anchor import Definition, Engine, Step, drain
from pp_anchor.persistence.snapshot import backup, restore


def test_real_postgres_snapshot_restore_and_corruption(engine, dsn, tmp_path):
    completed = engine.submit(
        Definition("complete", 1, (Step("x"),)), {"artifact": "synthetic"}, "complete"
    )
    asyncio.run(drain(engine))
    waiting = engine.submit(
        Definition("pending", 1, (Step("timer", kind="timer", delay=100),)), {}, "pending"
    )
    snapshot = tmp_path / "backup.zip"
    backup(engine, snapshot)
    with pytest.raises(FileExistsError):
        backup(engine, snapshot)
    target_schema = "anchor_test_" + uuid.uuid4().hex[:20]
    try:
        with Engine(dsn, target_schema) as target:
            restore(target, snapshot)
            assert target.history(completed) == engine.history(completed)
            assert target.replay(completed).status == "completed"
            assert target.replay(waiting).status == "running"
            assert target.tick(advance_seconds=101) == 1
            assert target.replay(waiting).status == "completed"
            assert (
                target.submit(
                    Definition("complete", 1, (Step("x"),)), {"artifact": "synthetic"}, "complete"
                )
                == completed
            )
            with pytest.raises(ValueError, match="empty"):
                restore(target, snapshot)
    finally:
        with psycopg.connect(dsn, autocommit=True) as c:
            c.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(target_schema))
            )
    bad = tmp_path / "corrupt.zip"
    with zipfile.ZipFile(snapshot) as source, zipfile.ZipFile(bad, "w") as archive:
        for name in source.namelist():
            archive.writestr(name, b"altered" if name == "signals.copy" else source.read(name))
    with pytest.raises(ValueError, match="checksum"):
        restore(engine, bad)
    traversal = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal, "w") as archive:
        archive.writestr("../outside", "bad")
    with pytest.raises(ValueError, match="members"):
        restore(engine, traversal)
    link = tmp_path / "link"
    link.symlink_to(snapshot)
    with pytest.raises(ValueError, match="symlinks"):
        restore(engine, link)
    with pytest.raises(ValueError):
        backup(engine, tmp_path / "link")
    assert not (tmp_path / "outside").exists()

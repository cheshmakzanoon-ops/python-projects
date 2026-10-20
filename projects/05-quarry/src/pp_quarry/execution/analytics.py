"""Bounded DuckDB sessions and the shared daily-reduction contract."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb

from pp_quarry.storage.files import literal

DAILY_AGGREGATE = (
    'SELECT "day",sum(count)::BIGINT count,sum(total) total FROM read_parquet(?) GROUP BY "day"'
)


@contextmanager
def analytical_session(
    root: Path, *, memory_mb: int = 128, threads: int = 1
) -> Iterator[duckdb.DuckDBPyConnection]:
    if (
        type(memory_mb) is not int
        or memory_mb < 32
        or type(threads) is not int
        or threads not in {1, 2}
    ):
        raise ValueError("analytical memory must be an integer >=32 MB and threads must be 1 or 2")
    with duckdb.connect() as engine:
        engine.execute(f"SET memory_limit='{memory_mb}MB'")
        engine.execute(f"SET threads={threads}")
        engine.execute(f"SET temp_directory={literal(str(root / 'tmp'))}")
        yield engine


def check_daily_totals(engine: duckdb.DuckDBPyConnection, paths: list[str]) -> None:
    """Finite source values can still overflow within or across bucket sums."""
    try:
        invalid = engine.execute(
            f"SELECT 1 FROM ({DAILY_AGGREGATE}) WHERE NOT isfinite(total) LIMIT 1", [paths]
        ).fetchone()
    except duckdb.OutOfRangeException as exc:
        raise ValueError("daily aggregation exceeds finite DOUBLE range") from exc
    if invalid is not None:
        raise ValueError("daily aggregation exceeds finite DOUBLE range")

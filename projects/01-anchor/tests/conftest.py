import os
import uuid

import psycopg
import pytest
from psycopg import sql

from pp_anchor import Engine


@pytest.fixture
def dsn() -> str:
    value = os.environ.get("ANCHOR_DATABASE_URL")
    if not value:
        pytest.fail("ANCHOR_DATABASE_URL is required: required PostgreSQL tests never skip")
    return value


@pytest.fixture
def engine(dsn: str):
    schema = "anchor_test_" + uuid.uuid4().hex[:20]
    with Engine(dsn, schema) as value:
        yield value
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))

"""Recognize format-v1 SQLite structure before accepting durable records."""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from functools import cache

STATEMENTS = (
    "CREATE TABLE format(version INTEGER NOT NULL)",
    """CREATE TABLE ingress(ordinal INTEGER PRIMARY KEY, source TEXT NOT NULL,
       partition INTEGER NOT NULL, offset INTEGER NOT NULL, wire TEXT NOT NULL,
       UNIQUE(source,partition,offset))""",
    """CREATE TABLE checkpoint(id INTEGER PRIMARY KEY CHECK(id=1),
       position INTEGER NOT NULL, state TEXT NOT NULL)""",
    """CREATE TABLE deliveries(job TEXT,operator TEXT,key TEXT,revision INTEGER,
       payload TEXT NOT NULL,sent INTEGER NOT NULL DEFAULT 0,
       PRIMARY KEY(job,operator,key,revision))""",
    """CREATE TABLE results(job TEXT,operator TEXT,key TEXT,revision INTEGER,
       payload TEXT NOT NULL,PRIMARY KEY(job,operator,key))""",
)
TABLES = ("format", "ingress", "checkpoint", "deliveries", "results")

_TOKENS = re.compile(
    r"--[^\n]*|/\*.*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|"
    r"`(?:``|[^`])*`|\[[^\]]*\]|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|[^\s]",
    re.DOTALL,
)


def _tokens(sql: str) -> list[str]:
    return [
        token if token[0] in "'\"`[" else token.lower()
        for token in _TOKENS.findall(sql)
        if not token.startswith(("--", "/*"))
    ]


def _checks(tokens: list[str]) -> tuple[tuple[str, ...], ...]:
    """Extract tokenized CHECK expressions; SQLite has no CHECK metadata pragma.

    Format v1 supports its declared expressions, ignoring whitespace, comments
    and keyword case. Other expressions require an explicit format migration.
    Quoted literals remain single tokens, so their contents cannot add checks.
    """
    checks = []
    for position, token in enumerate(tokens):
        if token != "check" or tokens[position + 1 : position + 2] != ["("]:
            continue
        depth = 1
        end = position + 2
        while end < len(tokens) and depth:
            depth += (tokens[end] == "(") - (tokens[end] == ")")
            end += 1
        if depth:
            raise ValueError("unrecognized journal schema")
        checks.append(tuple(tokens[position + 2 : end - 1]))
    return tuple(sorted(checks))


def _identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _signature(db: sqlite3.Connection, table: str) -> dict[str, object]:
    name = _identifier(table)
    indexes = [
        (
            index[2],  # unique
            index[3],  # primary key, unique constraint or explicit index
            index[4],  # partial
            tuple(db.execute(f"PRAGMA index_xinfo({_identifier(index[1])})")),
        )
        for index in db.execute(f"PRAGMA index_list({name})")
    ]
    sql = db.execute(
        "SELECT sql FROM sqlite_schema WHERE type='table' AND name=?", (table,)
    ).fetchone()[0]
    tokens = _tokens(sql)
    return {
        "columns": tuple(db.execute(f"PRAGMA table_xinfo({name})")),
        "indexes": tuple(sorted(indexes, key=repr)),
        "foreign_keys": tuple(db.execute(f"PRAGMA foreign_key_list({name})")),
        "table_flags": db.execute(
            "SELECT wr,strict FROM pragma_table_list WHERE schema='main' AND name=?", (table,)
        ).fetchone(),
        "checks": _checks(tokens),
        # Column collations and ON CONFLICT policies have no table-info
        # metadata. A case-insensitive payload column would weaken exact
        # acknowledgement matching despite unchanged primary keys.
        "collations": tuple(
            tokens[position + 1] for position, token in enumerate(tokens) if token == "collate"
        ),
        "conflict_policies": tuple(
            tokens[position + 2]
            for position in range(len(tokens) - 2)
            if tokens[position : position + 2] == ["on", "conflict"]
        ),
    }


@cache
def _expected() -> dict[str, dict[str, object]]:
    # Derive metadata from the same declarations used for initialization rather
    # than maintaining a second, subtly different list of constraint rules.
    with closing(sqlite3.connect(":memory:")) as db:
        for statement in STATEMENTS:
            db.execute(statement)
        return {table: _signature(db, table) for table in TABLES}


def validate(db: sqlite3.Connection, *, allow_empty: bool) -> bool:
    # LIKE's underscore wildcard would also hide user objects named sqliteX...
    schema = db.execute(
        "SELECT name,type FROM sqlite_schema WHERE name NOT GLOB 'sqlite_*'"
    ).fetchall()
    if not schema and allow_empty:
        return False
    if dict(schema) != dict.fromkeys(TABLES, "table"):
        raise ValueError("unrecognized journal schema")
    expected = _expected()
    if any(_signature(db, table) != expected[table] for table in TABLES):
        raise ValueError("unrecognized journal schema")
    if db.execute("SELECT version FROM format").fetchall() != [(1,)]:
        raise ValueError("unsupported journal format")
    return True

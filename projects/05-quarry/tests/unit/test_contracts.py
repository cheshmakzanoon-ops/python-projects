from __future__ import annotations

import pytest

from pp_quarry import Config, Contract, Event, Field
from pp_quarry.planning.dag import Node, order
from pp_quarry.planning.partitions import bucket


@pytest.mark.parametrize("version", [-1, True, 1.5])
def test_version_rejects_invalid(version: int) -> None:
    with pytest.raises(ValueError):
        Event("a", "b", version, "delete", {})


def test_canonical_and_bucket() -> None:
    a = Event("n", "κ", 2, "upsert", {"b": 1, "a": 2})
    b = Event("n", "κ", 2, "upsert", {"a": 2, "b": 1})
    assert a.fingerprint == b.fingerprint
    assert (
        bucket(a.key_bytes, 8)
        == int.from_bytes(__import__("hashlib").sha256('["n","κ"]'.encode()).digest()[:8], "big")
        % 8
    )
    with pytest.raises(ValueError, match="delete payload"):
        Event("n", "k", 1, "delete", {"x": 1})
    with pytest.raises(ValueError):
        bucket(b"x", 0)


def test_schema_nullable_addition_and_migration() -> None:
    original = Contract()
    Contract({**original.fields, "firmware": Field("string", True)}).compatible(original)
    with pytest.raises(ValueError, match="migration required"):
        Contract({**original.fields, "firmware": Field("string")}).compatible(original)
    with pytest.raises(ValueError, match="value"):
        Contract({**original.fields, "value": Field("integer")}).compatible(original)
    with pytest.raises(ValueError, match="value"):
        Contract({"day": Field("string"), "device": Field("string")}).compatible(original)


def test_dag_cycles_unknown_nodes_invalid_config() -> None:
    with pytest.raises(ValueError, match="cycle"):
        order((Node("a", "facts", ("b",)), Node("b", "facts", ("a",))))
    with pytest.raises(ValueError, match="unknown"):
        order((Node("a", "facts", ("missing",)),))
    with pytest.raises(ValueError, match="unsupported"):
        order((Node("a", "arbitrary_sql"),))
    with pytest.raises(ValueError, match="arity"):
        order((Node("a", "normalize", ("a",)),))
    with pytest.raises(ValueError, match="duplicate"):
        order((Node("a", "normalize"), Node("a", "normalize")))
    with pytest.raises(ValueError):
        Config(batch_size=100000)
    with pytest.raises(ValueError):
        Contract(minimum=5, maximum=2)
    with pytest.raises(ValueError):
        Contract({"bad": Field("unknown")})

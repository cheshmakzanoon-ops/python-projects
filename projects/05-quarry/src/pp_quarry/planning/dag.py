"""Declarative partition-local execution graph and semantic fingerprints."""

import hashlib
from dataclasses import dataclass

from pp_quarry.model.events import canonical


@dataclass(frozen=True)
class Node:
    name: str
    transform: str
    parents: tuple[str, ...] = ()
    contract_version: int = 1


def order(nodes: tuple[Node, ...]) -> tuple[Node, ...]:
    index = {n.name: n for n in nodes}
    if len(index) != len(nodes):
        raise ValueError("duplicate DAG node")
    result: list[Node] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise ValueError("DAG cycle")
        if name in visited:
            return
        if name not in index:
            raise ValueError(f"unknown DAG dependency {name}")
        node = index[name]
        if node.transform not in {"normalize", "facts", "daily"} or node.contract_version < 1:
            raise ValueError("unsupported transform or contract version")
        expected = {"normalize": 0, "facts": 1, "daily": 1}[node.transform]
        if len(node.parents) != expected:
            raise ValueError("invalid transform arity")
        visiting.add(name)
        for parent in node.parents:
            visit(parent)
        visiting.remove(name)
        visited.add(name)
        result.append(node)

    for node in nodes:
        visit(node.name)
    return tuple(result)


DEFAULT_DAG = (
    Node("normalized", "normalize"),
    Node("facts", "facts", ("normalized",)),
    Node("daily", "daily", ("facts",)),
)


def fingerprint(node: Node, inputs: list[str], schema: str, code_digest: str) -> str:
    return hashlib.sha256(
        canonical(
            [
                node.name,
                node.transform,
                node.parents,
                node.contract_version,
                inputs,
                schema,
                code_digest,
            ]
        ).encode()
    ).hexdigest()

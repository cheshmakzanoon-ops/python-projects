"""Statement basic blocks and explicit normal/loop edges.

Exception handlers are conservatively reachable from try entry. Exception timing,
finally return override, match destructuring, and with suppression are coverage
boundaries reported by the analyzer; no soundness claim extends through them.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass
class Block:
    index: int
    node: ast.stmt | None
    successors: list[int] = field(default_factory=list)


@dataclass
class Graph:
    blocks: dict[int, Block]
    entry: int


def build(statements: list[ast.stmt]) -> Graph:
    blocks: dict[int, Block] = {0: Block(0, None)}

    def add(node: ast.stmt) -> int:
        idx = len(blocks)
        blocks[idx] = Block(idx, node)
        return idx

    def sequence(nodes: list[ast.stmt], following: int, stop: int, again: int) -> int:
        current = following
        for node in reversed(nodes):
            idx = add(node)
            if isinstance(node, ast.If):
                blocks[idx].successors = [
                    sequence(node.body, current, stop, again),
                    sequence(node.orelse, current, stop, again),
                ]
            elif isinstance(node, (ast.While, ast.For, ast.AsyncFor)):
                end = sequence(node.orelse, current, stop, again)
                blocks[idx].successors = [sequence(node.body, idx, current, idx), end]
            elif isinstance(node, ast.Break):
                blocks[idx].successors = [stop]
            elif isinstance(node, ast.Continue):
                blocks[idx].successors = [again]
            elif isinstance(node, (ast.Return, ast.Raise)):
                blocks[idx].successors = [0]
            elif isinstance(node, (ast.Try, ast.TryStar)):
                final = sequence(node.finalbody, current, stop, again)
                normal = sequence(node.orelse, final, stop, again)
                blocks[idx].successors = [sequence(node.body, normal, stop, again)] + [
                    sequence(handler.body, final, stop, again) for handler in node.handlers
                ]
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                blocks[idx].successors = [sequence(node.body, current, stop, again)]
            elif isinstance(node, ast.Match):
                blocks[idx].successors = [
                    sequence(case.body, current, stop, again) for case in node.cases
                ] + [current]
            else:
                blocks[idx].successors = [current]
            current = idx
        return current

    entry = sequence(statements, 0, 0, 0)
    return Graph(blocks, entry)

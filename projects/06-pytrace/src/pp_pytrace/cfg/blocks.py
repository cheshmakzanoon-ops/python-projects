"""Structured control flow with explicit normal, exceptional and abrupt exits.

Finally suites are specialized by continuation: the same syntax can run on a
normal path, return, raise, break or continue. Exception types remain a may-match
approximation; exceptional edges join state before and after the raising block.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Literal

Operation = Literal[
    "statement",
    "for-init",
    "for-next",
    "for-bind",
    "except-enter",
    "except-clear",
    "match-init",
    "match-case",
]


@dataclass
class Block:
    index: int
    node: ast.AST | None
    successors: list[int] = field(default_factory=list)
    exceptional_successors: list[int] = field(default_factory=list)
    operation: Operation = "statement"
    temporary: str = ""


@dataclass
class Graph:
    blocks: dict[int, Block]
    entry: int
    normal_exit: int = 0
    return_exit: int = 1
    raise_exit: int = 2


@dataclass(frozen=True)
class Continuations:
    returned: int
    raised: int
    broken: int
    continued: int
    exceptional: int | None = None


def build(statements: list[ast.stmt], *, max_blocks: int = 20_000) -> Graph:
    if max_blocks < 3:
        raise ValueError("Control-flow block budget must include the three exits")
    blocks = {index: Block(index, None) for index in range(3)}
    sequences: dict[tuple[tuple[int, ...], int, Continuations], int] = {}

    def add(node: ast.AST | None, operation: Operation = "statement", temporary: str = "") -> int:
        if len(blocks) >= max_blocks:
            raise ValueError(f"Control-flow graph exceeds {max_blocks} blocks")
        index = len(blocks)
        blocks[index] = Block(index, node, operation=operation, temporary=temporary)
        return index

    def exceptional(index: int, exits: Continuations) -> None:
        if exits.exceptional is not None:
            blocks[index].exceptional_successors = [exits.exceptional]

    def sequence(nodes: list[ast.stmt], following: int, exits: Continuations) -> int:
        if not nodes:
            return following
        cache_key = tuple(map(id, nodes)), following, exits
        if cache_key in sequences:
            return sequences[cache_key]
        current = following
        for node in reversed(nodes):
            index = add(node)
            block = blocks[index]
            if isinstance(node, ast.If):
                block.successors = [
                    sequence(node.body, current, exits),
                    sequence(node.orelse, current, exits),
                ]
                exceptional(index, exits)
            elif isinstance(node, ast.While):
                end = sequence(node.orelse, current, exits)
                loop = Continuations(
                    exits.returned, exits.raised, current, index, exits.exceptional
                )
                block.successors = [sequence(node.body, index, loop), end]
                exceptional(index, exits)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                key = f"\0iterator:{index}"
                block.operation, block.temporary = "for-init", key
                step = add(node, "for-next", key)
                binding = add(node, "for-bind", key)
                loop = Continuations(exits.returned, exits.raised, current, step, exits.exceptional)
                blocks[binding].successors = [sequence(node.body, step, loop)]
                empty = (
                    isinstance(node.iter, (ast.List, ast.Tuple, ast.Set))
                    and not node.iter.elts
                    or isinstance(node.iter, ast.Dict)
                    and not node.iter.keys
                    or isinstance(node.iter, ast.Constant)
                    and node.iter.value in ("", b"")
                )
                blocks[step].successors = ([] if empty else [binding]) + [
                    sequence(node.orelse, current, exits)
                ]
                nonempty = (
                    isinstance(node.iter, (ast.List, ast.Tuple, ast.Set))
                    and bool(node.iter.elts)
                    and not any(isinstance(item, ast.Starred) for item in node.iter.elts)
                    or isinstance(node.iter, ast.Dict)
                    and any(key is not None for key in node.iter.keys)
                    or isinstance(node.iter, ast.Constant)
                    and isinstance(node.iter.value, (str, bytes))
                    and bool(node.iter.value)
                )
                # A literal with a known element cannot take the exhaustion edge
                # before its first body execution. Later iterations still may end.
                block.successors = [binding if nonempty else step]
                exceptional(index, exits)
                exceptional(step, exits)
                exceptional(binding, exits)
            elif isinstance(node, ast.Break):
                block.successors = [exits.broken]
            elif isinstance(node, ast.Continue):
                block.successors = [exits.continued]
            elif isinstance(node, ast.Return):
                block.successors = [exits.returned]
                exceptional(index, exits)
            elif isinstance(node, ast.Raise):
                block.successors = [exits.raised]
                # Evaluating the exception or its ``from`` cause can fail
                # before later expression writes run. Preserve those prefixes
                # on the exceptional route just as for a return expression.
                exceptional(index, exits)
            elif isinstance(node, (ast.Try, ast.TryStar)):
                finals: dict[int, int] = {}

                def finish(destination: int) -> int:
                    if destination not in finals:
                        finals[destination] = sequence(node.finalbody, destination, exits)
                    return finals[destination]

                protected = Continuations(
                    finish(exits.returned),
                    finish(exits.raised),
                    finish(exits.broken),
                    finish(exits.continued),
                    finish(exits.raised) if node.finalbody else exits.exceptional,
                )
                normal = sequence(node.orelse, finish(current), protected)
                dispatch = add(None)
                handlers = []
                for handler in node.handlers:
                    handler_exits = protected
                    after = finish(current)
                    if handler.name:
                        cleared: dict[int, int] = {}

                        def clear(destination: int) -> int:
                            if destination not in cleared:
                                cleanup = add(handler, "except-clear")
                                blocks[cleanup].successors = [destination]
                                cleared[destination] = cleanup
                            return cleared[destination]

                        after = clear(after)
                        handler_exits = Continuations(
                            clear(protected.returned),
                            clear(protected.raised),
                            clear(protected.broken),
                            clear(protected.continued),
                            clear(protected.raised),
                        )
                    entered = add(handler, "except-enter")
                    blocks[entered].successors = [sequence(handler.body, after, handler_exits)]
                    exceptional(entered, protected)
                    handlers.append(entered)
                if not any(handler.type is None for handler in node.handlers):
                    handlers.append(protected.raised)
                blocks[dispatch].successors = handlers
                body_exits = Continuations(
                    protected.returned, dispatch, protected.broken, protected.continued, dispatch
                )
                block.successors = [sequence(node.body, normal, body_exits)]
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                block.successors = [sequence(node.body, current, exits)]
                exceptional(index, exits)
            elif isinstance(node, ast.Match):
                key = f"\0match:{index}"
                block.operation, block.temporary = "match-init", key
                following_case = current
                for case in reversed(node.cases):
                    chosen = add(case, "match-case", key)
                    blocks[chosen].successors = [sequence(case.body, current, exits)]
                    if case.guard is not None:
                        blocks[chosen].successors.append(following_case)
                    exceptional(chosen, exits)
                    selection = add(None)
                    irrefutable = (
                        isinstance(case.pattern, ast.MatchAs) and case.pattern.pattern is None
                    )
                    blocks[selection].successors = [chosen] + (
                        [] if irrefutable else [following_case]
                    )
                    following_case = selection
                block.successors = [following_case]
                exceptional(index, exits)
            else:
                block.successors = [current]
                if not isinstance(node, (ast.Pass, ast.Global, ast.Nonlocal)):
                    exceptional(index, exits)
            current = index
        sequences[cache_key] = current
        return current

    return Graph(blocks, sequence(statements, 0, Continuations(1, 2, 0, 0)))

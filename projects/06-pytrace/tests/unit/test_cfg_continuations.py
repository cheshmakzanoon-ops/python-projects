from __future__ import annotations

import ast
import textwrap

import pytest

from pp_pytrace.cfg.blocks import build


def test_for_iterator_initialization_is_outside_the_cycle() -> None:
    graph = build(ast.parse("for item in obtain():\n work(item)\nelse:\n done()\n").body)
    initialization = next(block for block in graph.blocks.values() if block.operation == "for-init")
    step = next(block for block in graph.blocks.values() if block.operation == "for-next")
    assert graph.entry == initialization.index
    assert initialization.successors == [step.index]
    assert all(initialization.index not in block.successors for block in graph.blocks.values())
    binding = next(block for block in graph.blocks.values() if block.operation == "for-bind")
    assert binding.index in step.successors
    assert len(step.successors) == 2


def test_try_exception_edges_leave_each_protected_statement() -> None:
    graph = build(ast.parse("try:\n first()\n second()\nexcept ValueError:\n recover()\n").body)
    protected = [
        block
        for block in graph.blocks.values()
        if isinstance(block.node, ast.Expr) and block.node.lineno in (2, 3)
    ]
    assert len(protected) == 2
    assert protected[0].exceptional_successors == protected[1].exceptional_successors
    assert protected[0].exceptional_successors
    handler = next(block for block in graph.blocks.values() if block.operation == "except-enter")
    dispatch = graph.blocks[protected[0].exceptional_successors[0]]
    assert handler.index in dispatch.successors


def test_finally_return_overrides_pending_return_and_skips_following_code() -> None:
    function = ast.parse(
        "def f():\n try:\n  return 1\n finally:\n  return 2\n unreachable()\n"
    ).body[0]
    assert isinstance(function, ast.FunctionDef)
    graph = build(function.body)
    pending = [graph.entry]
    reachable = set()
    while pending:
        index = pending.pop()
        if index not in reachable:
            reachable.add(index)
            pending.extend(graph.blocks[index].successors)
    lines = {getattr(graph.blocks[index].node, "lineno", 0) for index in reachable}
    assert 3 in lines and 5 in lines and 6 not in lines
    assert graph.return_exit in reachable and graph.normal_exit not in reachable


def test_nested_finally_continuations_share_identical_suffixes() -> None:
    source = "pass\n"
    counts = []
    for _ in range(12):
        source = "try:\n pass\nfinally:\n" + textwrap.indent(source, " ")
        counts.append(len(build(ast.parse(source).body).blocks))
    # Small nested suites must not request an exponential number of clones.
    # A linear envelope leaves margin for distinct abrupt continuations.
    assert counts[-1] < 100 * 12
    assert counts[-1] < 4 * counts[5]


def test_explicit_cfg_budget_refuses_expansion() -> None:
    with pytest.raises(ValueError, match="exceeds 8 blocks"):
        build(ast.parse("value=1\n" * 10).body, max_blocks=8)

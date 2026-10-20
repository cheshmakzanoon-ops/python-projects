"""Execute only these authored fixtures against harmless stand-ins, never targets.

The concrete interpreter is CPython itself. Fake process APIs collect source
locations instead of launching processes; this oracle does not reuse CFG/lattice
implementation details or the analyzer's rule-matching logic.
"""

from __future__ import annotations

import ast
import builtins
import dis
import itertools
import symtable
import sys
import warnings
from types import CodeType, SimpleNamespace

import pytest

from pp_pytrace.analysis.engine import Analyzer
from pp_pytrace.frontend.discovery import parse

TAINT = "USER_SUPPLIED_TEST_VALUE"


def concrete_shell_lines(source: str, *, call: str | None = None, flag: bool = True) -> set[int]:
    observed: set[int] = set()

    def process(command: object, **options: object) -> None:
        if TAINT in str(command):
            observed.add(sys._getframe(1).f_lineno)

    def imports(name: str, *args: object, **kwargs: object) -> object:
        if name == "os":
            return SimpleNamespace(system=process)
        if name == "subprocess":
            return SimpleNamespace(run=process)
        raise AssertionError(f"fixture attempted an unexpected import: {name}")

    namespace = {
        "__builtins__": {**vars(builtins), "__import__": imports, "input": lambda: TAINT},
        "flag": flag,
        "unknown": lambda *args, **kwargs: None,
    }
    try:
        with warnings.catch_warnings(record=True) as emitted:
            program = compile(source, "owned-fixture.py", "exec")
        assert all(
            issubclass(item.category, SyntaxWarning) and "finally" in str(item.message)
            for item in emitted
        )
        exec(program, namespace)
        if call:
            namespace[call]()
    except (ValueError, UnboundLocalError):
        pass  # Deliberate abrupt exits in the fixtures below.
    return observed


def abstract_shell_lines(source: str) -> set[int]:
    return {
        item.location.line
        for item in Analyzer(source, "owned-fixture.py").run(parse(source)).diagnostics
        if item.rule_id == "PT001"
    }


RISK_CASES = [
    (
        "expression-prefix-exception",
        'import os\nrun=print\ntry:\n values=((run:=os.system), int("invalid"), (run:=print))\nexcept ValueError:\n run(input())\n',
        None,
    ),
    (
        "raise-expression-prefix",
        'import os\nrun=print\ntry:\n raise ValueError((run:=os.system), int("invalid"), (run:=print))\nexcept ValueError:\n run(input())\n',
        None,
    ),
    (
        "raise-cause-prefix",
        'import os\nrun=print\ntry:\n raise ValueError() from ((run:=os.system), int("invalid"), (run:=print))[0]\nexcept ValueError:\n run(input())\n',
        None,
    ),
    (
        "raise-prefix-finally",
        'import os\nrun=print\ntry:\n raise ValueError((run:=os.system), int("invalid"), (run:=print))\nfinally:\n run(input())\n',
        None,
    ),
    (
        "return-expression-prefix",
        'import os\ndef service():\n run=print\n try:\n  return ((run:=os.system), int("invalid"), (run:=print))\n except ValueError:\n  run(input())\n',
        "service",
    ),
    (
        "finally-return",
        "import os\ndef service():\n try:\n  return 0\n finally:\n  os.system(input())\n",
        "service",
    ),
    (
        "finally-raise",
        "import os\ndef service():\n try:\n  raise ValueError()\n finally:\n  os.system(input())\n",
        "service",
    ),
    (
        "finally-break",
        "import os\nfor step in [0]:\n try:\n  break\n finally:\n  os.system(input())\n",
        None,
    ),
    (
        "finally-continue",
        "import os\nfor step in [0]:\n try:\n  continue\n finally:\n  os.system(input())\n",
        None,
    ),
    ("empty-for-alias", "import os\nrun=os.system\nfor run in []:\n pass\nrun(input())\n", None),
    (
        "exception-state",
        "import os\nrun=print\ntry:\n run=os.system\n raise ValueError()\nexcept ValueError:\n run(input())\n",
        None,
    ),
    (
        "nested-finally",
        "import os\nrun=print\ntry:\n try:\n  raise ValueError()\n finally:\n  run=os.system\nexcept ValueError:\n run(input())\n",
        None,
    ),
    ("function-default", "import os\ndef service(value=os.system(input())):\n pass\n", None),
    ("class-suite", "class C:\n import os\n os.system(input())\n", None),
    (
        "dictionary-order",
        'import os\nx="safe"\nd={(x:=input()):(x:="safe"), (x:=input()):0}\nos.system(x)\n',
        None,
    ),
    (
        "comparison-short-circuit",
        'import os\nx=input()\nresult = 0 > 1 < (x:="safe")\nos.system(x)\n',
        None,
    ),
    (
        "guard-fallthrough",
        "import os\nrun=print\nmatch 1:\n case 1 if (run:=os.system) and False:\n  pass\n case _:\n  run(input())\n",
        None,
    ),
]


@pytest.mark.parametrize("name,source,call", RISK_CASES, ids=[case[0] for case in RISK_CASES])
def test_concrete_source_to_shell_paths_are_not_lost(
    name: str, source: str, call: str | None
) -> None:
    concrete = concrete_shell_lines(source, call=call)
    assert concrete, name  # A trivial zero-execution fixture cannot establish coverage.
    assert concrete <= abstract_shell_lines(source)


@pytest.mark.parametrize(
    "source",
    [
        "import os\ndef service():\n return 0\n os.system(input())\n",
        "import os\ndef service():\n try:\n  return 0\n finally:\n  return 1\n os.system(input())\n",
        "import os\nfor step in [0]:\n break\nelse:\n os.system(input())\n",
        "import os\ndef service():\n os.system(input())\n try:\n  pass\n except ValueError as os:\n  pass\n",
        "import os\ndef service():\n os.system(input())\n match []:\n  case os:\n   pass\n",
        "import os\ndef service():\n os.system(input())\n def nested(value=(os:=None)):\n  pass\n",
    ],
)
def test_dead_paths_and_lexical_unbound_names_do_not_borrow_globals(source: str) -> None:
    assert not concrete_shell_lines(source, call="service" if "def service" in source else None)
    assert not abstract_shell_lines(source)


def test_confidence_comes_from_the_converged_join_not_worklist_order() -> None:
    source = "import os\nif flag:\n run=os.system\nelse:\n x=0\n x=1\n run=unknown\nrun(input())\n"
    items = [
        item
        for item in Analyzer(source, "join.py").run(parse(source)).diagnostics
        if item.rule_id == "PT001"
    ]
    assert len(items) == 1 and items[0].confidence == "uncertain"


@pytest.mark.parametrize(
    "binding",
    [
        "try:\n pass\nexcept ValueError as shadow:\n pass",
        'match value:\n  case {"x": shadow, **remaining}:\n   pass',
        "values=[(shadow:=x) for x in sequence]",
        "def nested(argument=(shadow:=1)):\n  pass",
        "class Nested(base_factory(shadow:=1)):\n  pass",
        "callback=lambda: (internal:=1)",
    ],
)
def test_lexical_binding_prepass_agrees_with_cpython_symbol_table(binding: str) -> None:
    from pp_pytrace.semantics.symbols import Locals, parameters

    source = "def service(value, sequence):\n " + binding.replace("\n", "\n ") + "\n"
    tree = ast.parse(source)
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)
    collected = Locals()
    for statement in function.body:
        collected.visit(statement)
    table = next(
        child
        for child in symtable.symtable(source, "symbols.py", "exec").get_children()
        if child.get_name() == "service" and child.get_type() == "function"
    )
    # CPython exposes inlined-comprehension slots in this table. Its independent
    # bytecode records their saved/restored lifetime; they are not ordinary
    # enclosing bindings. 3.13 lacks the later Symbol.is_comp_iter convenience.
    code = next(
        item
        for item in compile(source, "symbols.py", "exec").co_consts
        if isinstance(item, CodeType) and item.co_name == "service"
    )
    isolated_slots = {
        instruction.argval
        for instruction in dis.get_instructions(code)
        if instruction.opname == "LOAD_FAST_AND_CLEAR"
    }
    expected = {
        symbol.get_name()
        for symbol in table.get_symbols()
        if symbol.is_local() and symbol.get_name() not in isolated_slots
    }
    assert collected.local_bindings | set(parameters(function)) == expected


def test_adding_noop_finally_preserves_all_observable_flows() -> None:
    for first, second in itertools.product([False, True], repeat=2):
        assignment = "input()" if first else '"safe"'
        update = "input()" if second else '"safe"'
        plain = (
            f"import os\ncommand={assignment}\nif flag:\n command={update}\nos.system(command)\n"
        )
        wrapped = (
            "try:\n"
            + "".join(" " + line + "\n" for line in plain.splitlines())
            + "finally:\n pass\n"
        )
        for source in (plain, wrapped):
            concrete = concrete_shell_lines(source, flag=False) | concrete_shell_lines(
                source, flag=True
            )
            assert concrete <= abstract_shell_lines(source)

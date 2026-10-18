from __future__ import annotations

import ast

import pytest

from pp_pytrace.analysis.engine import Analyzer
from pp_pytrace.cfg.blocks import build
from pp_pytrace.frontend.discovery import parse


def findings(source: str) -> list[tuple[str, int, str]]:
    result = Analyzer(source, "service.py").run(parse(source))
    return [
        (item.rule_id, item.location.line, item.confidence)
        for item in result.diagnostics
        if item.rule_id != "PT900"
    ]


@pytest.mark.parametrize(
    ("body", "rules"),
    [
        ("import subprocess as sp\nx=input()\nsp.run(x,shell=True)\n", ["PT001"]),
        ("from subprocess import run as go\nx=input()\ngo(x,shell=True)\n", ["PT001"]),
        ("import subprocess\ngo=subprocess.run\ngo(input(),shell=True)\n", ["PT001"]),
        ('import subprocess\nx=input()\nx="fixed"\nsubprocess.run(x,shell=True)\n', []),
        ('import subprocess\nsubprocess.run(["echo",input()],shell=False)\n', []),
        ("import subprocess\nsubprocess=object()\nsubprocess.run(input(),shell=True)\n", []),
        ("import subprocess\ndef f(subprocess):\n subprocess.run(input(),shell=True)\n", []),
        ("import subprocess\ndef f():\n subprocess.run(input(),shell=True)\n subprocess=0\n", []),
        ("import shlex, subprocess\nx=shlex.quote(input())\nsubprocess.run(x,shell=True)\n", []),
        ('import shlex\nx=shlex.quote(input())\ncursor.execute("SELECT "+x)\n', ["PT002"]),
        ('cursor.execute("SELECT * FROM x WHERE a=?", (input(),))\n', []),
        ('cursor.execute(f"SELECT {input()}", (1,))\n', ["PT002"]),
        ('go=cursor.execute\ngo("SELECT "+input())\n', ["PT002"]),
        ("import time as t\nasync def f():\n t.sleep(1)\n", ["PT003"]),
        ("from time import sleep as nap\nasync def f():\n nap(1)\n", ["PT003"]),
        ("from time import sleep\nasync def f(sleep):\n sleep(1)\n", []),
        ("import time\ndef f():\n time.sleep(1)\n", []),
        ("import subprocess\nx = mysterious()\nsubprocess.run(x,shell=True)\n", ["PT001"]),
        ("import subprocess\nx=input()\nsubprocess.run(x,shell=flag)\n", ["PT001"]),
        ("import os\nos.system(input())\n", ["PT001"]),
    ],
)
def test_semantic_cases(body: str, rules: list[str]) -> None:
    assert [item[0] for item in findings(body)] == rules


def test_loop_worklist_revisits_prior_sink() -> None:
    source = 'import subprocess\nx="safe"\nwhile flag:\n subprocess.run(x,shell=True)\n x=input()\n'
    result = Analyzer(source, "loop.py").run(parse(source))
    assert [(item.rule_id, item.location.line) for item in result.diagnostics] == [("PT001", 4)]
    assert result.blocks < result.iterations < 100
    assert result.diagnostics[0].evidence[0].line == 5


def test_branch_unknown_and_tainted_alias() -> None:
    source = "import subprocess\nif flag:\n go=subprocess.run\nelse:\n go=unknown\ngo(input(),shell=True)\n"
    assert findings(source) == [("PT001", 6, "uncertain")]


def test_cfg_has_hand_drawn_edges() -> None:
    tree = ast.parse("x=0\nif flag:\n x=1\nelse:\n x=2\nreturn_value=x\n")
    graph = build(tree.body)
    lines = {index: getattr(block.node, "lineno", 0) for index, block in graph.blocks.items()}
    edges = {
        (lines[index], lines[successor])
        for index, block in graph.blocks.items()
        for successor in block.successors
    }
    assert edges == {(1, 2), (2, 3), (2, 5), (3, 6), (5, 6), (6, 0)}


def test_uncertainty_is_visible() -> None:
    source = "def f():\n with unknown() as x:\n  exec(x)\n return [item for item in x]\n"
    result = Analyzer(source, "unknown.py").run(parse(source))
    assert len(result.diagnostics) >= 3
    assert all(item.coverage == "partial" for item in result.diagnostics)
    assert any("Comprehension" in item.message for item in result.diagnostics)


def test_suppression_is_a_comment_not_string_text() -> None:
    source = 'import os\nx=input()\nos.system(x)  # pytrace: ignore[PT001]\nos.system(x + "# pytrace: ignore[PT001]")\n'
    assert findings(source) == [("PT001", 4, "high")]


def test_unicode_multiline_and_stable_identifier() -> None:
    source = "import os\n城市 = input()\n城市; os.system(\n 城市\n)\n"
    first = Analyzer(source, "café.py").run(parse(source))
    second = Analyzer(source, "café.py").run(parse(source))
    item = first.diagnostics[0]
    assert item.location.line == 3 and item.location.column == 5
    assert item.location.end_line == 5 and item.location.end_column == 2
    assert item.identifier == second.diagnostics[0].identifier
    assert item.evidence[0].line == 2


def test_nested_shadowing_is_explicit_boundary() -> None:
    source = "import time\ndef outer():\n time=unknown\n async def inner():\n  time.sleep(1)\n return inner\n"
    result = Analyzer(source, "closure.py").run(parse(source))
    assert not any(item.rule_id == "PT003" for item in result.diagnostics)
    assert any("closures" in item.message for item in result.diagnostics)


def test_configured_bare_source_and_contextual_sql_summary() -> None:
    from pp_pytrace.rules.registry import Config

    config = Config(sources=("user_input",), sql_sanitizers=("safe_sql",))
    source = "import os\nx=user_input()\nos.system(x)\ncursor.execute(safe_sql(x))\n"
    result = Analyzer(source, "configured.py", config).run(parse(source))
    assert [(item.rule_id, item.location.line) for item in result.diagnostics] == [("PT001", 3)]


def test_loop_break_continue_and_exit_join() -> None:
    source = 'import os\ndef service(flag):\n command="safe"\n while flag:\n  if flag == 1:\n   command=input()\n   continue\n  os.system(command)\n  break\n else:\n  os.system("safe")\n os.system(command)\n'
    result = Analyzer(source, "loop-exits.py").run(parse(source))
    risks = [(item.rule_id, item.location.line) for item in result.diagnostics]
    assert risks == [("PT001", 8), ("PT001", 12)]
    assert result.iterations < 200


def test_annotated_augmented_destructured_and_deleted_bindings() -> None:
    source = 'import os\nvalue: str=input()\nvalue += " tail"\n[first, second] = [value, value]\nos.system(first)\ndel first\nos.system(first)\n'
    result = Analyzer(source, "bindings.py").run(parse(source))
    risks = [item for item in result.diagnostics if item.rule_id == "PT001"]
    assert [item.location.line for item in risks] == [5, 7]
    assert all(item.confidence == "uncertain" for item in risks)
    assert risks[0].evidence[0].line == 2


@pytest.mark.parametrize("shell", ["1", "42", "'yes'", "b'yes'", "1j", "..."])
def test_truthy_shell_constants_enable_process_sink(shell: str) -> None:
    source = f"import subprocess\nsubprocess.run(input(), shell={shell})\n"
    assert findings(source) == [("PT001", 2, "high")]


@pytest.mark.parametrize("shell", ["False", "0", "None", "''", "b''", "0j"])
def test_falsey_shell_constants_do_not_enable_process_sink(shell: str) -> None:
    assert not findings(f"import subprocess\nsubprocess.run(input(), shell={shell})\n")


def test_unpacked_process_keywords_can_enable_shell() -> None:
    assert findings("import subprocess\nsubprocess.run(input(), **options)\n") == [
        ("PT001", 2, "uncertain")
    ]
    assert not findings("import subprocess\nsubprocess.run(input(), shell=False, **options)\n")


def test_ambiguous_sanitizer_does_not_clear_taint() -> None:
    source = "import shlex, os\nif flag:\n clean=shlex.quote\nelse:\n clean=str\nos.system(clean(input()))\n"
    assert findings(source) == [("PT001", 6, "uncertain")]


def test_annotation_without_value_does_not_overwrite_binding() -> None:
    assert findings("import os\nx=input()\nx: str\nos.system(x)\n") == [("PT001", 4, "high")]


@pytest.mark.parametrize(
    "call",
    [
        'subprocess.run(x, shell=(x:="safe"))',
        'subprocess.run(args=x, shell=(x:="safe"))',
        'cursor.execute(x, parameters=(x:="safe"))',
        'cursor.execute(query=x, parameters=(x:="safe"))',
    ],
)
def test_sink_arguments_are_evaluated_once_in_order(call: str) -> None:
    source = "import subprocess\nx=input()\n" + call + "\n"
    risks = findings(source)
    assert [item[:2] for item in risks] == [("PT001" if "subprocess" in call else "PT002", 3)]


def test_format_receiver_is_evaluated_before_its_arguments() -> None:
    source = 'import os\nx=input()\ny=x.format(x:="safe")\nos.system(y)\n'
    assert findings(source) == [("PT001", 4, "high")]


@pytest.mark.parametrize(
    "expression",
    [
        '(y:=input()) if flag else (y:="safe")',
        '(y:="safe") if flag else (y:=input())',
        '(y:=input()) or (y:="safe")',
        '(y:=input()) and (y:="safe")',
    ],
)
def test_expression_branches_join_conditional_name_writes(expression: str) -> None:
    source = f"import os\nx={expression}\nos.system(y)\n"
    assert findings(source) == [("PT001", 3, "high")]

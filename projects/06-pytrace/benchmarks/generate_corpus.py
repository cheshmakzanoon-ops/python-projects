"""Materialize 50 reviewed scenario variants; labels are declared at author time.

No analyzer runs here. These local synthetic fixtures are original portfolio data.
Every line is executable example structure or a contextual comment, no LOC padding.
"""

from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = '''"""Labeled synthetic service {number}: {context}; never execute during analysis."""
import subprocess as {process}
import time as {clock}
import shlex
from subprocess import run as launch
from time import sleep as pause


def shell_source():
    """User input must not enter a shell command."""
    user = input("{prompt}")
    command = "echo " + user
    alias = {process}.run
    alias(command, shell=True)  # EXPECT: PT001
    return command


def argv_is_not_shell():
    """Argument-vector execution is outside the shell injection rule."""
    user = input("{prompt}")
    argv = ["echo", user]
    result = launch(argv, shell=False)
    return result


def reassignment_kills_flow():
    """A later constant assignment kills the earlier taint."""
    user = input("{prompt}")
    user = "fixed text"
    command = user
    launch(command, shell=True)
    return command


def branch_join(flag):
    """A may-flow on one reachable branch remains after the join."""
    if flag:
        command = input("{prompt}")
    else:
        command = "echo safe"
    launch(command, shell=True)  # EXPECT: PT001
    return command


def shell_context_sanitizer():
    """Shell quoting discharges shell taint for this configured summary."""
    user = input("{prompt}")
    quoted = shlex.quote(user)
    command = "echo " + quoted
    launch(command, shell=True)
    return command


def interpolated_query(cursor):
    """Interpolating a value is different from binding a SQL parameter."""
    user = input("{prompt}")
    query = "SELECT id FROM people WHERE name = '%s'" % user
    execute = cursor.execute
    execute(query)  # EXPECT: PT002
    return query


def bound_query(cursor):
    """The SQL text is fixed while values travel through the parameter API."""
    user = input("{prompt}")
    query = "SELECT id FROM people WHERE name = ?"
    parameters = (user,)
    cursor.execute(query, parameters)
    return parameters


async def blocking_alias():
    """The imported alias still denotes a synchronous blocking function."""
    duration = 1
    blocking = pause
    blocking(duration)  # EXPECT: PT003
    return duration


async def locally_shadowed():
    """The local binding shadows an imported name throughout its scope."""
    pause = input
    marker = "{context}"
    pause(marker)
    return marker


def loop_fixed_point(flag):
    """Loop-carried taint must reach the sink despite an initial safe value."""
    command = "echo safe"
    while flag:
        launch(command, shell=True)  # EXPECT: PT001
        command = input("{prompt}")
        flag = False
    return command


def sanitizer_context_is_not_global(cursor):
    """Shell quoting is not a SQL sanitizer."""
    user = input("{prompt}")
    quoted = shlex.quote(user)
    query = "SELECT id FROM people WHERE name = " + quoted
    cursor.execute(query)  # EXPECT: PT002
    return query


async def blocking_module():
    """Attribute resolution must retain canonical import provenance."""
    delay = 0.01
    module_alias = {clock}
    module_alias.sleep(delay)  # EXPECT: PT003
    return delay
'''


def generate(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    labels: dict[str, object] = {}
    contexts = [
        "billing",
        "catalog",
        "search",
        "dispatch",
        "support",
        "audit",
        "exports",
        "profiles",
        "reports",
        "inventory",
    ]
    for number in range(50):
        text = TEMPLATE.format(
            number=number,
            context=contexts[number % 10],
            process=["sp", "process", "proc", "child", "runner"][number % 5],
            clock=["tm", "clock", "timer", "wall", "sync_time"][number % 5],
            prompt=["name", "naïve", "城市", "café", "owner 🐍"][number // 10],
        )
        # Reviewed expression/flow variants exercise distinct AST forms, not only names.
        shell_expressions = [
            '"echo " + user',
            'f"echo {user}"',
            '"echo {}".format(user)',
            '"echo %s" % user',
            '" ".join(("echo", user))',
            "user",
            'user + " tail"',
            'f"echo {user!r}"',
            "str(user)",
            '(user if flag else "safe")',
        ]
        sql_expressions = [
            "\"SELECT id FROM people WHERE name = '%s'\" % user",
            'f"SELECT id FROM people WHERE name = {user}"',
            '"SELECT " + user',
            '"SELECT {}".format(user)',
            '" ".join(("SELECT", user))',
            "user",
            'user + " LIMIT 1"',
            'f"SELECT {user!r}"',
            "str(user)",
            '(user if flag else "SELECT 1")',
        ]
        text = text.replace(
            'command = "echo " + user', "command = " + shell_expressions[number % 10]
        )
        text = text.replace(
            "query = \"SELECT id FROM people WHERE name = '%s'\" % user",
            "query = " + sql_expressions[(number // 5 + number) % 10],
        )
        text = text.replace(
            'user = "fixed text"',
            "user = " + ['"fixed text"', '""', "None", "0", "False"][number // 10],
        )
        name = f"service_{number:02d}.py"
        (root / name).write_text(text)
        labels[name] = [
            {"line": line, "rule_id": content.split("# EXPECT: ")[1]}
            for line, content in enumerate(text.splitlines(), 1)
            if "# EXPECT: " in content
        ]
    manifest = {
        "schema_version": 1,
        "provenance": "Original hand-authored semantic scenarios with deterministic contextual/alias/Unicode variants; labels declared independently of implementation",
        "files": labels,
        "lines": sum(len(path.read_text().splitlines()) for path in root.glob("*.py")),
    }
    (root / "labels.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    generate(Path(__file__).parents[1] / "tests/fixtures/labeled")

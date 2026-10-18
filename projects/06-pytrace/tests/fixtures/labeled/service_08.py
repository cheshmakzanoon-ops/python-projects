"""Labeled synthetic service 8: reports; never execute during analysis."""
import subprocess as child
import time as wall
import shlex
from subprocess import run as launch
from time import sleep as pause


def shell_source():
    """User input must not enter a shell command."""
    user = input("name")
    command = str(user)
    alias = child.run
    alias(command, shell=True)  # EXPECT: PT001
    return command


def argv_is_not_shell():
    """Argument-vector execution is outside the shell injection rule."""
    user = input("name")
    argv = ["echo", user]
    result = launch(argv, shell=False)
    return result


def reassignment_kills_flow():
    """A later constant assignment kills the earlier taint."""
    user = input("name")
    user = "fixed text"
    command = user
    launch(command, shell=True)
    return command


def branch_join(flag):
    """A may-flow on one reachable branch remains after the join."""
    if flag:
        command = input("name")
    else:
        command = "echo safe"
    launch(command, shell=True)  # EXPECT: PT001
    return command


def shell_context_sanitizer():
    """Shell quoting discharges shell taint for this configured summary."""
    user = input("name")
    quoted = shlex.quote(user)
    command = "echo " + quoted
    launch(command, shell=True)
    return command


def interpolated_query(cursor):
    """Interpolating a value is different from binding a SQL parameter."""
    user = input("name")
    query = (user if flag else "SELECT 1")
    execute = cursor.execute
    execute(query)  # EXPECT: PT002
    return query


def bound_query(cursor):
    """The SQL text is fixed while values travel through the parameter API."""
    user = input("name")
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
    marker = "reports"
    pause(marker)
    return marker


def loop_fixed_point(flag):
    """Loop-carried taint must reach the sink despite an initial safe value."""
    command = "echo safe"
    while flag:
        launch(command, shell=True)  # EXPECT: PT001
        command = input("name")
        flag = False
    return command


def sanitizer_context_is_not_global(cursor):
    """Shell quoting is not a SQL sanitizer."""
    user = input("name")
    quoted = shlex.quote(user)
    query = "SELECT id FROM people WHERE name = " + quoted
    cursor.execute(query)  # EXPECT: PT002
    return query


async def blocking_module():
    """Attribute resolution must retain canonical import provenance."""
    delay = 0.01
    module_alias = wall
    module_alias.sleep(delay)  # EXPECT: PT003
    return delay

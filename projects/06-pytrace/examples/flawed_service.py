"""Intentionally flawed analysis input: never execute this file."""

import subprocess as process
import time

from pp_pytrace.trusted_api import deliver


async def service(cursor: object) -> object:
    user = input("name")
    process.run("echo " + user, shell=True)
    cursor.execute(f"SELECT name FROM people WHERE name = '{user}'")
    time.sleep(1)
    label = str("ready")
    return deliver(label, timeout=3)

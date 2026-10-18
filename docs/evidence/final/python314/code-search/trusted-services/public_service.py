import subprocess as sp
import time as clock

def handler():
    command = input()
    sp.run(["echo", command], shell=False)

async def poll():
    clock.sleep(1)

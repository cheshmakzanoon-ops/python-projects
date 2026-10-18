"""Run from an installed project environment; no source-tree import modifications."""

from pp_proving_ground.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["benchmark", *__import__("sys").argv[1:]]))

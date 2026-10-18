"""Isolated AST encoder: accepts JSON on stdin, never imports analyzed code."""

from __future__ import annotations

import ast
import json
import sys
from typing import Any


def encode(value: Any) -> Any:
    if isinstance(value, ast.AST):
        return {
            "_type": type(value).__name__,
            **{name: encode(item) for name, item in ast.iter_fields(value)},
            **{
                name: getattr(value, name)
                for name in ("lineno", "col_offset", "end_lineno", "end_col_offset")
                if hasattr(value, name)
            },
        }
    if isinstance(value, list):
        return [encode(item) for item in value]
    if isinstance(value, bytes):
        return {"_constant": "bytes", "hex": value.hex()}
    if isinstance(value, complex):
        return {"_constant": "complex", "real": value.real, "imag": value.imag}
    if value is Ellipsis:
        return {"_constant": "ellipsis"}
    return value


def main() -> None:
    request = json.load(sys.stdin)
    if request["memory_bytes"] < 32 * 1024 * 1024:
        print(
            json.dumps(
                {"error": "parser memory budget below minimum 32 MiB", "line": 1, "column": 1}
            )
        )
        return
    try:
        import resource

        limit = request["memory_bytes"]
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    except ImportError:
        pass
    try:
        tree = ast.parse(request["source"], filename=request["filename"])
        compile(tree, request["filename"], "exec")  # compile only; never eval/exec
        count = sum(1 for _ in ast.walk(tree))
        if count > request["max_nodes"]:
            raise ValueError("AST node limit exceeded")
        print(json.dumps({"tree": encode(tree), "nodes": count}))
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "line": getattr(exc, "lineno", 1) or 1,
                    "column": getattr(exc, "offset", 1) or 1,
                }
            )
        )


if __name__ == "__main__":
    main()

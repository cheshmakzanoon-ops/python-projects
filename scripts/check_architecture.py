"""Enforce source-level project independence without importing application code."""

from __future__ import annotations

import ast
from pathlib import Path

from catalog import ProjectSpec, load_projects

ROOT = Path(__file__).resolve().parents[1]


def import_violations(source: str, package: str, known_packages: set[str]) -> list[tuple[int, str]]:
    """Check explicit imports, literal dynamic imports and import-path mutation.

    This is a development boundary check, not a Python sandbox or a claim that
    arbitrary computed imports can be determined statically.
    """
    tree = ast.parse(source)
    aliases: dict[str, str] = {}
    violations = []

    def forbidden(module: str) -> bool:
        head = module.split(".")[0]
        return (head in known_packages and head != package) or head == "projects"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                head = name.name.split(".")[0]
                aliases[name.asname or head] = name.name if name.asname else head
                if forbidden(name.name):
                    violations.append((node.lineno, f"sibling source import: {name.name}"))
        elif isinstance(node, ast.ImportFrom) and not node.level:
            module = node.module or ""
            for name in node.names:
                aliases[name.asname or name.name] = module + "." + name.name
            if forbidden(module):
                violations.append((node.lineno, f"sibling source import: {module}"))

    def qualified(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return qualified(node.value) + "." + node.attr
        if isinstance(node, (ast.Subscript, ast.Starred)):
            return qualified(node.value)
        return ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function = qualified(node.func)
            if function in {"__import__", "builtins.__import__", "importlib.import_module"}:
                if node.args and isinstance(node.args[0], ast.Constant):
                    value = node.args[0].value
                    if isinstance(value, str) and forbidden(value):
                        violations.append((node.lineno, f"dynamic sibling source import: {value}"))
            if function in {
                "sys.path." + method
                for method in (
                    "insert",
                    "append",
                    "extend",
                    "remove",
                    "pop",
                    "clear",
                    "reverse",
                    "sort",
                    "__setitem__",
                    "__delitem__",
                    "__iadd__",
                    "__imul__",
                )
            }:
                violations.append((node.lineno, "source modules must not mutate sys.path"))
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(qualified(target).startswith("sys.path") for target in targets):
                violations.append((node.lineno, "source modules must not replace sys.path"))
    return sorted(set(violations))


def check_projects(projects: list[ProjectSpec], root: Path = ROOT) -> list[str]:
    known = {project["package"] for project in projects}
    failures = []
    for project in projects:
        source = root / project["directory"] / "src"
        if not source.is_dir():
            failures.append(f"{source.relative_to(root)}: missing production source directory")
            continue
        for path in sorted(source.rglob("*.py")):
            try:
                findings = import_violations(
                    path.read_text(encoding="utf-8"), project["package"], known
                )
            except (OSError, SyntaxError, UnicodeError) as error:
                failures.append(f"{path.relative_to(root)}: cannot inspect source: {error}")
                continue
            failures.extend(
                f"{path.relative_to(root)}:{line}: {message}" for line, message in findings
            )
    return failures


def main() -> int:
    failures = check_projects(load_projects(ROOT))
    for failure in failures:
        print(failure)
    print(f"Project independence: {len(failures)} violations")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())

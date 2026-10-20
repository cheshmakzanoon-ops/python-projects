"""Validate the repository's development contract without importing product code."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import NotRequired, TypedDict, cast

ROOT = Path(__file__).resolve().parents[1]
PROJECT_SLUGS = frozenset(
    {
        "anchor",
        "strata",
        "current",
        "meridian",
        "quarry",
        "pytrace",
        "atlas",
        "proving-ground",
        "routecraft",
        "resonance",
    }
)


class ProjectSpec(TypedDict):
    slug: str
    directory: str
    distribution: str
    package: str
    cli: str
    default_python: str
    required_python_versions: list[str]
    supported_platforms: list[str]
    required_services: list[str]
    status: str
    demo_module: str
    format_arguments: list[str]
    lint_arguments: list[str]
    type_arguments: list[str]
    test_arguments: list[str]
    default_port: NotRequired[int]


def _strings(record: dict[str, object], field: str, *, empty: bool = False) -> list[str]:
    value = record.get(field)
    if (
        not isinstance(value, list)
        or (not value and not empty)
        or any(not isinstance(item, str) or not item or "\x00" in item for item in value)
    ):
        raise ValueError(f"{field} must be a {'possibly empty ' if empty else ''}string list")
    return value


def load_projects(root: Path = ROOT) -> list[ProjectSpec]:
    """Use one validated schema for local execution, CI selection and diagnostics."""
    root = root.resolve()
    with (root / "portfolio.toml").open("rb") as stream:
        raw = tomllib.load(stream)
    if type(raw.get("schema_version")) is not int or raw["schema_version"] != 1:
        raise ValueError("unsupported portfolio schema_version")
    if (
        not isinstance(raw.get("uv_version"), str)
        or re.fullmatch(r"\d+\.\d+\.\d+", raw["uv_version"]) is None
    ):
        raise ValueError("uv_version must be an exact stable version")
    projects = raw.get("projects")
    if not isinstance(projects, list) or any(not isinstance(p, dict) for p in projects):
        raise ValueError("projects must be a list of records")
    slugs = [p.get("slug") for p in projects]
    if len(slugs) != len(PROJECT_SLUGS) or any(not isinstance(s, str) for s in slugs):
        raise ValueError("manifest must declare exactly all ten unique projects")
    if set(slugs) != PROJECT_SLUGS:
        raise ValueError("manifest must declare exactly all ten unique projects")
    directories: set[Path] = set()
    identities: dict[str, set[str]] = {key: set() for key in ("distribution", "package", "cli")}
    ports: set[int] = set()
    for project in projects:
        for field in (
            "slug",
            "directory",
            "distribution",
            "package",
            "cli",
            "status",
            "demo_module",
        ):
            value = project.get(field)
            if not isinstance(value, str) or not value or "\x00" in value:
                raise ValueError(f"{field} must be a nonempty string")
        directory = project["directory"]
        resolved = (root / directory).resolve()
        if not resolved.is_relative_to(root) or resolved == root:
            raise ValueError("project path must be a nonempty path within the repository")
        if resolved in directories:
            raise ValueError("duplicate directory")
        if directory != resolved.relative_to(root).as_posix():
            raise ValueError("project directory must use its canonical repository-relative path")
        if any(resolved.is_relative_to(d) or d.is_relative_to(resolved) for d in directories):
            raise ValueError("project directories must not overlap")
        directories.add(resolved)
        for field, seen in identities.items():
            value = project[field]
            pattern = r"[a-z][a-z0-9_]*" if field == "package" else r"[a-z][a-z0-9-]*"
            if re.fullmatch(pattern, value) is None or value in seen:
                raise ValueError(f"invalid or duplicate {field}")
            seen.add(value)
        if project["demo_module"] != project["package"] + ".cli":
            raise ValueError("demo_module must reference the owning package CLI")
        versions = _strings(project, "required_python_versions")
        if len(set(versions)) != len(versions) or any(
            re.fullmatch(r"3\.\d+\.\d+", version) is None for version in versions
        ):
            raise ValueError("required_python_versions must contain unique exact patch versions")
        if project.get("default_python") not in versions:
            raise ValueError("default_python must be a required interpreter")
        if len({v.rsplit(".", 1)[0] for v in versions}) != len(versions):
            raise ValueError("declare one tested patch version per Python family")
        _strings(project, "supported_platforms")
        _strings(project, "required_services", empty=True)
        for field in ("format_arguments", "lint_arguments", "type_arguments", "test_arguments"):
            _strings(project, field)
        if "default_port" in project:
            port = project["default_port"]
            if type(port) is not int or not 1 <= port <= 65535 or port in ports:
                raise ValueError("default_port must be a unique TCP port")
            ports.add(port)
    return cast(list[ProjectSpec], projects)


def resolve_python(project: ProjectSpec, requested: str | None) -> str:
    """Resolve a documented family selector to the patch actually tested in CI."""
    if requested is None:
        return project["default_python"]
    for version in project["required_python_versions"]:
        if requested in (version, version.rsplit(".", 1)[0]):
            return version
    raise ValueError(f"{project['slug']}: unsupported interpreter {requested!r}")


def checkout_problems(project: ProjectSpec, root: Path = ROOT) -> list[str]:
    """Check declarations against packaging; presence does not establish test success."""
    directory = root / project["directory"]
    problems = []
    for name in (
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        f"src/{project['package']}/__init__.py",
    ):
        if not (directory / name).is_file():
            problems.append(f"missing {name}")
    if problems:
        return problems
    if (directory / ".python-version").read_text().strip() != project["default_python"]:
        problems.append("interpreter pin differs from default_python")
    with (directory / "pyproject.toml").open("rb") as stream:
        package = tomllib.load(stream).get("project", {})
    if package.get("name") != project["distribution"]:
        problems.append("distribution differs from pyproject.toml")
    target = package.get("scripts", {}).get(project["cli"], "")
    if not isinstance(target, str) or not target.startswith(project["demo_module"] + ":"):
        problems.append("console entry point differs from demo_module")
    return problems

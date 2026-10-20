import json
import math
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pp_anchor import Definition, Step
from pp_anchor.cli import app, clean_demo, database_url, drop_schema, output_directory
from pp_anchor.definitions.model import canonical


@pytest.mark.parametrize("value", [{"text": "\x00"}, {"text": "\ud800"}, {"\udc00": "key"}])
def test_canonical_rejects_text_not_representable_in_postgresql(value):
    with pytest.raises(ValueError):
        canonical(value)


def test_canonical_rejects_deep_and_cyclic_values_without_recursion_error():
    nested = []
    current = nested
    for _ in range(100):
        child = []
        current.append(child)
        current = child
    with pytest.raises(ValueError, match="nesting"):
        canonical(nested)
    cycle = []
    cycle.append(cycle)
    with pytest.raises(ValueError, match="nesting"):
        canonical(cycle)


def test_canonical_preserves_valid_unicode_and_shared_container_references():
    shared = {"text": "Montréal 🏦"}
    assert canonical([shared, shared]) == canonical([shared, dict(shared)])


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "../escape"},
        {"name": ""},
        {"activity": ""},
        {"after": ["a"]},
        {"after": ("a", "a")},
        {"compensate": ""},
        {"kind": "unknown"},
        {"kind": "signal"},
        {"signal": "x" * 101},
        {"max_attempts": 0},
        {"max_attempts": True},
        {"max_attempts": 33},
        {"delay": math.nan},
        {"delay": -1},
        {"retry_delay": math.inf},
        {"delay": "soon"},
        {"delay": True},
        {"delay": 10**1000},
    ],
)
def test_invalid_step_inputs(changes):
    with pytest.raises(ValueError):
        Step(**{"name": "x", **changes})


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"name": "x", "version": 1, "steps": "bad"},
        {"name": "x", "version": 1, "steps": [1]},
        {"name": "x", "version": 1, "steps": [{"name": "a", "after": "bad"}]},
        {"name": "x", "version": 1, "steps": [{"name": "a", "unknown": 1}]},
        {"name": 1, "version": 1, "steps": [{"name": "a"}]},
        {"name": "x", "version": True, "steps": [{"name": "a"}]},
    ],
)
def test_invalid_definition_json(data):
    with pytest.raises(ValueError):
        Definition.from_dict(data)


@pytest.mark.parametrize(
    "name,version,steps",
    [
        ("", 1, (Step("a"),)),
        ("x", 0, (Step("a"),)),
        ("x", 2_147_483_648, (Step("a"),)),
        ("x", 1, ()),
        ("x", 1, tuple(Step(str(i)) for i in range(1001))),
    ],
)
def test_definition_runtime_limits(name, version, steps):
    with pytest.raises(ValueError):
        Definition(name, version, steps)


def test_finite_json_and_missing_url(monkeypatch):
    with pytest.raises(ValueError):
        canonical({"nan": float("nan")})
    with pytest.raises(ValueError):
        canonical({"bytes": b"bad"})
    monkeypatch.delenv("ANCHOR_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(Exception, match="ANCHOR_DATABASE_URL"):
        database_url()


def test_owned_output_refuses_unknown_symlink_and_traversal(tmp_path):
    with pytest.raises(ValueError):
        output_directory(Path("relative"))
    with pytest.raises(ValueError):
        output_directory(Path("/"))
    target = tmp_path / "target"
    target.mkdir()
    (target / "unrelated").write_text("preserve")
    with pytest.raises(ValueError):
        output_directory(target)
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError):
        output_directory(link / "child")
    with pytest.raises(ValueError):
        clean_demo(target)
    marker = target / ".anchor-owned.json"
    marker.write_text(
        json.dumps(
            {"schema_version": 1, "schema": "anchor_demo_" + "a" * 20, "output": str(target)}
        )
    )
    with pytest.raises(ValueError, match="Unknown files"):
        clean_demo(target)
    assert (target / "unrelated").read_text() == "preserve"
    marker.write_text(json.dumps({"schema_version": 1, "schema": "anchor", "output": "/different"}))
    with pytest.raises(ValueError, match="marker"):
        clean_demo(target)
    with pytest.raises(ValueError, match="namespace"):
        drop_schema("not-a-dsn", "anchor")
    with pytest.raises(ValueError):
        clean_demo(Path("relative"))
    with pytest.raises(ValueError):
        clean_demo(link)


def test_cli_help_is_available():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0 and "benchmark" in result.stdout and "demo" in result.stdout

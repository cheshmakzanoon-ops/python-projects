"""Behavioral comparison of explicitly owned, non-security fixture programs."""

from __future__ import annotations

import asyncio

import pytest

from pp_pytrace.codemods.transforms import rewrite


@pytest.mark.parametrize(
    "literal",
    [
        '"plain"',
        '"naïve 城市"',
        'r"line\\n"',
        'u"typed text"',
        "'''multiline\ntext'''",
        '"quote\\"slash\\\\"',
    ],
)
def test_literal_transform_preserves_computed_values_and_docstrings(literal: str) -> None:
    source = f"""str("module expression, not a docstring")
class Example:
 str("class expression, not a docstring")
 def method(self):
  str("function expression, not a docstring")
  return str({literal})
async def async_value():
 str("async expression, not a docstring")
 return str({literal})
result = (Example().method(), str({literal}))
"""
    changed = rewrite(source)
    assert changed.changes
    states = []
    for text in (source, changed.after):
        namespace: dict[str, object] = {}
        exec(compile(text, "trusted-literal-fixture.py", "exec"), namespace)
        example = namespace["Example"]
        states.append(
            (
                namespace.get("__doc__"),
                example.__doc__,
                example.method.__doc__,
                namespace["result"],
                asyncio.run(namespace["async_value"]()),
            )
        )
    assert states[0] == states[1]
    assert rewrite(changed.after).after == changed.after


@pytest.mark.parametrize("value", ["0", "9", "-1", '"invalid"', "None", "True"])
def test_api_migration_preserves_evaluation_order_results_and_errors(value: str) -> None:
    source = f"""from pp_pytrace.trusted_api import deliver as send
calls=[]
def observe(name, value):
 calls.append(name)
 return value
try:
 result=("ok", send(observe("payload", "message"), timeout=observe("deadline", {value})))
except (ValueError, TypeError) as error:
 result=(type(error).__name__, str(error))
"""
    changed = rewrite(source)
    assert "deadline=observe" in changed.after
    outputs = []
    for text in (source, changed.after):
        namespace: dict[str, object] = {}
        exec(compile(text, "trusted-api-fixture.py", "exec"), namespace)
        outputs.append((namespace["result"], namespace["calls"]))
    assert outputs[0] == outputs[1]
    assert outputs[0][1] == ["payload", "deadline"]
    assert rewrite(changed.after).after == changed.after

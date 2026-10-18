from __future__ import annotations

from dataclasses import replace

import pytest

from pp_pytrace.codemods.transforms import MigrationManifest, rewrite


@pytest.mark.parametrize(
    "source",
    [
        'str("docstring")\n',
        'class C:\n str("docstring")\n',
        'def f():\n (str("docstring"))\n',
        'async def f():\n str("docstring")\n',
        'str=other\nx=str("value")\n',
        'def f(str):\n x=str("value")\n',
        'x=str(b"bytes")\n',
        'x=str(f"format")\n',
        "x=str(*args)\n",
        'x=str(value="hello")\n',
        'x=str("hello", "ascii")\n',
        'x=str(\n # preserve me\n "hello"\n)\n',
    ],
)
def test_literal_abstentions(source: str) -> None:
    result = rewrite(source)
    assert result.after == source
    assert result.abstentions


def test_literal_preserves_comments_crlf_and_idempotence() -> None:
    source = '# header\r\nx = (str("hello"))  # trailing\r\n'
    expected = '# header\r\nx = ("hello")  # trailing\r\n'
    first = rewrite(source)
    assert first.after == expected
    assert rewrite(first.after).after == expected


@pytest.mark.parametrize(
    "call",
    [
        'send("x", timeout=1, deadline=2)',
        'send("x", timeout=1, **kwargs)',
        "send(*args, timeout=1)",
        'send("x", deadline=1)',
    ],
)
def test_api_abstains_on_unsafe_preconditions(call: str) -> None:
    source = "from pp_pytrace.trusted_api import deliver as send\nresult=" + call + "\n"
    assert rewrite(source).after == source


def test_api_preserves_argument_expression_and_comment() -> None:
    source = 'from pp_pytrace.trusted_api import deliver as send\nresult=send("x", timeout = expensive()) # comment\n'
    changed = rewrite(source)
    assert changed.after == source.replace("timeout =", "deadline =")
    assert rewrite(changed.after).after == changed.after


def test_api_conflicting_import_bindings_abstain() -> None:
    source = 'if flag:\n from pp_pytrace.trusted_api import deliver as send\nelse:\n from another import deliver as send\nx=send("x", timeout=2)\n'
    assert rewrite(source).after == source


def test_untrusted_manifest_is_refused() -> None:
    with pytest.raises(ValueError, match="manifest"):
        rewrite('x=str("x")\n', replace(MigrationManifest.trusted(), api_sha256="0" * 64))


def test_nested_literal_constructors_reach_idempotence_in_one_pass() -> None:
    source = 'x=str(str(str("text")))\n'
    first = rewrite(source)
    assert first.after == 'x="text"\n'
    assert len(first.changes) == 3
    assert not rewrite(first.after).changes
    protected = rewrite('str(str("docstring hazard"))\n')
    assert protected.after == 'str("docstring hazard")\n'
    assert rewrite(protected.after).after == protected.after

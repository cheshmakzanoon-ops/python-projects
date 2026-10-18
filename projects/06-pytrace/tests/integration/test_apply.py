from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from pp_pytrace.codemods.plan import Edit, Plan, apply, create_plan, recover
from pp_pytrace.trusted_api import deliver


def test_apply_recover_and_stale_hash(tmp_path: Path) -> None:
    source = tmp_path / "service.py"
    before = 'x=str("hello")\r\n'
    source.write_bytes(before.encode())
    plan = create_plan(tmp_path, ["service.py"])
    journal = tmp_path / "journal"
    apply(plan, journal)
    assert source.read_bytes() == b'x="hello"\r\n'
    assert not create_plan(tmp_path, ["service.py"]).edits
    with pytest.raises(ValueError, match="stale"):
        apply(plan, tmp_path / "second-journal")
    recover(journal)
    assert source.read_bytes() == before.encode()
    apply(plan, tmp_path / "third-journal")
    source.write_text("user changed\n")
    with pytest.raises(ValueError, match="externally"):
        recover(tmp_path / "third-journal")


def test_preflight_does_not_partially_modify(tmp_path: Path) -> None:
    for name in ("a.py", "b.py"):
        (tmp_path / name).write_text('x=str("hi")\n')
    plan = create_plan(tmp_path, ["a.py", "b.py"])
    (tmp_path / "b.py").write_text("changed=1\n")
    with pytest.raises(ValueError, match="stale"):
        apply(plan, tmp_path / "journal")
    assert (tmp_path / "a.py").read_text() == 'x=str("hi")\n'
    assert not (tmp_path / "journal").exists()


def test_forged_replacement_and_overlapping_edits(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text('x=str("hi")\n')
    plan = create_plan(tmp_path, ["a.py"])
    duplicate = replace(plan, edits=(plan.edits[0], plan.edits[0]))
    with pytest.raises(ValueError, match="overlapping"):
        apply(duplicate, tmp_path / "journal")
    forged = replace(plan, edits=(replace(plan.edits[0], replacement='x="evil"\n'),))
    with pytest.raises(ValueError, match="conservative"):
        apply(forged, tmp_path / "journal")
    with pytest.raises(ValueError, match="overlapping"):
        create_plan(tmp_path, ["a.py", "a.py"])


@pytest.mark.parametrize(
    "name", ["../escape.py", "/tmp/escape.py", "folder\\escape.py", "C:escape.py", ""]
)
def test_path_traversal(tmp_path: Path, name: str) -> None:
    plan = Plan(str(tmp_path), (Edit(name, "0" * 64, "x=1\n"),))
    with pytest.raises(ValueError, match="path"):
        apply(plan, tmp_path / "journal")


def test_symlink_edit_refused(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text('x=str("hi")\n')
    (tmp_path / "link.py").symlink_to(tmp_path / "a.py")
    with pytest.raises(ValueError, match="symlink"):
        create_plan(tmp_path, ["link.py"])


def test_trusted_api_equivalence_including_errors() -> None:
    # Only our pinned trusted fixture API is executed, never analyzed target code.
    for payload, value in [("x", 0), ("x", 10), ("", 999), ("x", -1), ("x", "bad"), (10, 2)]:
        results = []
        for keyword in ("timeout", "deadline"):
            try:
                results.append(("result", deliver(payload, **{keyword: value})))
            except (TypeError, ValueError) as exc:
                results.append((type(exc).__name__, str(exc)))
        assert results[0] == results[1]

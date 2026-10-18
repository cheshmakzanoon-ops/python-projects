import importlib.util
import subprocess
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "evidence.py"
spec = importlib.util.spec_from_file_location("evidence", MODULE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_source_and_contract_scopes_are_explicit_and_sensitive(tmp_path):
    def put(name, value):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    put("portfolio.toml", "schema_version=1\n")
    put("ruff.toml", "line-length=100\n")
    put("project/src/product.py", "VALUE=1\n")
    put("project/tests/test_product.py", "assert 1 == 1\n")
    put("project/uv.lock", "version=1\n")
    put(".gitignore", ".local/\n__pycache__/\n")
    for args in (
        ("init", "-q"),
        ("config", "user.name", "Test"),
        ("config", "user.email", "test@example.invalid"),
        ("add", "."),
        ("commit", "-qm", "baseline"),
    ):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    project = tmp_path / "project"
    initial = module.capture(project, tmp_path)
    assert not initial["source_dirty"]
    put("project/.local/results.json", "{}")
    put("project/__pycache__/junk.pyc", "junk")
    assert (
        module.capture(project, tmp_path)["source_content_sha256"]
        == initial["source_content_sha256"]
    )
    put("project/tests/test_product.py", "assert 1 == 2\n")
    changed = module.capture(project, tmp_path)
    assert changed["source_content_sha256"] != initial["source_content_sha256"]
    assert changed["source_dirty"]
    put("project/tests/test_product.py", "assert 1 == 1\n")
    put("project/uv.lock", "version=2\n")
    assert module.capture(project, tmp_path)["lockfile_sha256"] != initial["lockfile_sha256"]
    put("ruff.toml", "line-length=88\n")
    assert (
        module.capture(project, tmp_path)["root_contract_sha256"] != initial["root_contract_sha256"]
    )

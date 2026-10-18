"""Guard against accidentally shipping developer fixtures in the wheel."""

from pathlib import Path
import tomllib


def test_wheel_excludes_development_files() -> None:
    project = Path(__file__).resolve().parents[2]
    data = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = data["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["packages"] == ["src/pp_pytrace"]
    assert not wheel.get("force-include")

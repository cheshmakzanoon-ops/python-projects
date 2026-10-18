import json
import subprocess
import sys
from pathlib import Path


def test_cli_demo_and_safe_cleanup(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    command = [sys.executable, "-m", "pp_current.cli"]
    completed = subprocess.run(
        [*command, "demo", "--output", str(output), "--seed", "1729"],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads((output / "report.json").read_text())
    assert report["oracle_matches"] and sum(report["dispositions"].values()) == 10_000
    assert (
        subprocess.run(
            [*command, "clean-demo", "--output", str(output)], capture_output=True, timeout=10
        ).returncode
        == 0
    )
    unowned = tmp_path / "unowned"
    unowned.mkdir()
    (unowned / "keep").write_text("keep")
    assert (
        subprocess.run(
            [*command, "clean-demo", "--output", str(unowned)], capture_output=True, timeout=10
        ).returncode
        != 0
    )
    assert (unowned / "keep").read_text() == "keep"

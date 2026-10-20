"""JUnit outcomes must describe executed tests before a check can establish readiness."""

import pytest
from test_results import read_junit


@pytest.mark.parametrize(
    "cases,expected,ready",
    [
        ('<testcase name="one"/>', (1, 0, 0, 0), True),
        ("<testcase><failure/></testcase>", (0, 1, 0, 0), False),
        ("<testcase><error/></testcase>", (0, 0, 1, 0), False),
        ('<testcase><skipped type="pytest.xfail"/></testcase>', (0, 0, 0, 1), False),
        ("", (0, 0, 0, 0), False),
    ],
)
def test_executed_leaf_cases_determine_readiness(tmp_path, cases, expected, ready):
    report = tmp_path / "results.xml"
    total = sum(expected)
    report.write_text(
        f'<testsuites tests="{total}"><testsuite tests="{total}">{cases}</testsuite></testsuites>'
    )
    results = read_junit(report)
    assert tuple(results.as_dict().values()) == expected
    assert results.ready is ready


@pytest.mark.parametrize("body", ["", "broken", "<results/>", "<testsuite>"])
def test_invalid_report_is_not_a_passing_test_run(tmp_path, body):
    report = tmp_path / "results.xml"
    report.write_text(body)
    with pytest.raises(ValueError):
        read_junit(report)


def test_missing_or_symlink_report_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        read_junit(tmp_path / "missing")
    source = tmp_path / "old.xml"
    source.write_text('<testsuite><testcase name="old"/></testsuite>')
    alias = tmp_path / "new.xml"
    alias.symlink_to(source)
    with pytest.raises(ValueError):
        read_junit(alias)


def test_actual_pytest_collection_and_skip_are_not_ready(tmp_path):
    import subprocess
    import sys

    source = tmp_path / "test_subject.py"
    source.write_text(
        'import pytest\n@pytest.mark.skip(reason="not executed")\ndef test_work(): pass\n'
    )
    for options in ([], ["--collect-only"]):
        report = tmp_path / ("collect.xml" if options else "skip.xml")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                *options,
                str(source),
                "--junitxml",
                str(report),
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert not read_junit(report).ready


def test_incomplete_case_report_is_rejected_even_if_process_succeeded(tmp_path):
    report = tmp_path / "partial.xml"
    report.write_text('<testsuite tests="2"><testcase name="only-one"/></testsuite>')
    with pytest.raises(ValueError, match="summary"):
        read_junit(report)

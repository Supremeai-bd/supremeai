"""Tests for the CI test-failure trend report builder (Gap 8).

`scripts/ci/build_test_failure_trend.py` converts a pytest JUnit XML report
into a machine-readable per-run failure trend report that CI archives as an
evidence artifact. These tests cover parsing, report building, and the CLI
exit-code contract — no network, no live CI required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ci_dir = Path(__file__).resolve().parents[3] / "scripts" / "ci"
sys.path.insert(0, str(_ci_dir))

if not (_ci_dir / "build_test_failure_trend.py").is_file():
    pytest.skip(
        "scripts/ci/build_test_failure_trend.py not found — un-skip once restored.",
        allow_module_level=True,
    )

from build_test_failure_trend import (  # noqa: E402
    build_trend_report,
    main,
    parse_junit,
)

FAILING_JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="10" failures="2" errors="1" skipped="1" passed="6">
    <testcase classname="tests.test_a" name="test_ok" time="0.1"/>
    <testcase classname="tests.test_a" name="test_fail" time="0.1">
      <failure message="AssertionError: boom">full traceback here</failure>
    </testcase>
    <testcase classname="tests.test_b" name="test_err" time="0.1">
      <error message="RuntimeError: kaboom">full traceback here</error>
    </testcase>
    <testcase classname="tests.test_b" name="test_skip" time="0.1">
      <skipped message="not now"/>
    </testcase>
  </testsuite>
</testsuites>
"""

PASSING_JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="3" failures="0" errors="0" skipped="0" passed="3">
    <testcase classname="tests.test_ok" name="test_one" time="0.1"/>
    <testcase classname="tests.test_ok" name="test_two" time="0.1"/>
    <testcase classname="tests.test_ok" name="test_three" time="0.1"/>
  </testsuite>
</testsuites>
"""


def _write_junit(tmp_path: Path, content: str, name: str = "test-results.xml") -> Path:
    junit = tmp_path / name
    junit.write_text(content, encoding="utf-8")
    return junit


def test_parse_junit_extracts_totals_and_failure_list(tmp_path):
    report = parse_junit(_write_junit(tmp_path, FAILING_JUNIT))
    assert report["total"] == 10
    assert report["passed"] == 6
    assert report["failed"] == 2
    assert report["errors"] == 1
    assert report["skipped"] == 1
    assert report["failed_test_count"] == 2
    by_status = {f["status"]: f for f in report["failures"]}
    assert by_status["failed"]["test"] == "tests.test_a::test_fail"
    assert by_status["failed"]["message"] == "AssertionError: boom"
    assert by_status["error"]["test"] == "tests.test_b::test_err"
    assert by_status["error"]["message"] == "RuntimeError: kaboom"


def test_build_trend_report_writes_json_with_run_metadata(tmp_path):
    junit = _write_junit(tmp_path, FAILING_JUNIT)
    out = tmp_path / "reports" / "test-failure-trend.json"
    report = build_trend_report(junit, out, run_id="42", sha="abc1234", branch="main")
    assert report["run_id"] == "42"
    assert report["sha"] == "abc1234"
    assert report["branch"] == "main"
    assert report["timestamp"]  # ISO timestamp present
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk == report  # file content mirrors the returned report


def test_cli_exit_codes(tmp_path):
    junit_fail = _write_junit(tmp_path, FAILING_JUNIT, name="failing.xml")
    junit_pass = _write_junit(tmp_path, PASSING_JUNIT, name="passing.xml")
    out = tmp_path / "trend.json"

    # 0 = green run, 2 = failures found, 1 = missing junit (evidence integrity).
    assert main(["--junit", str(junit_pass), "--out", str(out)]) == 0
    assert main(["--junit", str(junit_fail), "--out", str(out)]) == 2
    assert main(["--junit", str(tmp_path / "missing.xml"), "--out", str(out)]) == 1


def test_cli_writes_report_and_emits_summary_lines(tmp_path, capsys):
    junit = _write_junit(tmp_path, FAILING_JUNIT)
    out = tmp_path / "trend.json"
    main(["--junit", str(junit), "--out", str(out), "--run-id", "7"])
    captured = capsys.readouterr().out
    assert "Test trend:" in captured
    assert "FAILED tests.test_a::test_fail" in captured
    assert json.loads(out.read_text(encoding="utf-8"))["run_id"] == "7"


def test_failure_message_is_first_line_and_truncated(tmp_path):
    junit = _write_junit(
        tmp_path,
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="1" failures="1">
  <testcase classname="t" name="x">
    <failure>line one
line two</failure>
  </testcase>
</testsuite></testsuites>
""",
    )
    report = parse_junit(junit)
    assert report["failures"][0]["message"] == "line one"

#!/usr/bin/env python3
"""Build a per-run test failure trend report from a pytest JUnit XML file.

Gap closure: after every full-suite run on main, CI produces a machine-readable
`test-failure-trend.json` (totals + failure list). Combined with the smart
pipeline summary's `--include-trends` (GitHub API, last runs), this gives the
board an auditable failure trend instead of ad-hoc logs.

Usage:
    python scripts/ci/build_test_failure_trend.py \
        --junit backend/test-results.xml \
        --out ci-reports/test-failure-trend.json \
        --run-id 123 --sha abc123 --branch main
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _first_line(text: str | None, fallback: str) -> str:
    if not text:
        return fallback
    return text.strip().splitlines()[0][:400]


def parse_junit(junit_path: str | Path) -> dict[str, Any]:
    """Parses a pytest JUnit XML report into totals + a failure list."""
    tree = ET.parse(str(junit_path))
    root = tree.getroot()
    total = passed = failed = errors = skipped = 0
    failures: list[dict[str, str]] = []
    for suite in root.iter("testsuite"):
        total += int(suite.get("tests", 0))
        passed += int(suite.get("passed", 0))
        failed += int(suite.get("failures", 0))
        errors += int(suite.get("errors", 0))
        skipped += int(suite.get("skipped", 0))
        for case in suite.iter("testcase"):
            name = case.get("name", "")
            classname = case.get("classname", "")
            fail = case.find("failure")
            if fail is not None:
                failures.append(
                    {
                        "test": f"{classname}::{name}" if classname else name,
                        "status": "failed",
                        "message": _first_line(
                            fail.get("message") or fail.text,
                            "no failure message",
                        ),
                    }
                )
            err = case.find("error")
            if err is not None:
                failures.append(
                    {
                        "test": f"{classname}::{name}" if classname else name,
                        "status": "error",
                        "message": _first_line(
                            err.get("message") or err.text,
                            "no error message",
                        ),
                    }
                )
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "failed_test_count": len(failures),
        "failures": failures,
    }


def build_trend_report(
    junit_path: str | Path,
    out_path: str | Path,
    run_id: str | None = None,
    sha: str | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    """Writes a per-run failure trend report to `out_path`."""
    report = parse_junit(junit_path)
    report.update(
        {
            "run_id": run_id,
            "sha": sha,
            "branch": branch,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", required=True, help="pytest JUnit XML report path")
    parser.add_argument("--out", required=True, help="output JSON path")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sha", default=None)
    parser.add_argument("--branch", default=None)
    args = parser.parse_args(argv)

    if not Path(args.junit).is_file():
        print(f"::error::JUnit report not found: {args.junit}")
        return 1

    report = build_trend_report(
        args.junit, args.out, run_id=args.run_id, sha=args.sha, branch=args.branch
    )
    summary = (
        f"Test trend: {report['total']} total, {report['passed']} passed, "
        f"{report['failed']} failed, {report['errors']} errors, "
        f"{report['skipped']} skipped, {report['failed_test_count']} failed tests"
    )
    print(summary)
    if report["failed_test_count"]:
        for item in report["failures"][:10]:
            print(f"  FAILED {item['test']}: {item['message']}")
    return 0 if report["failed_test_count"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
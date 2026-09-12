#!/usr/bin/env python3
"""Mission-suite pass^k harness — the first honest reliability scoreboard in CI.

বাংলা: MASTER_PLAN-এর B1 battlefield (Verified Reliability) — pass^k মাপে
"একই মিশন k বার চালালে কত শতাংশ সম্ভাবনায় k বারই সফল হয়"। এটি pass@1-এর
চেয়ে অনেক বেশি কঠোর: demo-ভিত্তিক মডেলরা pass@1-এ ঝলমল করে, কিন্তু
inconsistent হলে pass^k-তে ধসে পড়ে।

কাজ করার নিয়ম:
  * backend/tests/missions স্যুটকে k বার (ডিফল্ট 3) চালায়;
  * প্রতি রানের JUnit XML থেকে total/passed গোনা হয়;
  * pass^k = C(successes, k) / C(n, k) (unbiased estimator, core/self_benchmark.py
    এর সাথে একই গণিত);
  * reports/mission_passk.json-এ ফলাফল লেখে (CI artifact) এবং কনসোলে ছাপে।

Exit code: 0 = হারনেস চলেছে (pass^k যাই হোক); 2 = স্যুট কালেক্ট-ই হয়নি
(ব্রোকেন হারনেস — অবশ্যই ঠিক করতে হবে)। Gate decision এখন মানুষের হাতে;
Phase 2-তে এটি promotion gate হবে।
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
REPORT_DIR = REPO_ROOT / "reports"
MISSION_DIR = "tests/missions"


def run_mission_suite(run_index: int) -> tuple[int, int]:
    """Runs the mission suite once; returns (passed, total)."""
    junit = BACKEND_DIR / f"mission_junit_{run_index}.xml"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            MISSION_DIR,
            "-q",
            "--junitxml",
            str(junit),
            "-p",
            "no:cacheprovider",
        ],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=900,
    )
    total = passed = 0
    if junit.exists():
        try:
            root = ET.parse(junit).getroot()
            for suite in root.iter("testsuite"):
                suite_total = int(suite.attrib.get("tests", "0"))
                failures = int(suite.attrib.get("failures", "0"))
                errors = int(suite.attrib.get("errors", "0"))
                skipped = int(suite.attrib.get("skipped", "0"))
                total += suite_total
                passed += suite_total - failures - errors - skipped
        except ET.ParseError:
            pass
        finally:
            junit.unlink(missing_ok=True)
    if total == 0:
        print(f"[pass^k] run {run_index}: suite collected 0 tests (exit={proc.returncode})")
        print(proc.stdout[-2000:] if proc.stdout else proc.stderr[-2000:])
        raise SystemExit(2)
    return passed, total


def pass_hat_k(successes: int, n: int, k: int) -> float:
    """Unbiased pass^k estimator — identical math to core/self_benchmark.py."""
    if n < k or successes < k:
        return 0.0
    return math.comb(successes, k) / math.comb(n, k)


def main() -> int:
    parser = argparse.ArgumentParser(description="Mission-suite pass^k harness")
    parser.add_argument("--k", type=int, default=3, help="number of consistency runs (default 3)")
    args = parser.parse_args()

    k = max(1, args.k)
    runs: list[dict[str, object]] = []
    for i in range(1, k + 1):
        passed, total = run_mission_suite(i)
        runs.append({"run": i, "passed": passed, "total": total})
        print(f"[pass^k] run {i}/{k}: {passed}/{total} missions green")

    totals = {r["total"] for r in runs}
    if len(totals) != 1:
        # বাংলা: রান-মাঝে স্যুট সাইজ বদলালে estimator অর্থহীন — সৎভাবে 0.0।
        print("[pass^k] WARNING: total test count changed between runs; treating as unstable")
        score = 0.0
        successes = 0
        n = 0
    else:
        n = runs[0]["total"]
        per_mission_success = [0] * n
        for r in runs:
            for idx in range(int(r["passed"])):
                per_mission_success[idx] += 1
        # স্যুট-লেভেল অ্যাগ্রিগেট: min-run successes দিয়ে conservative estimate
        successes = min(int(r["passed"]) for r in runs)
        score = pass_hat_k(successes, n, k)

    result = {
        "suite": MISSION_DIR,
        "k": k,
        "n": n,
        "successes_min": successes,
        "pass_hat_k": round(score, 4),
        "runs": runs,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / "mission_passk.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[pass^k] pass^{k} = {score:.4f}  (n={n}, successes_min={successes})")
    print(f"[pass^k] report written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

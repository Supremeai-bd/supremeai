#!/usr/bin/env python3
"""Mission-suite pass^k harness — the first honest reliability scoreboard in CI.

বাংলা: MASTER_PLAN-এর B1 battlefield (Verified Reliability) — pass^k মাপে
"একই মিশন k বার চালালে কত শতাংশ সম্ভাবনায় k বারই সফল হয়"। এটি pass@1-এর
চেয়ে অনেক বেশি কঠোর: demo-ভিত্তিক মডেলরা pass@1-এ ঝলমল করে, কিন্তু
inconsistent হলে pass^k-তে ধসে পড়ে।

কাজ করার নিয়ম:
  * core/tests/missions স্যুটকে k বার (ডিফল্ট 3) চালায়;
  * প্রতি রানের JUnit XML থেকে total/passed গোনা হয়;
  * একই test ID সব k রানেই পাস করেছে কি না দেখে empirical pass^k গণনা করে;
  * reports/mission_passk.json-এ ফলাফল লেখে (CI artifact) এবং কনসোলে ছাপে।

Gate mode (L1 Reliability Moat — Constitution #5):
  * `--min-pass-hat-k 0.8` দিলে score threshold-এর নিচে গেলে exit 1 —
    রাতভর nightly run-এ এটিই promotion gate; scoreboard mode-এ (threshold
    ছাড়া) স্কোর যাই হোক exit 0, কারণ তখন এটি শুধু পর্যবেক্ষণযোগ্য মাপকাঠি।

Exit code: 0 = হারনেস চলেছে এবং gate (থাকলে) পাস; 1 = gate ব্যর্থ (স্কোর
threshold-এর নিচে); 2 = স্যুট কালেক্ট-ই হয়নি (ব্রোকেন হারনেস — অবশ্যই ঠিক
করতে হবে)।
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = REPO_ROOT / "core"
REPORT_DIR = REPO_ROOT / "reports"
MISSION_DIR = "tests/missions"


# বাংলা (CI-hang সংশোধন): প্রতি রানের হার্ড বাজেট ১৫০ সেকেন্ড। job-এর timeout-minutes: 10,
# আর k=3 রান — তাই প্রতি রান ১৫০s-এর বেশি হলে গেট পুরো job টাইমআউট খেয়ে ফেলে।
# আগের subprocess.run(timeout=900) বাগ: timeout-এ শুধু pytest ডাইরেক্ট child kill হতো,
# কিন্তু pytest-এর spawn করা grandchild (uvicorn/browser) stdout/stderr pipe ধরে রাখত —
# communicate() তখন চিরকাল আটকে যেত এবং CI জব ২+ ঘণ্টা zombie অবস্থায় ঝুলত (observed
# run 35248503140)। সমাধান: নতুন process session (start_new_session) + timeout-এ পুরো
# process group-কে SIGKILL — সব descendant নিশ্চিতভাবে বন্ধ, pipe EOF নিশ্চিত।
PER_RUN_TIMEOUT_SECONDS = 150
POST_KILL_DRAIN_SECONDS = 30


def run_mission_suite(run_index: int) -> tuple[int, int, frozenset[tuple[str, str]], frozenset[tuple[str, str]]]:
    """Return counts, all test IDs and passing IDs from one JUnit run."""
    junit = CORE_DIR / f"mission_junit_{run_index}.xml"
    # বাংলা: আগের অসমাপ্ত রান থেকে পাওয়া XML যেন নতুন ফল না হয়।
    junit.unlink(missing_ok=True)
    proc = subprocess.Popen(
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
        cwd=CORE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=PER_RUN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=POST_KILL_DRAIN_SECONDS)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        print(
            f"[pass^k] run {run_index}: TIMEOUT after {PER_RUN_TIMEOUT_SECONDS}s — "
            "process group killed (hang-proof guard)",
            file=sys.stderr,
        )
    if timed_out:
        # বাংলা: আংশিক junit হলেও suite সম্পূর্ণ হয়নি — সৎভাবে ব্যর্থ ঘোষণা
        # (exit 2 = ব্রোকেন হারনেস)। কোনো ভুয়া সবুজ নয়।
        junit.unlink(missing_ok=True)
        raise SystemExit(2)
    total = passed = 0
    test_ids: set[tuple[str, str]] = set()
    passed_ids: set[tuple[str, str]] = set()
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
                for case in suite.findall("testcase"):
                    test_id = (case.get("classname", ""), case.get("name", ""))
                    if not all(test_id) or test_id in test_ids:
                        raise ValueError("missing or duplicate test identity")
                    test_ids.add(test_id)
                    if not any(case.find(tag) is not None for tag in ("failure", "error", "skipped")):
                        passed_ids.add(test_id)
        except (ET.ParseError, ValueError) as exc:
            print(f"[pass^k] run {run_index}: invalid JUnit report: {exc}", file=sys.stderr)
            raise SystemExit(2)
        finally:
            junit.unlink(missing_ok=True)
    if proc.returncode not in (0, 1):
        print(f"[pass^k] run {run_index}: pytest infrastructure/collection error (exit={proc.returncode})", file=sys.stderr)
        print((stdout or "")[-2000:] or (stderr or "")[-2000:], file=sys.stderr)
        raise SystemExit(2)
    if total == 0:
        # বাংলা: Popen-এ stdout/stderr ফাইল-অবজেক্ট — communicate() থেকে পাওয়া
        # স্ট্রিং ভেরিয়েবলই ব্যবহার করতে হবে (ফাইল-অবজেক্ট slice করা যায় না)।
        print(
            f"[pass^k] run {run_index}: suite collected 0 tests (exit={proc.returncode})"
        )
        print((stdout or "")[-2000:] or (stderr or "")[-2000:])
        raise SystemExit(2)
    if len(test_ids) != total or len(passed_ids) != passed:
        print(f"[pass^k] run {run_index}: JUnit counts do not match test cases", file=sys.stderr)
        raise SystemExit(2)
    if proc.returncode == 1:
        # বাংলা: ব্যর্থ টেস্টের কারণ গোপন না করে CI লগে রাখি।
        print(stdout or "", end="")
        print(stderr or "", end="", file=sys.stderr)
    return passed, total, frozenset(test_ids), frozenset(passed_ids)


def main() -> int:
    parser = argparse.ArgumentParser(description="Mission-suite pass^k harness")
    parser.add_argument(
        "--k", type=int, default=3, help="number of consistency runs (default 3)"
    )
    parser.add_argument(
        "--min-pass-hat-k",
        type=float,
        default=0.0,
        help="gate threshold; exit 1 when pass^k falls below it (0 = scoreboard only)",
    )
    args = parser.parse_args()

    k = max(1, args.k)
    gate_threshold = max(0.0, min(1.0, args.min_pass_hat_k))
    # বাংলা: অসম্পূর্ণ নতুন রান পুরোনো রিপোর্টকে বৈধ দেখাতে পারবে না।
    (REPORT_DIR / "mission_passk.json").unlink(missing_ok=True)
    runs: list[dict[str, object]] = []
    all_ids = None
    common_passes = None
    for i in range(1, k + 1):
        passed, total, ids, passed_ids = run_mission_suite(i)
        if all_ids is not None and ids != all_ids:
            print("[pass^k] test identities changed between runs; refusing a verdict", file=sys.stderr)
            raise SystemExit(2)
        all_ids = ids
        common_passes = passed_ids if common_passes is None else common_passes & passed_ids
        runs.append({"run": i, "passed": passed, "total": total})
        print(f"[pass^k] run {i}/{k}: {passed}/{total} missions green")

    n = len(all_ids or ())
    successes = len(common_passes or ())
    score = successes / n

    result = {
        "suite": MISSION_DIR,
        "k": k,
        "n": n,
        "successes_all_runs": successes,
        "pass_hat_k": round(score, 4),
        "gate": {
            "threshold": gate_threshold,
            "passed": score >= gate_threshold,
        },
        "runs": runs,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / "mission_passk.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[pass^k] pass^{k} = {score:.4f}  (n={n}, successes_all_runs={successes})")
    print(f"[pass^k] report written to {out}")
    if gate_threshold > 0.0:
        if score < gate_threshold:
            # বাংলা: সৎ ব্যর্থতা — কোনো exit-0 ভুয়া সবুজ নয় (L1 Reliability Moat)।
            print(
                f"[pass^k] GATE FAIL: pass^{k}={score:.4f} < min {gate_threshold:.4f}",
                file=sys.stderr,
            )
            return 1
        print(f"[pass^k] GATE PASS: pass^{k}={score:.4f} >= min {gate_threshold:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

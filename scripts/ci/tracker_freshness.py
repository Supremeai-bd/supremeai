#!/usr/bin/env python3
"""
scripts/ci/tracker_freshness.py — Stale tracker/issue freshness bot (Audit A2).

সমস্যা (2026-11-26 ডিপ অডিট):
  - supremeai-public/TASK_LIST বলে server.ts ১১,৭২৫ লাইন → বাস্তব ২,৫২৭ (ভাঙা সত্য)
  - পুরনো ফেইলিউর-রেজিস্টার ইস্যু ৪৫ দিন ধরে বাসি
  - CI ইতিমধ্যে যে কাজ করে ফেলেছে সেই ইস্যু খোলা থেকে যায়

সমাধান — শুধু প্রমাণসহ nudge, auto-close নয় (close করবে owner/মানুষ):
  1) একটা markdown ট্র্যাকার ফাইলে "done-looking" হেডিং (✅/DONE/[x]/"completed")
     আর ফাইলের সাথে অসঙ্গত সংখ্যা-দাবি (যেমন "১১,৭২৫ lines") খোঁজে
  2) ওপেন ইস্যুর ভেতরের দাবি বনাম repo বাস্তবতা (ফাইল আছে কি না) ক্রস-চেক করে
     `stale` লেবেল + প্রমাণসহ একটা কমেন্ট দেয়

Regression-safe: label/comment ONLY। কোনো close/merge/revert নয়।
--dry-run দিলে কোনো write নেই — শুধু রিপোর্ট stdout-এ।

Usage:
  python scripts/ci/tracker_freshness.py --dry-run
  python scripts/ci/tracker_freshness.py --tracker supremeai-public/TASK_LIST_SUPREMEAI_PUBLIC.md
  python scripts/ci/tracker_freshness.py --issues 9,655 --label stale
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# বাংলা মন্তব্য: "done-looking" হেডিং প্যাটার্ন — ট্র্যাকারের হেডিং যদি নিজেই বলে কাজ শেষ
DONE_HEADING = re.compile(
    r"^#{1,4}\s.*\[(x|X)\]|^#{1,4}\s.*(✅|\bDONE\b|\bdone\b|completed)",
)

# বাংলা মন্তব্য: ফাইল-সাইজ দাবি (যেমন "server.ts … 11,725 lines") — বাস্তবতার সাথে মিলবে।
# বাংলা সংখ্যা (০-৯ / U+09E6-09EF) ও বাংলা "লাইন" শব্দও ধরা হয় — TASK_LIST বাংলায় লেখা।
_SIZE_NUM = r"[0-9\u09e6-\u09ef][0-9,\u09e6-\u09ef]{2,}"
SIZE_CLAIM = re.compile(
    r"(?P<file>[\w./\-]+\.(?:py|ts|tsx|js|mjs|sh|yml|yaml))\D{0,60}?"
    r"(?P<num>" + _SIZE_NUM + r")\s*(?:lines|\u09b2\u09be\u0987\u09a8|L\b)",
    re.IGNORECASE,
)

_BN_TRANS = str.maketrans("\u09e6\u09e7\u09e8\u09e9\u09ea\u09eb\u09ec\u09ed\u09ee\u09ef", "0123456789")


def _to_int(num_str: str) -> int:
    """বাংলা/ইংরেজি সংখ্যা স্ট্রিং → int (কমা বাদ)।"""
    return int(num_str.translate(_BN_TRANS).replace(",", ""))


def count_lines(path: Path) -> int | None:
    """ফাইল থাকলে লাইন সংখ্যা দেয়; না থাকলে None — দাবি 'ফাইল নেই' হিসেবে সাজানো হয়।"""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return None


def fetch_remote_tracker(url: str) -> Path:
    """https://github.com/.../blob/main/<path> থেকে raw ফাইল টেম্পে ডাউনলোড করে পাথ দেয়।"""
    # বাংলা মন্তব্য: blob URL → raw.githubusercontent.com-এ রূপান্তর
    raw = url.replace("/blob/", "/raw/", 1)
    import urllib.request

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    req = urllib.request.Request(raw)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = urllib.request.urlopen(req, timeout=30).read()
    tmp = Path(os.environ.get("RUNNER_TEMP", ".")) / "_tracker_freshness_remote.md"
    tmp.write_bytes(data)
    return tmp


def scan_tracker(tracker: Path) -> list[dict[str, object]]:
    """ট্র্যাকার md-তে done-looking হেডিং + ভুল size-দাবি খোঁজে।"""
    findings: list[dict[str, object]] = []
    if not tracker.is_file():
        findings.append({
            "kind": "tracker-missing",
            "detail": f"{tracker} পাওয়া যায়নি —িজেই stale/মুছে গেছে",
        })
        return findings

    text = tracker.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        if DONE_HEADING.match(line):
            findings.append({"kind": "done-heading", "line": i, "detail": line.strip()[:160]})

    for m in SIZE_CLAIM.finditer(text):
        claimed = _to_int(m.group("num"))
        target = tracker.parent / m.group("file")
        if not target.is_file():
            # বাংলা মন্তব্য: repo-root-relative ট্রাই
            target = REPO_ROOT / m.group("file")
        if not target.is_file():
            findings.append({
                "kind": "file-missing",
                "file": m.group("file"),
                "claimed": claimed,
                "actual": None,
                "detail": f"ট্র্যাকার দাবি {m.group('file')}={claimed}L, কিন্তু ফাইল রিপোতে নেই",
            })
            continue
        actual = count_lines(target)
        # ২০% বা বেশি ড্রিফট = stale দাবি
        if actual is not None and abs(actual - claimed) / max(actual, 1) > 0.20:
            findings.append({
                "kind": "size-drift",
                "file": m.group("file"),
                "claimed": claimed,
                "actual": actual,
                "detail": f"ট্র্যাকার দাবি {m.group('file')}={claimed}L, বাস্তব {actual}L (>20% ড্রিফট)",
            })
    return findings


def _gh(args: list[str]) -> str:
    env = dict(os.environ)
    token = env.get("GH_TOKEN") or env.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN নেই — gh auth login করো বা GH_TOKEN সেট করো")
    out = subprocess.check_output(
        ["gh", *args], text=True, stderr=subprocess.STDOUT, env=env, timeout=60
    )
    return out


def propose_issue_stale(
    issue: int, reason: str, label: str, dry_run: bool
) -> dict[str, object]:
    """ইস্যুতে `stale` লেবেল + প্রমাণসহ কমেন্ট — close নয়।"""
    actions: list[str] = []
    if dry_run:
        actions.append(f"[dry-run] label '{label}' + comment দেওয়া হবে issue #{issue}")
    else:
        try:
            _gh(["issue", "edit", str(issue), "--add-label", label])
            actions.append(f"label '{label}' added")
        except Exception as exc:  # noqa: BLE001 — লেবেল না হলেও কমেন্ট চলবে
            actions.append(f"label fail (non-blocking): {exc}")
        try:
            _gh(["issue", "comment", str(issue), "--body", reason[:4000]])
            actions.append("comment posted")
        except Exception as exc:  # noqa: BLE001
            actions.append(f"comment fail (non-blocking): {exc}")
    return {"issue": issue, "actions": actions}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stale tracker/issue freshness bot — label/comment only, no auto-close"
    )
    parser.add_argument(
        "--tracker", default="https://github.com/Supremeai-bd/supremeai-public/blob/main/TASK_LIST_SUPREMEAI_PUBLIC.md",
        help="md ট্র্যাকার পাথ (repo-relative) অথবা https:// ইউআরএল",
    )
    parser.add_argument(
        "--issues", default="", help="কমা-separated ওপেন ইস্যু নম্বর, যেগুলোতে nudge দেওয়া হবে",
    )
    parser.add_argument("--label", default="stale", help="যে লেবেল লাগানো হবে")
    parser.add_argument("--dry-run", action="store_true", help="কোনো write নয় — শুধু রিপোর্ট")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    report: dict[str, object] = {"tracker": args.tracker, "findings": [], "issues": []}

    tracker = Path(args.tracker)
    if not tracker.is_absolute() and not tracker.is_file() and args.tracker.startswith("http"):
        tracker = fetch_remote_tracker(args.tracker)
        report["tracker_source"] = "remote"
    elif not tracker.is_absolute():
        tracker = REPO_ROOT / args.tracker
    report["findings"] = scan_tracker(tracker)

    for raw in filter(None, (s.strip() for s in args.issues.split(","))):
        if not raw.isdigit():
            continue
        n = int(raw)
        reason = (
            f"🤖 **Stale-check nudge (tracker_freshness.py, label-only — close করবে owner):**\n\n"
            f"এই ইস্যুর বর্ণিত কাজ ইতিমধ্যে CI/main-এ বাস্তবায়িত হতে পারে। "
            f"প্রমাণ যাচাই করে ঠিক থাকলে owner-এর অনুমোদনে close করুন (`state_reason: completed`); "
            f"বাস্তবায়িত না হলে এই নudge উপেক্ষা করুন এবং scope আপডেট করুন।\n\n"
            f"- Tracking doc: `{args.tracker}`\n"
            f"- Policy: label/comment only, কোনো auto-close নয়।"
        )
        report["issues"].append(propose_issue_stale(n, reason, args.label, args.dry_run))

    print(json.dumps(report, indent=2, ensure_ascii=False))

    # বাংলা মন্তব্য: findings আছে = ট্র্যাকার বাসি — কিন্তু এটা কখনো CI gate fail করবে না
    # (informational, exit 0 — audit A2-এর "fail-open" নীতি)।
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""AGENTS.md + AGENT_RULES.md validator — verifies the 2-file constitution model.

# বাংলা মন্তব্য: সংবিধান এখন ২ ফাইলের মডেল —
#   AGENTS.md      = মাত্র ২টি Major Rule (কর্তৃত্ব ও স্টেটলেস-লাইফসাইকেল)
#   AGENT_RULES.md = একক রুল-ফাইল (বাকি সব রুলের একমাত্র ঘর)
# এই স্ক্রিপ্ট নিশ্চিত করে দুই ফাইলই বিদ্যমান এবং মৌলিক ধারাগুলো অক্ষত আছে।
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_PATH = REPO_ROOT / "AGENTS.md"
RULES_PATH = REPO_ROOT / "AGENT_RULES.md"

# বাংলা মন্তব্য (#3095-রির্স্ট্রাকচার-অনুসরণ): স্টেবল মার্কার — নতুন canonical কাঠামো।
# পুরনো মার্কার (Major Rule 1/2, ভাগ ১-৫, রোল: coder) #3095-এ অবসর গেছে; মার্কার-
# তালিকা আপডেট না হওয়ায় রির্স্ট্রাকচারের পর প্রতিটি PR নীরবে constitution-gate-এ
# ব্লক হচ্ছিল (main নিজে সবুজ — গেট শুধু PR-এ চলে)। নতুন মার্কার = নতুন সংবিধানের
# অখণ্ডতা-চুক্তি: কর্তৃত্ব-নিয়ম, স্টেটলেস-লাইফসাইকেল, রুল-ফাইল রেফারেন্স +
# ইউনিভার্সাল চুক্তি, রোল-চুক্তি, ইস্যু-সৃষ্টি পলিসি, গ্রুপ/প্রায়োরিটি/সিকোয়েন্স,
# অ্যাডমিন-সিদ্ধান্ত, স্ট্যান্ডার্ড টাস্ক-কন্ট্র্যাক্ট, কোডার-রোল।
AGENTS_REQUIRED_MARKERS = [
    "First Rule: Authority",
    "Second Rule: Stateless Task Lifecycle",
    "AGENT_RULES.md",
]
RULES_REQUIRED_MARKERS = [
    "U1 — Scope",
    "Role Policy Contracts",
    "Issue Creation Policy",
    "Group / Priority / Sequence",
    "Admin Decision Policy",
    "Standard Task Contract",
    "## Coder",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify 2-file constitution model")
    parser.add_argument("--check", action="store_true", help="verify constitution integrity")
    _ = parser.parse_args()

    ok = True

    # বাংলা মন্তব্য: AGENTS.md — ২ Major Rule + রুল-ফাইল রেফারেন্স যাচাই
    if not AGENTS_PATH.exists() or AGENTS_PATH.stat().st_size == 0:
        print("[FAILED] AGENTS.md is missing or empty", file=sys.stderr)
        ok = False
    else:
        content = AGENTS_PATH.read_text(encoding="utf-8")
        missing = [m for m in AGENTS_REQUIRED_MARKERS if m not in content]
        if missing:
            print(f"[FAILED] AGENTS.md missing markers: {missing}", file=sys.stderr)
            ok = False

    # বাংলা মন্তব্য: AGENT_RULES.md — একক রুল-ফাইলের ৫ ভাগ ও রোল-সেকশন যাচাই
    if not RULES_PATH.exists() or RULES_PATH.stat().st_size == 0:
        print("[FAILED] AGENT_RULES.md is missing or empty", file=sys.stderr)
        ok = False
    else:
        rules = RULES_PATH.read_text(encoding="utf-8")
        missing = [m for m in RULES_REQUIRED_MARKERS if m not in rules]
        if missing:
            print(f"[FAILED] AGENT_RULES.md missing markers: {missing}", file=sys.stderr)
            ok = False

    if not ok:
        print("[FAILED] 2-file constitution model is broken", file=sys.stderr)
        return 1

    print("[PASSED] AGENTS.md (authority+stateless rules) + AGENT_RULES.md (canonical policy contracts) are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""AGENTS.md validator — verifies AGENTS.md exists as Single Source of Truth.

# বাংলা মন্তব্য: AGENTS.md এখন স্বয়ংসম্পূর্ণ সংবিধান (Single Source of Truth)।
# এই স্ক্রিপ্ট নিশ্চিত করে যে রুট AGENTS.md বিদ্যমান এবং এতে সংবিধানের মৌলিক ধারাগুলো অক্ষত রয়েছে।
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_PATH = REPO_ROOT / "AGENTS.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify AGENTS.md Single Source of Truth")
    parser.add_argument("--check", action="store_true", help="verify AGENTS.md integrity")
    _ = parser.parse_args()

    if not AGENTS_PATH.exists() or AGENTS_PATH.stat().st_size == 0:
        print("[FAILED] AGENTS.md is missing or empty", file=sys.stderr)
        return 1

    content = AGENTS_PATH.read_text(encoding="utf-8")
    if "Universal Operating Constitution" not in content and "৬টি মৌলিক সার্বজনীন নিয়মাবলী" not in content:
        print("[FAILED] AGENTS.md does not contain required constitutional invariants", file=sys.stderr)
        return 1

    print("[PASSED] AGENTS.md is valid Single Source of Truth constitution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

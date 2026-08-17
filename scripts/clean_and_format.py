#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SupremeAI Codebase Cleaner & Formatter

এই স্ক্রিপ্টটি কোডবেস পরিষ্কার এবং ফরম্যাট করার জন্য একটি সমন্বিত টুল।
এটি নিম্নলিখিত কাজগুলো করে:
1.  প্রজেক্ট ডিরেক্টরি থেকে `__pycache__`, `.pytest_cache`, `.ruff_cache` এর মতো ক্যাশ এবং বিল্ড ফাইল মুছে দেয়।
2.  `ruff` ব্যবহার করে পাইথন কোড ফরম্যাট এবং লিন্ট করে।

ব্যবহার:
python scripts/maintenance/clean_and_format.py
python scripts/maintenance/clean_and_format.py --action clean
python scripts/maintenance/clean_and_format.py --action format
"""

import argparse
import os
import shutil
import subprocess
import sys

# ANSI রঙ (terminal-র জন্য)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def bprint(msg: str, color: str = "") -> None:
    """রঙিন আউটপুটের জন্য প্রিন্ট ফাংশন।"""
    print(f"{color}{msg}{RESET}")


def clean_project(root_dir: str):
    """প্রজেক্ট থেকে অপ্রয়োজনীয় ফাইল ও ডিরেক্টরি মুছে দেয়।"""
    bprint("\n🧹 [ধাপ ১] ক্যাশ এবং অপ্রয়োজনীয় ফাইল মোছা শুরু হচ্ছে...", CYAN)

    patterns_to_remove = [
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "build",
        "dist",
        ".egg-info",
        "node_modules",
        ".next",
        ".vercel",
        ".astro",
        "coverage",
        ".coverage",
    ]

    files_removed_count = 0
    dirs_removed_count = 0

    for root, dirs, files in os.walk(root_dir):
        # ডিরেক্টরি রিমুভ
        for d in list(dirs):
            if d in patterns_to_remove:
                dir_path = os.path.join(root, d)
                try:
                    shutil.rmtree(dir_path)
                    bprint(f"  - ডিরেক্টরি মুছে ফেলা হয়েছে: {dir_path}", YELLOW)
                    dirs_removed_count += 1
                    dirs.remove(d)  # os.walk কে আর এই ডিরেক্টরিতে যেতে হবে না
                except OSError as e:
                    bprint(f"  ❌ '{dir_path}' মুছতে সমস্যা হয়েছে: {e}", RED)

    if dirs_removed_count > 0:
        bprint(f"\n✅ মোট {dirs_removed_count}টি অপ্রয়োজনীয় ডিরেক্টরি মুছে ফেলা হয়েছে।", GREEN)
    else:
        bprint("\n✅ কোনো অপ্রয়োজনীয় ডিরেক্টরি পাওয়া যায়নি।", GREEN)


def format_code(root_dir: str):
    """Ruff ব্যবহার করে কোড ফরম্যাট ও লিন্ট করে।"""
    bprint("\n💅 [ধাপ ২] Ruff দিয়ে কোড ফরম্যাটিং এবং লিন্টিং শুরু হচ্ছে...", CYAN)

    try:
        bprint("  - Ruff Formatter চালানো হচ্ছে...", YELLOW)
        subprocess.run(["ruff", "format", root_dir], check=True, capture_output=True, text=True)

        bprint("  - Ruff Linter (auto-fix) চালানো হচ্ছে...", YELLOW)
        subprocess.run(["ruff", "check", root_dir, "--fix"], check=True, capture_output=True, text=True)

        bprint("\n✅ কোড সফলভাবে ফরম্যাট এবং লিন্ট করা হয়েছে।", GREEN)
    except FileNotFoundError:
        bprint("❌ 'ruff' কমান্ড পাওয়া যায়নি। Ruff ইনস্টল করা আছে কিনা তা নিশ্চিত করুন (`pip install ruff`)", RED)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        bprint(f"❌ ফরম্যাটিং বা লিন্টিং-এ সমস্যা হয়েছে:\n{e.stderr}", RED)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SupremeAI Codebase Cleaner & Formatter.")
    parser.add_argument("--action", choices=["clean", "format", "all"], default="all", help="কোন কাজটি চালাবেন: clean, format, or all (default)")
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    if args.action in ["clean", "all"]:
        clean_project(project_root)

    if args.action in ["format", "all"]:
        format_code(project_root)

    bprint("\n🎉 কাজ সম্পন্ন!", GREEN)

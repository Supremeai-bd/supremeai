#!/usr/bin/env python3
"""
scripts/ci/create_cross_repo_patch.py
Developer & Agent CLI tool to quickly package cross-repo patches into
.patches/public/ or .patches/private/.

Usage:
    # 1. From git diff of recent commit:
    python scripts/ci/create_cross_repo_patch.py --target public --slug update-api-schemas

    # 2. From piped diff:
    git diff HEAD~1 HEAD | python scripts/ci/create_cross_repo_patch.py --target public --slug fix-types

    # 3. From an existing diff file:
    python scripts/ci/create_cross_repo_patch.py --target public --slug sync-docs --diff-file changes.diff
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sanitize_slug(slug: str) -> str:
    """বাংলা মন্তব্য: স্লাগ ফিল্টার করে শুধুমাত্র নিরাপদ আলফানিউমেরিক ও ড্যাশ রাখা।"""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", slug.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "patch"


def main() -> int:
    parser = argparse.ArgumentParser(description="Package git diff into a cross-repo patch file.")
    parser.add_argument(
        "--target",
        type=str,
        default="public",
        choices=["public", "private"],
        help="Target repository channel ('public' for supremeai-public, 'private' for supremeai)",
    )
    parser.add_argument(
        "--slug",
        type=str,
        required=True,
        help="Short slug identifier for the patch filename (e.g. sync-auth-types)",
    )
    parser.add_argument(
        "--diff-file",
        type=str,
        default=None,
        help="Path to an existing .diff or .patch file to copy/import",
    )
    parser.add_argument(
        "--from-staged",
        action="store_true",
        help="Generate diff from git staged changes (git diff --cached)",
    )
    parser.add_argument(
        "--from-head",
        action="store_true",
        help="Generate diff from latest commit (git show HEAD)",
    )
    args = parser.parse_args()

    target_dir = ROOT / ".patches" / args.target
    target_dir.mkdir(parents=True, exist_ok=True)

    slug = sanitize_slug(args.slug)
    patch_filename = f"{slug}.patch"
    out_path = target_dir / patch_filename

    diff_content = ""

    if args.diff_file:
        diff_path = Path(args.diff_file).resolve()
        if not diff_path.exists():
            print(f"Error: Specified diff file does not exist: {diff_path}")
            return 1
        diff_content = diff_path.read_bytes().decode("utf-8")
    elif args.from_staged:
        diff_content = subprocess.check_output(["git", "diff", "--cached"], cwd=ROOT).decode("utf-8")
    elif args.from_head:
        diff_content = subprocess.check_output(["git", "diff", "HEAD~1", "HEAD"], cwd=ROOT).decode("utf-8")
    elif not sys.stdin.isatty():
        diff_content = sys.stdin.buffer.read().decode("utf-8")
    else:
        # Default: try uncommitted changes first, then HEAD
        diff_content = subprocess.check_output(["git", "diff"], cwd=ROOT).decode("utf-8")
        if not diff_content.strip():
            diff_content = subprocess.check_output(["git", "diff", "--cached"], cwd=ROOT).decode("utf-8")

    # বাংলা মন্তব্য: strip/newline normalization করলে CRLF ও শেষ context নষ্ট হয়।
    if not diff_content.strip():
        print("Error: No diff content found. Provide via stdin, --diff-file, --from-staged, or make local changes.")
        return 1

    # Basic header check
    if not any(marker in diff_content for marker in ("diff --git", "--- ", "+++ ", "PATCH")):
        print("Warning: Input does not appear to be a standard unified git diff.")

    out_path.write_bytes((diff_content if diff_content.endswith("\n") else diff_content + "\n").encode("utf-8"))
    print(f"✅ Cross-repo patch created successfully:")
    print(f"   Path: {out_path.relative_to(ROOT)}")
    print(f"   Size: {len(diff_content)} bytes")
    print("\nNext step to commit:")
    print(f"   git add {out_path.relative_to(ROOT)}")
    print(f'   git commit -m "feat(sync): add cross-repo patch for {args.target} ({slug})"')
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
"""
check_free_tier_limits.py
=========================
বাংলা মন্তব্য: pre-commit hook হিসেবে কাজ করে।
প্রতিটি commit-এর আগে বিভিন্ন free-tier পরিবেশের সাইজ লিমিট
চেক করে এবং সীমা অতিক্রম করতে চাইলে সতর্ক করে বা block করে।

Free-tier limits tracked:
  - Render (Free):      ~500MB backend deploy context
  - GitHub Actions:     8GB cache (our soft cap, hard limit 10GB)
  - Vercel (Hobby):     100MB per serverless function bundle
  - Firebase Hosting:   1GB total storage
  - Git Repo:           200MB recommended max (GitHub warning at 5GB)

Usage:
    python scripts/ci/check_free_tier_limits.py
"""

import os
import sys
from pathlib import Path
from typing import NamedTuple

# বাংলা মন্তব্য: Windows-এ emoji print করতে UTF-8 encoding force করা হচ্ছে
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Project root ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent

# ══════════════════════════════════════════════════════════════════════════════
# Free-tier limit definitions
# ══════════════════════════════════════════════════════════════════════════════

MB = 1024 * 1024
GB = 1024 * MB

class SizeLimit(NamedTuple):
    label: str           # Human readable env name
    path: str            # Relative path from root to measure
    warn_bytes: int      # Warn at this size (80%)
    block_bytes: int     # Block commit at this size (95%)
    tip: str             # What to do if exceeded


FREE_TIER_LIMITS: list[SizeLimit] = [
    SizeLimit(
        label="🟠 Render Free (backend deploy context)",
        path="backend",
        warn_bytes=int(400 * MB),    # 400MB → warn (80% of 500MB)
        block_bytes=int(475 * MB),   # 475MB → block (95% of 500MB)
        tip=(
            "Render free tier ~500MB RAM. Remove unused packages from "
            "pyproject.toml, delete large model files, or use .dockerignore "
            "to exclude test/dev assets from the build context."
        ),
    ),
    SizeLimit(
        label="🟡 GitHub Actions cache (CI cache quota)",
        path=".git",
        warn_bytes=int(6 * GB),      # 6GB → warn
        block_bytes=int(8 * GB),     # 8GB → block (our soft cap)
        tip=(
            "GitHub cache approaches our 8GB soft cap. Run "
            "'git gc --aggressive --prune=now' to shrink .git, "
            "or remove large binary/model files from history with git-filter-repo."
        ),
    ),
    SizeLimit(
        label="🔵 Vercel Hobby (frontend bundle per function)",
        path="frontend/dist",
        warn_bytes=int(80 * MB),     # 80MB → warn (80% of 100MB)
        block_bytes=int(95 * MB),    # 95MB → block (95% of 100MB)
        tip=(
            "Vercel hobby limit is 100MB per function. Run 'pnpm build' "
            "and check bundle analyzer output. Use dynamic imports, "
            "tree-shaking, or move large deps to CDN."
        ),
    ),
    SizeLimit(
        label="🟢 Firebase Hosting (static assets)",
        path="frontend/dist",
        warn_bytes=int(800 * MB),    # 800MB → warn (80% of 1GB)
        block_bytes=int(950 * MB),   # 950MB → block (95% of 1GB)
        tip=(
            "Firebase Hosting free tier allows 1GB storage. "
            "Compress images, use WebP format, and remove unused static assets."
        ),
    ),
    SizeLimit(
        label="📦 Git repo size (tracked files, excl. .git)",
        path=".",
        warn_bytes=int(800 * MB),    # 800MB → warn (GitHub সাধারণত 2GB সীমার নিচে থাকা ভালো)
        block_bytes=int(2 * GB),     # 2GB → block
        tip=(
            "Repo working tree is large. Avoid committing binary files, model weights, "
            "or node_modules. Use Git LFS for large assets. "
            "Run: git ls-files | xargs ls -la | sort -k5 -rn | head -20"
        ),
    ),
]

# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

EXCLUDED_DIRS = {
    "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "htmlcov",
    ".git",  # বাংলা: .git আলাদাভাবে check হয়, repo size থেকে বাদ
    ".worktrees", "dist", "build", "target",
}


def get_dir_size(path: Path) -> int:
    """বাংলা মন্তব্য: একটি ডিরেক্টরির মোট সাইজ বাইটে গণনা করে।"""
    total = 0
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size

    for dirpath, dirnames, filenames in os.walk(path):
        # বাংলা মন্তব্য: ভার্চুয়াল এনভায়রনমেন্ট ও cache বাদ দেওয়া হচ্ছে
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for filename in filenames:
            try:
                fp = Path(dirpath) / filename
                total += fp.stat().st_size
            except (OSError, PermissionError):
                pass
    return total


def human_size(size_bytes: int) -> str:
    """বাংলা মন্তব্য: বাইট সংখ্যাকে মানুষের পড়ার যোগ্য ফরম্যাটে রূপান্তর।"""
    if size_bytes >= GB:
        return f"{size_bytes / GB:.2f} GB"
    if size_bytes >= MB:
        return f"{size_bytes / MB:.1f} MB"
    return f"{size_bytes / 1024:.1f} KB"


def progress_bar(current: int, total: int, width: int = 30) -> str:
    """বাংলা মন্তব্য: ASCII progress bar তৈরি করে।"""
    filled = int(width * current / total) if total > 0 else 0
    filled = min(filled, width)
    bar = "█" * filled + "░" * (width - filled)
    pct = min(100.0, 100.0 * current / total) if total > 0 else 0.0
    return f"[{bar}] {pct:.1f}%"


# ══════════════════════════════════════════════════════════════════════════════
# Main scan
# ══════════════════════════════════════════════════════════════════════════════

def run_checks() -> bool:
    """
    বাংলা মন্তব্য: সব free-tier limit চেক করে।
    Returns True if commit should be BLOCKED, False if safe to proceed.
    """
    print("\n📏 SupremeAI Free-Tier Size Guard — Pre-commit Check")
    print("=" * 60)

    any_warn = False
    any_block = False

    for limit in FREE_TIER_LIMITS:
        target = ROOT / limit.path
        if not target.exists():
            # বাংলা মন্তব্য: path না থাকলে skip করা হয় (e.g. dist/ not built yet)
            print(f"\n{limit.label}")
            print(f"  ⏭  Path not found: {limit.path!r} — skipping")
            continue

        size = get_dir_size(target)
        bar = progress_bar(size, limit.block_bytes)

        print(f"\n{limit.label}")
        print(f"  Path : {limit.path}")
        print(f"  Size : {human_size(size)} / {human_size(limit.block_bytes)} limit")
        print(f"  {bar}")

        if size >= limit.block_bytes:
            print(f"  🔴 CRITICAL: Size exceeds {int(100 * limit.block_bytes / limit.block_bytes)}% of free-tier limit!")
            print(f"  💡 Fix: {limit.tip}")
            any_block = True

        elif size >= limit.warn_bytes:
            pct = int(100 * limit.warn_bytes / limit.block_bytes)
            print(f"  🟠 WARNING: Approaching limit ({pct}% threshold reached)")
            print(f"  💡 Tip: {limit.tip}")
            any_warn = True

        else:
            print("  ✅ OK — well within free-tier limit")

    print("\n" + "=" * 60)

    if any_block:
        print("🚫 COMMIT BLOCKED: One or more free-tier size limits exceeded.")
        print("   Fix the issues above before committing.")
        print("   Use --no-verify to bypass (NOT recommended for production).")
        return True  # block

    if any_warn:
        print("⚠️  WARNINGS: Some paths are approaching free-tier limits.")
        print("   Monitor closely — no action required yet.")

    if not any_warn and not any_block:
        print("✅ All free-tier size checks passed!")

    print("")
    return False  # allow commit


if __name__ == "__main__":
    should_block = run_checks()
    sys.exit(1 if should_block else 0)

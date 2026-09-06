#!/usr/bin/env python3
"""
fix_scripts_2.py — one-off codemod: point scripts/ at core.config settings.

Legacy behavior preserved: for every target script, inject the
``from core.config import settings`` bootstrap import (when absent) and
rewrite ``os.getenv(...)`` lookups for BACKEND_URL / DATABASE_URL /
APP_BASE_URL / SUPABASE_URL into ``settings.*`` attribute reads.

SCRIPT-INTELLIGENCE v9: auto-discovers targets via scripts/lib/auto_discovery.py — no hardcoded file inventories.

Target discovery:
  - every ``scripts/ai/*.py`` and ``scripts/billing/*.py`` (discovered globs,
    anchored at the discovered repo root — works from any cwd)
  - legacy seed ``scripts/deploy/update_render.py`` kept as
    discovered-if-exists: absent seeds are skipped with a
    "[discovery] skipping missing ..." note instead of silently rotting the
    fix-mapping table.

Usage:
  python3 scripts/fix_scripts_2.py             # apply codemod (legacy behavior)
  python3 scripts/fix_scripts_2.py --dry-run   # show what would change, write nothing
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# SCRIPT-INTELLIGENCE v9: make the shared discovery lib importable (scripts/ on sys.path)
sys.path.insert(0, str(Path(__file__).resolve().parents[0]))  # -> scripts/
from lib.auto_discovery import existing_paths, get_layout, require  # noqa: E402

# Codemod payload (kept byte-identical to the original one-off script)
IMPORT_STMT = (
    'import sys\nfrom pathlib import Path\n'
    'sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "backend"))\n'
    'from core.config import settings\n'
)

CODEMOD_RULES: list[tuple[str, str]] = [
    (r'os\.getenv\([\s\'"]*BACKEND_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.backend_url'),
    (r'os\.getenv\([\s\'"]*DATABASE_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.database_url'),
    (r'os\.getenv\([\s\'"]*APP_BASE_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.app_base_url'),
    (r'os\.getenv\([\s\'"]*SUPABASE_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.supabase_url'),
]

# Legacy fix-mapping seed (stale on disk) — discovered-if-exists, never fatal.
LEGACY_SEEDS = ("scripts/deploy/update_render.py",)

# Discovered glob dirs (relative to the discovered scripts/ root)
GLOB_DIRS = ("ai", "billing")


def discover_targets() -> list[Path]:
    """Resolve codemod targets via discovery: globs + legacy seeds, filtered.

    বাংলা মন্তব্য: টার্গেট তালিকা ডিসকভারি থেকে আসে — হারানো ফাইল থাকলে নোট দিয়ে
    স্কিপ হয়, ফলে ম্যাপিং টেবিল আর পচে যায় না।
    """
    layout = get_layout()
    scripts_dir = layout.scripts if layout.scripts is not None else layout.root / "scripts"

    candidates: list[Path] = []
    for sub in GLOB_DIRS:
        sub_dir = scripts_dir / sub
        if sub_dir.is_dir():
            candidates.extend(sorted(sub_dir.glob("*.py")))
    for seed in LEGACY_SEEDS:
        candidates.append(layout.root / seed)

    found = existing_paths(candidates)
    found_set = {p.resolve() for p in found}
    for cand in candidates:
        if cand.resolve() not in found_set:
            print(f"[discovery] skipping missing {cand}")
    return found


def apply_codemod(text: str) -> str:
    """Apply the fix rules to one file's content (rules kept intact)."""
    if 'from core.config import settings' not in text:
        # inject
        # find first import
        m = re.search(r'^(import |from )', text, re.MULTILINE)
        if m:
            text = text[:m.start()] + IMPORT_STMT + text[m.start():]

    for pattern, replacement in CODEMOD_RULES:
        text = re.sub(pattern, replacement, text)
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fix_scripts_2.py",
        description="Codemod: rewrite os.getenv(...) config lookups to core.config settings (SCRIPT-INTELLIGENCE v9)",
        epilog="""Target discovery:
  scripts/ai/*.py + scripts/billing/*.py (discovered globs at the discovered repo
  root) plus the legacy seed scripts/deploy/update_render.py, which is
  discovered-if-exists and skipped with a note when absent.

Default (no flags) applies the codemod in place — legacy behavior.
Use --dry-run to preview without writing.
""")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would change per file without writing anything",
    )
    args = parser.parse_args(argv)

    targets = require(discover_targets(), "codemod target scripts")
    mode = "DRY-RUN" if args.dry_run else "APPLY"
    print(f"[discovery] {len(targets)} codemod target(s) resolved — mode: {mode}")

    changed = unchanged = 0
    for p in targets:
        try:
            original = p.read_text("utf-8")
        except OSError as exc:
            print(f"[codemod] unreadable, skipping: {p} ({exc})")
            continue
        updated = apply_codemod(original)
        if updated == original:
            unchanged += 1
            print(f"[codemod] unchanged: {p}")
            continue
        if args.dry_run:
            changed += 1
            print(f"[dry-run] would rewrite: {p}")
        else:
            p.write_text(updated, "utf-8")
            changed += 1
            print(f"[codemod] rewrote: {p}")

    print(f"[codemod] done — {changed} file(s) {'would change' if args.dry_run else 'changed'}, "
          f"{unchanged} unchanged, {len(targets)} target(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

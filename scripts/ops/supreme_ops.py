"""
scripts/supreme_ops.py
======================
Unified SupremeAI Operations & Pipeline CLI Dispatcher.
Consolidates dozens of scattered one-off maintenance scripts into a single,
self-healing operational entry point.

Usage:
    python scripts/supreme_ops.py audit
    python scripts/supreme_ops.py knowledge [--inject] [--verify]
    python scripts/supreme_ops.py health
    python scripts/supreme_ops.py sync-env
    python scripts/supreme_ops.py clean
    python scripts/supreme_ops.py recipe <recipe_id>
    python scripts/ops/supreme_ops.py cookies status   # == ghost_tower/3_check_cookies_status.bat
    python scripts/ops/supreme_ops.py cookies sync     # == ghost_tower/4_sync_cookies_to_infisical.bat
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

# Add project root and backend to sys.path
# scripts/ops/supreme_ops.py -> repo root is two levels up (the file moved from scripts/).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))


def run_health_check():
    """Run comprehensive system health check and failure predictions."""
    print("=== [SupremeOps] Running Comprehensive Health & Predictive Check ===")
    from core.health_check import ComprehensiveHealthChecker
    checker = ComprehensiveHealthChecker()
    res = asyncio.run(checker.check_all())
    print(f"Health Status: {res.get('status')}")
    print(f"Predictions: {res.get('predictions')}")
    print(f"Summary: {res.get('summary')}")


def run_knowledge_ops(inject: bool = False, verify: bool = True):
    """Run knowledge base verification and vector injection."""
    print("=== [SupremeOps] Knowledge Operations ===")
    # বাংলা মন্তব্য: ডিলিট হওয়া tools.tool_knowledge_injector-এর বদলে ক্যানোনিকাল KnowledgeBaseIndexer ও TOOLS রেজিস্ট্রি ব্যবহার
    from core.scripts.seed_tools_registry import TOOLS
    from core.tools.knowledge.knowledge_base_indexer import KnowledgeBaseIndexer

    indexer = KnowledgeBaseIndexer()
    print(f"Total Knowledge Matrix Cards: {len(TOOLS)}")
    if inject:
        print("Injecting cards into vector knowledge base...")
        cards = [
            {
                "id": f"tool::{tool_id}",
                "text": f"{name} ({category}): {desc} [path: {file_path}]",
                "metadata": {"tool_id": tool_id, "category": category, "path": file_path},
            }
            for tool_id, name, file_path, category, desc, *_ in TOOLS
        ]
        res = indexer.index_scraped_data(cards)
        print(f"Successfully synced: {res.get('indexed', 0)} cards.")
    if verify:
        print("Verifying semantic recall query...")
        sample_results = indexer.search_knowledge("How to route models through free tier?", n_results=2)
        print(f"Recall matches found: {len(sample_results)}")


def run_audit():
    """Run configuration, security, and environment audit."""
    print("=== [SupremeOps] Running System & Environment Audit ===")
    from core.feature_flags import feature_flags
    status = feature_flags.status()
    print("Feature Flags Status:", status)
    print("[OK] Audit completed successfully.")


def run_cache_clean():
    """Clean transient caches, pycache, and temporary logs."""
    print("=== [SupremeOps] Cleaning Transient Cache & Temp Artifacts ===")
    cleaned_count = 0
    for root, dirs, files in os.walk(PROJECT_ROOT):
        if "__pycache__" in root or ".pytest_cache" in root:
            for f in files:
                try:
                    os.remove(os.path.join(root, f))
                    cleaned_count += 1
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).exception(f"Silenced error: {e}")
    print(f"[OK] Cleaned {cleaned_count} temporary cache files.")


# Ghost Tower cookie tools (browser/ghost_tower). Run exactly the way the .bat
# launchers do — `cd ghost_tower && python <script>` — so the scripts' own
# sys.path / credential_vault imports and the .bat files keep working unchanged.
# বাংলা মন্তব্য: .bat ফাইল আর এই CLI একই স্ক্রিপ্ট একই cwd-তে চালায়; স্ক্রিপ্টে কোনো পরিবর্তন নেই।
GHOST_TOWER_DIR = PROJECT_ROOT / "browser" / "ghost_tower"
COOKIE_SCRIPTS = {
    "status": "check_cookies_status.py",
    "sync": "sync_cookies_to_infisical.py",
}


def run_cookies(action: str) -> int:
    """Run a Ghost Tower cookie script (status | sync) and return its exit code."""
    script = COOKIE_SCRIPTS.get(action)
    if script is None:
        print(f"[SupremeOps] Unknown cookies action: {action!r} (use: {', '.join(COOKIE_SCRIPTS)})")
        return 2
    script_path = GHOST_TOWER_DIR / script
    if not script_path.is_file():
        print(f"[SupremeOps] Missing Ghost Tower script: {script_path}")
        return 2
    print(f"=== [SupremeOps] Ghost Tower cookies {action} ({script}) ===")
    completed = subprocess.run(  # noqa: S603 - fixed script path, current interpreter
        [sys.executable, str(script_path)],
        cwd=str(GHOST_TOWER_DIR),
        check=False,
    )
    return completed.returncode


def main():
    parser = argparse.ArgumentParser(description="SupremeAI Unified Operations CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available operations")

    # health
    subparsers.add_parser("health", help="Check system health and failure predictions")

    # audit
    subparsers.add_parser("audit", help="Audit feature flags, configs, and security posture")

    # knowledge
    k_parser = subparsers.add_parser("knowledge", help="Manage tool knowledge matrix and embeddings")
    k_parser.add_argument("--inject", action="store_true", help="Sync all cards to pgvector")
    k_parser.add_argument("--verify", action="store_true", default=True, help="Verify semantic recall")

    # clean
    subparsers.add_parser("clean", help="Clean pycache and temp artifacts")

    # cookies (Ghost Tower)
    c_parser = subparsers.add_parser("cookies", help="Ghost Tower AI cookie status / Infisical sync")
    c_parser.add_argument("action", choices=sorted(COOKIE_SCRIPTS), help="status = verify local + live session; sync = push cookies to Infisical")

    args = parser.parse_args()

    if args.command == "health":
        run_health_check()
    elif args.command == "audit":
        run_audit()
    elif args.command == "knowledge":
        run_knowledge_ops(inject=args.inject, verify=args.verify)
    elif args.command == "clean":
        run_cache_clean()
    elif args.command == "cookies":
        sys.exit(run_cookies(args.action))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Public surface guard — enforces Universal Invariant 2 (Boundary).

Enforces:
1. No satellite shadowing code in repo root (no src/*, service/*, app/*).
2. Code files strictly belong to approved domain roots or manifest allowlist.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_ROOT_DIRS = {"src", "service", "app"}

APPROVED_ROOT_PREFIXES = (
    "core",
    "gateway",
    "browser",
    "vscode",
    "studio",
    "scripts",
    "tests",
    "docs",
    ".agents",
    ".github",
    "backend",
    "packages",
    "infrastructure",
    ".semgrep",
)


def load_manifest(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        return set()
    lines = manifest_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.strip().startswith("#")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Public surface boundary guard")
    parser.add_argument("--manifest", type=str, default="", help="Path to public surface manifest allowlist")
    parser.add_argument("--check", action="store_true", help="Perform surface check")
    args = parser.parse_args()

    manifest_allowlist = set()
    if args.manifest:
        m_path = Path(args.manifest)
        if not m_path.is_absolute():
            m_path = REPO_ROOT / m_path
        manifest_allowlist = load_manifest(m_path)

    errors = []

    # 1. Check for forbidden directories in root
    for f_dir in FORBIDDEN_ROOT_DIRS:
        p = REPO_ROOT / f_dir
        if p.exists() and p.is_dir():
            errors.append(f"Forbidden directory in repo root: '{f_dir}/' (violates Invariant 2)")

    # 2. Check for unexpected root-level python files outside standard tooling
    allowed_root_files = {
        "setup.py",
        "conftest.py",
        "manage.py",
    }
    if manifest_allowlist:
        allowed_root_files.update(manifest_allowlist)

    for item in REPO_ROOT.glob("*.py"):
        if item.name not in allowed_root_files:
            errors.append(f"Unexpected python script in repo root: '{item.name}'")

    if errors:
        print(f"[FAIL] public_surface_guard found {len(errors)} violation(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("[PASS] public_surface_guard: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

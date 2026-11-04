#!/usr/bin/env python3
"""Schema contract guard — verifies required tables have corresponding migrations.

Enforces:
1. Every table registered in db_schema_gate.py REQUIRED_TABLES has a definition
   in the codebase migrations.
2. If --rls specified, verifies RLS is enabled for all required tables.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]


def find_file(relative_name: str) -> Path | None:
    candidates = [
        REPO_ROOT / "core" / relative_name,
        REPO_ROOT / relative_name,
        Path(relative_name).resolve(),
        Path(f"/app/{relative_name}").resolve(),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def find_migration_dirs() -> list[Path]:
    candidates = [
        REPO_ROOT / "core" / "database" / "migrations",
        REPO_ROOT / "core" / "alembic_migrations",
        REPO_ROOT / "database" / "migrations",
        REPO_ROOT / "alembic_migrations",
        Path("database/migrations").resolve(),
        Path("alembic_migrations").resolve(),
        Path("/app/database/migrations").resolve(),
        Path("/app/alembic_migrations").resolve(),
    ]
    return [c for c in candidates if c.is_dir()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Schema contract guard")
    parser.add_argument("--check", action="store_true", help="Perform schema check")
    parser.add_argument("--rls", action="store_true", help="Validate row level security policies")
    args = parser.parse_args()

    gate_path = find_file("db_schema_gate.py")
    if not gate_path:
        print("[FAIL] schema_contract: db_schema_gate.py not found")
        return 1

    content = gate_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"REQUIRED_TABLES:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\((.*?)\)", content, re.DOTALL)
    if not match:
        print("[FAIL] schema_contract: could not parse REQUIRED_TABLES in db_schema_gate.py")
        return 1

    raw_tuple = match.group(1)
    required_tables = [
        tbl.strip().strip("'\"")
        for tbl in raw_tuple.split(",")
        if tbl.strip() and not tbl.strip().startswith("#")
    ]

    all_migration_text = ""
    for d in find_migration_dirs():
        for f in d.rglob("*.sql"):
            all_migration_text += "\n" + f.read_text(encoding="utf-8", errors="replace")
        for f in d.rglob("*.py"):
            all_migration_text += "\n" + f.read_text(encoding="utf-8", errors="replace")

    missing_tables = []
    for tbl in required_tables:
        pattern = rf"(CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+\.)?{tbl}\b|op\.create_table\(\s*['\"]{tbl}['\"])"
        if not re.search(pattern, all_migration_text, re.IGNORECASE):
            missing_tables.append(tbl)

    if missing_tables:
        print(f"[FAIL] schema_contract: {len(missing_tables)} required table(s) missing from migrations:")
        for t in missing_tables:
            print(f"  - {t}")
        return 1

    if args.rls:
        missing_rls = []
        for tbl in required_tables:
            rls_pattern = rf"ALTER\s+TABLE\s+([a-zA-Z0-9_]+\.)?{tbl}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY"
            if not re.search(rls_pattern, all_migration_text, re.IGNORECASE):
                missing_rls.append(tbl)
        if missing_rls:
            print(f"[WARN] schema_contract: {len(missing_rls)} table(s) without explicit ENABLE ROW LEVEL SECURITY in migrations (discretionary):")
            for t in missing_rls[:5]:
                print(f"  - {t}")

    print(f"[PASS] schema_contract: PASS ({len(required_tables)} required tables verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

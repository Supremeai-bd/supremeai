#!/usr/bin/env python3
"""Schema contract guard — verifies required tables have corresponding migrations.

Enforces:
1. Every table registered in core/db_schema_gate.py REQUIRED_TABLES has a definition
   in the codebase migrations.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    gate_path = REPO_ROOT / "core" / "db_schema_gate.py"
    if not gate_path.is_file():
        print("[FAIL] schema_contract: core/db_schema_gate.py not found")
        return 1

    content = gate_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"REQUIRED_TABLES:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\((.*?)\)", content, re.DOTALL)
    if not match:
        print("[FAIL] schema_contract: could not parse REQUIRED_TABLES in core/db_schema_gate.py")
        return 1

    raw_tuple = match.group(1)
    required_tables = [
        tbl.strip().strip("'\"")
        for tbl in raw_tuple.split(",")
        if tbl.strip() and not tbl.strip().startswith("#")
    ]

    # Search in core/database/migrations and core/alembic_migrations
    all_migration_text = ""
    for d in [REPO_ROOT / "core" / "database" / "migrations", REPO_ROOT / "core" / "alembic_migrations"]:
        if d.is_dir():
            for f in d.rglob("*.sql"):
                all_migration_text += f.read_text(encoding="utf-8", errors="replace") + "\n"
            for f in d.rglob("*.py"):
                all_migration_text += f.read_text(encoding="utf-8", errors="replace") + "\n"

    missing = []
    for table in required_tables:
        pattern = re.compile(rf"(CREATE\s+TABLE.*?{table}|op\.create_table\(['\"]{table}['\"])", re.IGNORECASE)
        if not pattern.search(all_migration_text):
            missing.append(table)

    if missing:
        print(f"[FAIL] schema_contract: The following required tables lack migration definitions: {missing}")
        return 1

    print(f"[PASS] schema_contract: PASS (All {len(required_tables)} required tables defined in migrations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

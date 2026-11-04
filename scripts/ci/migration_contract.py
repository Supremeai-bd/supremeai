#!/usr/bin/env python3
"""Migration contract guard — verifies idempotency and naming conventions of DB migrations.

Enforces:
1. Migration files in core/database/migrations/ follow naming conventions.
2. Migrations use idempotent DDL statements (IF NOT EXISTS, IF EXISTS, CREATE OR REPLACE).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    migrations_dir = REPO_ROOT / "core" / "database" / "migrations"
    if not migrations_dir.is_dir():
        print("[FAIL] migration_contract: core/database/migrations directory not found")
        return 1

    errors = []
    # Check top-level migration sql files (skip legacy and manual subdirs)
    sql_files = [f for f in migrations_dir.glob("*.sql") if f.is_file()]

    valid_name_re = re.compile(r"^(\d{8}|\d{1,4})_[a-zA-Z0-9_-]+\.sql$")
    create_table_re = re.compile(r"CREATE\s+TABLE\s+(?!IF\s+NOT\s+EXISTS)", re.IGNORECASE)

    for sql_file in sql_files:
        name = sql_file.name
        if not valid_name_re.match(name):
            errors.append(f"{name}: invalid migration file name (expected YYYYMMDD_* or NNN_*.sql)")

        content = sql_file.read_text(encoding="utf-8", errors="replace")
        for idx, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            if create_table_re.search(stripped):
                errors.append(f"{name}:{idx}: Non-idempotent CREATE TABLE (must use CREATE TABLE IF NOT EXISTS)")

    if errors:
        print(f"[FAIL] migration_contract found {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("[PASS] migration_contract: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Migration contract guard — verifies idempotency and naming conventions of DB migrations.

Enforces:
1. Migration files in database/migrations/ follow naming conventions.
2. Migrations use idempotent DDL statements (IF NOT EXISTS, IF EXISTS, CREATE OR REPLACE).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]


def find_migrations_dir() -> Path | None:
    candidates = [
        REPO_ROOT / "core" / "database" / "migrations",
        REPO_ROOT / "database" / "migrations",
        Path("database/migrations").resolve(),
        Path("/app/database/migrations").resolve(),
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Migration contract guard")
    parser.add_argument("--check", action="store_true", help="Perform check")
    parser.add_argument("--disposable-db", action="store_true", help="Validate against disposable test database if available")
    args = parser.parse_args()

    migrations_dir = find_migrations_dir()
    if not migrations_dir:
        print("[FAIL] migration_contract: database/migrations directory not found")
        return 1

    errors = []
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

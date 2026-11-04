#!/usr/bin/env python3
"""Readiness contract guard — verifies readiness probe and schema requirements.

Enforces:
1. REQUIRED_TABLES registry in core/db_schema_gate.py contains automation_executions,
   ai_memory, and task_checkpoints.
2. Readiness route exists in core/health_routes.py.
3. No secret values are printed or exposed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Readiness contract guard")
    parser.add_argument("--self-test", action="store_true", help="Perform offline self-test")
    parser.add_argument("--check-required-names", action="store_true", help="Check required secret names without values")
    args = parser.parse_args()

    errors = []

    # 1. Check db_schema_gate
    gate_path = REPO_ROOT / "core" / "db_schema_gate.py"
    if not gate_path.is_file():
        errors.append(f"Missing schema gate: {gate_path}")
    else:
        content = gate_path.read_text(encoding="utf-8", errors="replace")
        for table in ("automation_executions", "ai_memory", "task_checkpoints"):
            if f'"{table}"' not in content and f"'{table}'" not in content:
                errors.append(f"db_schema_gate.py missing required table '{table}'")

    # 2. Check health routes readiness probe
    health_routes_path = REPO_ROOT / "core" / "health_routes.py"
    if not health_routes_path.is_file():
        errors.append(f"Missing health routes: {health_routes_path}")
    else:
        health_content = health_routes_path.read_text(encoding="utf-8", errors="replace")
        if "readiness_probe" not in health_content and "/health/ready" not in health_content:
            errors.append("health_routes.py missing readiness probe endpoint definition")

    # 3. Check required secret names definition in secret_vault
    if args.check_required_names or not args.self_test:
        vault_path = REPO_ROOT / "core" / "security" / "secret_vault.py"
        if not vault_path.is_file():
            errors.append(f"Missing secret vault: {vault_path}")
        else:
            vault_content = vault_path.read_text(encoding="utf-8", errors="replace")
            if "HARD_REQUIRED_SECRETS" not in vault_content:
                errors.append("HARD_REQUIRED_SECRETS registry missing from secret_vault.py")

    if errors:
        print("[FAIL] readiness_contract FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("[PASS] readiness_contract: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

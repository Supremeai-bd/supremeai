#!/usr/bin/env python3
"""Readiness contract guard — verifies readiness probe and schema requirements.

Enforces:
1. REQUIRED_TABLES registry in core/db_schema_gate.py contains automation_executions,
   ai_memory, and task_checkpoints.
2. Readiness route exists in core/health_routes.py.
3. No secret values are printed or exposed.
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
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

    if errors:
        print("[FAIL] readiness_contract FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("[PASS] readiness_contract: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

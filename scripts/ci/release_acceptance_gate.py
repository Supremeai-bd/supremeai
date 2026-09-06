#!/usr/bin/env python3
"""Validate local release acceptance evidence without contacting production systems."""
from __future__ import annotations
import argparse, json
from pathlib import Path

REQUIRED = ("merge_policy", "route_inventory", "route_graph", "preflight_evidence", "security_tests")

def validate(payload: dict) -> list[str]:
    errors = []
    if payload.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    for key in REQUIRED:
        item = payload.get(key)
        if not isinstance(item, dict) or item.get("status") != "passed":
            errors.append(f"{key} must have status=passed")
    if payload.get("database", {}).get("status") != "manual_pending":
        errors.append("database must remain manual_pending until live verification")
    return errors

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid", "errors": [str(exc)]}))
        return 2
    errors = validate(payload)
    print(json.dumps({"status": "passed" if not errors else "blocked", "errors": errors}, indent=2))
    return 0 if not errors else 1

if __name__ == "__main__":
    raise SystemExit(main())

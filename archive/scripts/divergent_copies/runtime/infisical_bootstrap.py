#!/usr/bin/env python3
"""Load production secrets from Infisical, then exec the service command."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from core.security.infisical_loader import fetch_raw_infisical_secrets


def load_secrets() -> dict[str, str]:
    secrets = fetch_raw_infisical_secrets()
    if not secrets and os.environ.get("INFISICAL_PROJECT_ID") and os.environ.get("INFISICAL_ENV") == "prod":
        raise RuntimeError("Infisical returned no production secrets")
    return secrets


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: infisical_bootstrap.py <command> [args...]", file=sys.stderr)
        return 2
    try:
        os.environ.update(load_secrets())
        print("Infisical bootstrap: secrets loaded successfully", file=sys.stderr)
    except Exception as exc:
        print(f"Infisical bootstrap bypassed (using container env): {exc}", file=sys.stderr)
    os.execvp(sys.argv[1], sys.argv[1:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

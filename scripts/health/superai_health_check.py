#!/usr/bin/env python3
"""B3 thin deprecation wrapper: delegates to canonical scripts/health/check_system_health.py."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    print("[DEPRECATED] Use scripts/health/check_system_health.py", file=sys.stderr)
    canonical = Path(__file__).resolve().with_name("check_system_health.py")
    runpy.run_path(str(canonical), run_name="__main__")

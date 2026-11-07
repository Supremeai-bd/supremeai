"""Gateway re-export of root tests/test_openapi_breaking_guard.py (DRY SSOT)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT_TESTS = str(Path(__file__).resolve().parents[2] / "tests")
if _ROOT_TESTS not in sys.path:
    sys.path.insert(0, _ROOT_TESTS)

from test_openapi_breaking_guard import *  # noqa: F401, F403, E402

"""Migration contract: idempotent, correctly named DB migrations."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "migration_contract.py"


def test_guard_passes_on_the_live_tree():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=REPO_ROOT,
        capture_output=True, text=True, timeout=180, check=False,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]

"""secret env-naming rules — harness lock.

The guard ships its own self-test; nothing ran it from the pytest suite, so
`scripts/ci/test_parity_guard.py` counted `scripts/ci/secret_naming_guard.py` as untested and the parity
gate sat permanently red. Running the harness here keeps the guard honest: if
its fixtures or its parser rot, this fails.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/ci/secret_naming_guard.py"


def test_secret_naming_guard_harness_passes():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--self-test'],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]

"""Public-surface guard: the advertised surface must match its manifest.

Run against the committed manifest (the same invocation CI uses) so a manifest
edit that drops a file, or a file that starts exporting something the manifest
declares private, fails here too.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "public_surface_guard.py"
MANIFEST = REPO_ROOT / "scripts" / "ci" / "public_surface_manifest.txt"


def test_manifest_exists():
    assert MANIFEST.is_file(), "public surface manifest is missing"


def test_guard_passes_against_the_committed_manifest():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(MANIFEST)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=180, check=False,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]

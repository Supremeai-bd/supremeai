"""Tests for scripts/ci/service_entrypoint_census.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "service_entrypoint_census.py"


def test_service_entrypoint_census_self_test():
    """Verify that the guard's offline self-test passes 4/4 cases."""
    res = subprocess.run([sys.executable, str(SCRIPT), "--self-test"], capture_output=True, text=True)
    assert res.returncode == 0, f"Self-test failed:\n{res.stdout}\n{res.stderr}"
    assert "4/4 passed" in res.stdout


def test_service_entrypoint_census_check():
    """Verify that repo service_registry.yaml passes entrypoint census."""
    res = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True)
    assert res.returncode == 0, f"--check failed:\n{res.stdout}\n{res.stderr}"
    assert "PASS (all service entrypoints verified)" in res.stdout

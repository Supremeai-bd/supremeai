"""Tests for core/runner/agent_runner.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_core_agent_runner_self_test():
    """Verify that core/runner/agent_runner.py passes all hermetic contract checks."""
    runner = Path(__file__).resolve().parent.parent / "agent_runner.py"
    res = subprocess.run(
        [sys.executable, str(runner), "--self-test"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"agent_runner self-test failed:\n{res.stderr}\n{res.stdout}"
    assert "SELF-TEST OK" in res.stdout

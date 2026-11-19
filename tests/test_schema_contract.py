"""Schema contract gate: required tables must have migrations.

The guard maps each required table to a migration file. If that lookup silently
returns "found" for a missing table, schema drift ships.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "schema_contract.py"
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import schema_contract as contract  # noqa: E402


def test_migration_dirs_are_discovered():
    dirs = contract.find_migration_dirs()
    assert isinstance(dirs, list)


def test_find_file_returns_none_for_an_absent_name():
    assert contract.find_file("definitely-not-a-real-migration-2026.sql") is None


def test_guard_passes_on_the_live_tree():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=REPO_ROOT,
        capture_output=True, text=True, timeout=180, check=False,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]

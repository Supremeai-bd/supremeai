"""supreme_ops.py `cookies status|sync` wiring for browser/ghost_tower.

বাংলা মন্তব্য: CLI ঠিক .bat ফাইলের মতো (cwd=ghost_tower, একই স্ক্রিপ্ট) চালায় কিনা যাচাই।
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "scripts" / "ops" / "supreme_ops.py"
GHOST = ROOT / "browser" / "ghost_tower"


def _load():
    spec = importlib.util.spec_from_file_location("supreme_ops_under_test", OPS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize(
    ("action", "script", "bat"),
    [
        ("status", "check_cookies_status.py", "3_check_cookies_status.bat"),
        ("sync", "sync_cookies_to_infisical.py", "4_sync_cookies_to_infisical.bat"),
    ],
)
def test_cookies_action_runs_same_script_as_bat(action, script, bat):
    ops = _load()
    assert (GHOST / script).is_file()
    bat_text = (GHOST / bat).read_text(encoding="utf-8", errors="replace")
    assert f"python {script}" in bat_text, "the .bat launcher must keep running the same script"
    with mock.patch.object(ops.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
        assert ops.run_cookies(action) == 0
    args, kwargs = run.call_args
    assert args[0] == [sys.executable, str(GHOST / script)]
    assert kwargs["cwd"] == str(GHOST)
    assert kwargs["check"] is False


def test_cookies_propagates_exit_code_and_rejects_unknown():
    ops = _load()
    with mock.patch.object(ops.subprocess, "run", return_value=subprocess.CompletedProcess([], 3)):
        assert ops.run_cookies("status") == 3
    assert ops.run_cookies("nope") == 2


def test_cli_parses_cookies_subcommand():
    ops = _load()
    with mock.patch.object(ops, "run_cookies", return_value=0) as rc, mock.patch.object(
        sys, "argv", ["supreme_ops.py", "cookies", "status"]
    ):
        with pytest.raises(SystemExit) as exc:
            ops.main()
    assert exc.value.code == 0
    rc.assert_called_once_with("status")

"""Tests for scripts/ci/smart_priority_merger.py — Phase-A merge-authority disable (#4265).

বাংলা মন্তব্য: Pipeline Constitution RULE 6 / #4253 Phase-A — merge-gate.yml একমাত্র
landing authority। এই চুক্তি-টেস্ট নিশ্চিত করে:

1. `--execute` যেকোনো network/fetch/side-effect-এর **আগেই** fail-closed (exit 2) —
   কোনো অবস্থাতেই দ্বিতীয় merge authority হিসেবে চালু হতে পারে না।
2. Read-only planning modes (--plan) অটুট — guard অতিরিক্ত কিছু বন্ধ করে না।
3. কোনো workflow এই স্ক্রিপ্টকে invoke করে না (zero-ref স্থায়ী চুক্তি — ভবিষ্যতে
   re-wiring করলে টেস্ট লাল হবে, নীরবে RULE 6 ভাঙা অসম্ভব)।
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_MERGER = _ROOT / "scripts" / "ci" / "smart_priority_merger.py"

# বাংলা মন্তব্য: মডিউল লোড একবারই — spec-from-file (অন্য চুক্তি-টেস্টগুলোর মতোই)।
_spec = importlib.util.spec_from_file_location("smart_priority_merger_disable", _MERGER)
spm = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("smart_priority_merger_disable", spm)
_spec.loader.exec_module(spm)

EXIT_DENIED = 2
_DISABLED_MARKER = "MERGE-AUTHORITY-DISABLED"


def _run_cli(*argv: str) -> subprocess.CompletedProcess:
    # বাংলা মন্তব্য: ইচ্ছাকৃতভাবে কোনো GH_TOKEN নেই — guard সঠিক হলে network-পূর্বেই exit 2।
    env = {k: v for k, v in __import__("os").environ.items() if not k.startswith(("GH_", "GITHUB_"))}
    return subprocess.run(
        [sys.executable, str(_MERGER), *argv],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        cwd=str(_ROOT),
    )


class TestExecuteFailClosed:
    def test_execute_exits_2_before_any_network(self) -> None:
        """--execute → rc=2, disabled-marker সহ, এবং fetch_open_prs কখনোই পৌঁছায় না।"""
        res = _run_cli("--execute")
        assert res.returncode == EXIT_DENIED, f"rc={res.returncode} out={res.stdout[-400:]} err={res.stderr[-400:]}"
        assert _DISABLED_MARKER in res.stderr
        # বাংলা মন্তব্য: fetch-এর লগ-লাইন থাকল মানে guard network-এর পরে — চুক্তি-ভাঙা।
        assert "Fetching open PRs" not in (res.stdout + res.stderr)

    def test_execute_combined_with_dry_run_still_denied(self) -> None:
        """--execute --dry-run সংমিশ্রণেও execute-অর্থই প্রধান — সমানভাবে অস্বীকৃত (fail-closed)।"""
        res = _run_cli("--execute", "--dry-run")
        assert res.returncode == EXIT_DENIED
        assert _DISABLED_MARKER in res.stderr

    def test_guard_message_points_to_merge_gate(self) -> None:
        """বার্তায় merge-gate.yml নির্দেশ থাকতে হবে — operator যেন landing-লেন খুঁজে পায়।"""
        res = _run_cli("--execute")
        assert "merge-gate.yml" in res.stderr
        assert "#4265" in res.stderr or "#4253" in res.stderr


class TestGuardPrecedesSideEffects:
    def test_guard_precedes_fetch_open_prs(self) -> None:
        """fetch_open_prs বলা হলেই টেস্ট-ব্যর্থ — guard অবশ্যই তার আগে থাকতে হবে।"""
        def _explode(*_a, **_kw):
            raise AssertionError("fetch_open_prs reached — execute guard is not fail-closed")

        with patch.object(spm, "fetch_open_prs", side_effect=_explode), patch.object(
            sys, "argv", ["smart_priority_merger.py", "--execute"]
        ):
            with pytest.raises(SystemExit) as exc:
                spm.main()
        assert exc.value.code == EXIT_DENIED


class TestReadOnlyModesPreserved:
    def test_plan_mode_still_functions(self) -> None:
        """--plan (read-only) অটুট: fetch-এ খালি ফলাফল দিলে main স্বাভাবিকভাবে ফেরে।"""
        calls: list[list] = []

        def _fake_fetch(*_a, **_kw):
            calls.append(1)
            return []

        with patch.object(spm, "fetch_open_prs", side_effect=_fake_fetch), patch.object(
            sys, "argv", ["smart_priority_merger.py", "--plan"]
        ):
            spm.main()  # SystemExit হবে না
        assert calls, "plan mode অবরুদ্ধ হয়ে গেছে — guard over-blocking"

    def test_execute_flag_still_defined_but_denied_only_at_runtime(self) -> None:
        """argparse-এ --execute অপশন থেকে যায় (matrix/signals অপরিবর্তিত), শুধু runtime-এ deny।"""
        parser_probe = "--execute"
        res = _run_cli("--help")
        assert res.returncode == 0
        assert parser_probe in res.stdout


class TestZeroWorkflowReference:
    def test_no_workflow_invokes_smart_merger(self) -> None:
        """.github/workflows/-এ শূন্য রেফারেন্স — RULE 6-এর স্থায়ী source-level চুক্তি।"""
        wf_dir = _ROOT / ".github" / "workflows"
        hits: list[str] = []
        for wf in sorted(wf_dir.glob("*.y*ml")):
            text = wf.read_text(encoding="utf-8", errors="replace")
            if "smart_priority_merger" in text:
                hits.append(wf.name)
        assert hits == [], f"workflows re-wired to legacy merger: {hits}"

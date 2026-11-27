"""Changed-file guard selection remains fail-safe and non-vacuous."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'ci'))
import run_guards as runner


def test_unknown_guards_and_constitution_guards_are_never_filtered():
    assert runner._matches(['docs/example.md'], runner._paths_for(['python', 'scripts/ci/unknown_guard.py']))
    assert runner._matches(['docs/example.md'], runner._paths_for(['python', 'scripts/ci/workflow_validity_guard.py']))


def test_watch_paths_filter_only_unrelated_changes():
    cmd = ['python', 'scripts/ci/check_gateway_bypass.py', '--check']
    assert runner._matches(['gateway/main.py'], runner._paths_for(cmd))
    assert not runner._matches(['docs/example.md'], runner._paths_for(cmd))
    assert runner._matches([], runner._paths_for(cmd))


def test_select_keeps_always_run_guards_and_excludes_unrelated(monkeypatch):
    critical = ['python', 'scripts/ci/workflow_validity_guard.py', '--check']
    gateway = ['python', 'scripts/ci/check_gateway_bypass.py', '--check']
    monkeypatch.setattr(runner, 'GUARDS', [critical, gateway])
    selected, total = runner.select('full', ['docs/example.md'])
    assert total == 2 and selected == [critical]

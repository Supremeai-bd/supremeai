"""Offline tracker parsing and dry-run contracts."""
from __future__ import annotations

from scripts.ci import tracker_freshness as tracker


def test_scan_detects_heading_missing_file_and_size_drift(tmp_path):
    (tmp_path / 'server.ts').write_text('line\n' * 100, encoding='utf-8')
    doc = tmp_path / 'tracker.md'
    doc.write_text('# ✅ Completed\nserver.ts ২০০ লাইন\nmissing.py 100 lines\n', encoding='utf-8')
    findings = tracker.scan_tracker(doc)
    assert {f['kind'] for f in findings} == {'done-heading', 'size-drift', 'file-missing'}
    drift = next(f for f in findings if f['kind'] == 'size-drift')
    assert drift['claimed'] == 200 and drift['actual'] == 100


def test_missing_tracker_is_reported(tmp_path):
    assert tracker.scan_tracker(tmp_path / 'absent.md')[0]['kind'] == 'tracker-missing'


def test_dry_run_never_calls_gh(monkeypatch):
    def forbidden(_args):
        raise AssertionError('dry-run attempted a write')
    monkeypatch.setattr(tracker, '_gh', forbidden)
    result = tracker.propose_issue_stale(123, 'review', 'needs-verification', dry_run=True)
    assert result['issue'] == 123 and '[dry-run]' in result['actions'][0]

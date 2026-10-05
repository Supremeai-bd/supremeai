# বাংলা মন্তব্য (#2856 ফলো-আপ): legacy-API মাইগ্রেশন-শিম — create_discovery_issue.py একত্রীকরণের পর 
# create_issue.py থেকে একে নামের ফাংশন প্রদান করে; টেস্ট-বডি অপরিবর্তিত। """Unit tests — unified scripts/agents/create_issue.py (legacy surface)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from scripts.agents.create_issue import (
    check_duplicates,
    create_discovery_issue,
    format_discovery_body,
)


def test_format_discovery_body_contains_parent():
    body = format_discovery_body(
        parent_issue=123,
        description="Found test bug",
        role="coder",
        severity="medium",
    )
    assert "#123" in body
    assert "Found test bug" in body
    assert "coder" in body


def test_create_discovery_issue_dry_run():
    res = create_discovery_issue(
        parent_issue=123,
        title="fix(test): sample discovery",
        body="details",
        role="ci",
        severity="high",
        dry_run=True,
    )
    assert res.is_dry_run is True
    assert res.success is True
    assert "type:discovery" in res.labels
    assert "discovered-by:ci" in res.labels
    # #3278: severity → canonical P-label (bare `high` লেবেল রিপোতে নেই —
    # একই class-এ পুরো create মৃত হতো)
    assert "P1-high" in res.labels
    assert "high" not in res.labels


def test_create_discovery_issue_label_fallback(monkeypatch):
    """Verify that if initial gh issue create fails due to a missing label, it retries with fallback.

    #3278: এখন create-এর আগে label-ensure pre-flight চলে (প্রথম subprocess-কল
    = `gh label list`) — মক-সিকোয়েন্স সেই অনুযায়ী; fallback-লেবেলেও
    canonical P-label।"""
    calls = []

    def mock_run(cmd, **kwargs):
        calls.append(cmd)
        # label-ensure pre-flight (#3278): লেবেল-তালিকা — সব existing ধরা হোক
        if "label" in cmd and "list" in cmd:
            mock_res = MagicMock()
            mock_res.returncode = 0
            labels_json = [
                {"name": "type:discovery"},
                {"name": "status:unclaimed"},
                {"name": "discovered-by:coder"},
                {"name": "P2-medium"},
            ]
            mock_res.stdout = json.dumps(labels_json)
            mock_res.stderr = ""
            return mock_res
        issue_creates = [c for c in calls if "issue" in c and "create" in c]
        if len(issue_creates) == 1:
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=cmd,
                output="",
                stderr="could not add label: 'type:unknown' not found",
            )
        # পরবর্তী issue-create সফল
        mock_res = MagicMock()
        mock_res.stdout = "https://github.com/SaifulHaqueNiloy/supremeai/issues/9988\n"
        return mock_res

    monkeypatch.setattr(subprocess, "run", mock_run)

    res = create_discovery_issue(
        parent_issue=456,
        title="fix(test): fallback test",
        body="details",
        role="coder",
        severity="medium",
        dry_run=False,
    )

    issue_create_calls = [c for c in calls if "issue" in c and "create" in c]
    assert len(issue_create_calls) == 2
    assert res.success is True
    assert res.new_issue_number == 9988
    # #3278: fallback-এও canonical P-label — bare severity নয়
    assert res.labels == ["status:unclaimed", "P2-medium"]


def test_check_duplicates_gh_missing_no_unbound_local(monkeypatch):
    """#2528 regression: gh-বাইনারি না থাকলে (FileNotFoundError) আগে
    except-টাপলের json.JSONDecodeError এভালুয়েশনেই UnboundLocalError হতো —
    import json try-ব্লকের ভেতরে ছিল। এখন module-top import; [] ফেরত দেয়।"""
    import scripts.agents.create_issue as mod

    def _raise(*a, **kw):
        raise FileNotFoundError("gh: executable not found")

    monkeypatch.setattr(mod.subprocess, "run", _raise)
    result = check_duplicates("fix(db): vector store leaks across tenants")
    assert result == []


def test_check_duplicates_bad_json(monkeypatch):
    """gh-র আউটপুট ভাঙা JSON হলেও [] — একই try-ব্লকের চুক্তি।"""
    import scripts.agents.create_issue as mod

    class FakeProc:
        returncode = 0
        stdout = "not-json["

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **kw: FakeProc())
    assert check_duplicates("some title with words") == []

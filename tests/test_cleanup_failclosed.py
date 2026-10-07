#!/usr/bin/env python3
"""#4204 — fail-closed contract tests for cleanup_stale_branches.py.

Contract under test (#4200 §9 corrected): uncertainty NEVER resolves to
deletion. Three fail-open paths of the pre-#4204 implementation are covered:
  1. no GH_TOKEN           → abort (exit 2), zero deletions
  2. open-PR fetch failure → abort (exit 2), zero deletions
  3. label/PR API failure  → preserve that branch
Plus the merged/completed proof matrix (merged-pr / closed / none+ancestor).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = REPO_ROOT / "scripts" / "ci" / "cleanup_stale_branches.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cleanup_stale_branches_4204", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("cleanup_stale_branches_4204", mod)
    spec.loader.exec_module(mod)
    return mod


csb = _load_module()


# ─────────────────────────── pure decision core ───────────────────────────

class TestDecideDeletion:
    def test_merged_pr_allows_deletion(self):
        safe, reason = csb.decide_deletion("agent/4200-slug", labels=set(),
                                           pr_state="merged", ancestor=None)
        assert safe is True and reason == "merged-pr"

    def test_merged_ancestor_allows_deletion(self):
        safe, reason = csb.decide_deletion("coder-1-4200-slug", labels=set(),
                                           pr_state="none", ancestor=True)
        assert safe is True and reason == "merged-ancestor"

    def test_label_verification_unavailable_preserves(self):
        safe, reason = csb.decide_deletion("agent/4200-slug", labels=None,
                                           pr_state="merged", ancestor=None)
        assert safe is False and reason == "label-verification-unavailable"

    @pytest.mark.parametrize("label", sorted(csb.PRESERVE_LABELS))
    def test_preserve_labels_block_deletion(self, label):
        safe, reason = csb.decide_deletion("agent/4200-slug", labels={label},
                                           pr_state="merged", ancestor=None)
        assert safe is False and reason.startswith("preserve-label:")

    def test_merge_proof_unavailable_preserves(self):
        safe, _ = csb.decide_deletion("agent/4200-slug", labels=set(),
                                      pr_state=None, ancestor=None)
        assert safe is False

    def test_closed_unmerged_pr_preserves(self):
        safe, reason = csb.decide_deletion("agent/4200-slug", labels=set(),
                                           pr_state="closed", ancestor=None)
        assert safe is False and reason == "closed-unmerged-pr-preserved"

    def test_open_pr_preserves_defensively(self):
        safe, reason = csb.decide_deletion("agent/4200-slug", labels=set(),
                                           pr_state="open", ancestor=None)
        assert safe is False and reason == "open-pr-preserved"

    def test_unmerged_work_without_pr_preserves(self):
        """The #4200 core: unmerged persistent workspace must survive cleanup."""
        safe, reason = csb.decide_deletion("agent/4200-slug", labels=set(),
                                           pr_state="none", ancestor=False)
        assert safe is False and reason == "unmerged-work-preserved"

    def test_git_proof_unavailable_preserves(self):
        safe, reason = csb.decide_deletion("agent/4200-slug", labels=set(),
                                           pr_state="none", ancestor=None)
        assert safe is False and reason == "merge-proof-unavailable"


# ─────────────────────────── main() fail-closed gates ───────────────────────────

class TestFailClosedMain:
    def _patch(self, monkeypatch, token="tok", open_heads=None, open_heads_err=None,
               remote=None, labels=None, pr_state="merged", ancestor=False,
               delete_calls=None):
        monkeypatch.setattr(csb, "get_gh_token", lambda: token)
        if open_heads_err is not None:
            def _raise():
                raise RuntimeError(open_heads_err)
            monkeypatch.setattr(csb, "get_open_pr_head_branches", _raise)
        else:
            monkeypatch.setattr(csb, "get_open_pr_head_branches",
                                lambda: open_heads if open_heads is not None else set())
        monkeypatch.setattr(csb, "get_remote_branches", lambda: remote or set())
        monkeypatch.setattr(csb, "get_issue_labels", lambda n, t: labels)
        monkeypatch.setattr(csb, "get_pr_merge_state", lambda b, t: pr_state)
        monkeypatch.setattr(csb, "is_ancestor_of_main", lambda b: ancestor)
        monkeypatch.setattr(csb, "_delete_branches",
                            lambda branches: delete_calls.append(list(branches)))

    def test_no_token_aborts_and_deletes_nothing(self, monkeypatch):
        calls: list = []
        self._patch(monkeypatch, token="", remote=["agent/4200-x"], delete_calls=calls)
        assert csb.main() == 2
        assert calls == []

    def test_open_pr_fetch_failure_aborts_and_deletes_nothing(self, monkeypatch):
        calls: list = []
        self._patch(monkeypatch, open_heads_err="gh auth expired",
                    remote=["agent/4200-x"], delete_calls=calls)
        assert csb.main() == 2
        assert calls == []

    def test_label_api_failure_preserves_branch(self, monkeypatch):
        calls: list = []
        self._patch(monkeypatch, remote=["agent/4200-x"], labels=None,
                    pr_state="merged", delete_calls=calls)
        assert csb.main() == 0
        assert calls == []  # uncertainty → preserve, never delete

    def test_preserve_label_blocks_deletion_in_main_flow(self, monkeypatch):
        calls: list = []
        self._patch(monkeypatch, remote=["agent/4200-x"], labels={"branch:active"},
                    pr_state="merged", delete_calls=calls)
        assert csb.main() == 0
        assert calls == []

    def test_happy_path_deletes_only_provably_merged(self, monkeypatch):
        calls: list = []
        states = {"agent/4200-x": "merged", "agent/4201-y": "none",
                  "agent/4202-z": "closed"}
        monkeypatch.setattr(csb, "get_gh_token", lambda: "tok")
        monkeypatch.setattr(csb, "get_open_pr_head_branches", lambda: set())
        monkeypatch.setattr(csb, "get_remote_branches",
                            lambda: set(states) | {"main-check", "recheck"})
        monkeypatch.setattr(csb, "get_issue_labels", lambda n, t: set())
        monkeypatch.setattr(csb, "get_pr_merge_state", lambda b, t: states[b])
        monkeypatch.setattr(csb, "is_ancestor_of_main", lambda b: b == "agent/4200-x")
        monkeypatch.setattr(csb, "_delete_branches",
                            lambda branches: calls.append(list(branches)))
        assert csb.main() == 0
        flat = [b for chunk in calls for b in chunk]
        assert sorted(flat) == ["agent/4200-x"]  # merged proof only; unmerged/closed preserved

    def test_non_agent_branches_never_considered(self, monkeypatch):
        calls: list = []
        self._patch(monkeypatch, remote={"release-v1", "hotfix-x"},
                    pr_state="merged", delete_calls=calls)
        assert csb.main() == 0
        assert calls == []


# ─────────────────────────── extraction contract (stable API) ───────────────────────────

class TestExtractIssueNumber:
    @pytest.mark.parametrize("branch,expected", [
        ("agent/4200-persistent-branch", 4200),
        ("coder-1-4138-theme8-metrics", 4138),
        ("ci-2-1234-slug", 1234),
        ("planner-1-4204-cleanup-failclosed", 4204),
    ])
    def test_patterns(self, branch, expected):
        assert csb.extract_issue_number(branch) == expected

    def test_no_number_returns_none(self):
        assert csb.extract_issue_number("agent/session-workspace") is None

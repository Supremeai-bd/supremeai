"""Tests for continuous_agent_loop.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.agents.continuous_agent_loop import has_open_issues, run_audit


class TestHasOpenIssues:
    @patch("scripts.agents.continuous_agent_loop.run")
    def test_returns_true_when_issues_exist(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='[{"number": 1}]')
        assert has_open_issues() is True

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_returns_false_when_no_issues(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert has_open_issues() is False

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_returns_false_on_error(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")

    # ── #2928: type:ledger চির-open ড্যাশবোর্ড বাদ — নইলে smart-fallback মৃত-কোড ──

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_ledger_only_issues_mean_no_work_issues(self, mock_run):
        """PRIORITY-QUEUE-LEDGER-এর মতো ড্যাশবোর্ড open থাকলেও fallback চলবে।"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"labels": [{"name": "type:ledger"}]},
                {"labels": [{"name": "P0-critical"}, {"name": "type:ledger"}]},
            ]),
        )
        assert has_open_issues() is False

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_mixed_ledger_and_work_issues_mean_work_exists(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"labels": [{"name": "type:ledger"}]},
                {"labels": [{"name": "P1-high"}]},
            ]),
        )
        assert has_open_issues() is True

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_unparsable_output_falls_back_to_bool(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="not-json")
        assert has_open_issues() is True


class TestRunAudit:
    @patch("scripts.agents.continuous_agent_loop.run")
    def test_runs_audit(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        run_audit()
        assert mock_run.called


# ═══════════════════════════════════════════════════════════════════════
# #2745 — Admin-Approval Gate (সংবেদনশীল ইস্যুতে অ্যাডমিন-অনুমোদন বাধ্যতামূলক)
# ═══════════════════════════════════════════════════════════════════════

from scripts.agents.continuous_agent_loop import (
    _AWAITING_MARKER,
    admin_approval_gate,
)


def _issue_view_payload(labels, comments=None):
    import json as _json

    return _json.dumps({
        "labels": [{"name": l} for l in labels],
        "comments": comments or [],
    })


class TestAdminApprovalGate:
    @patch("scripts.agents.continuous_agent_loop.run")
    def test_ungated_issue_passes(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=_issue_view_payload(["P1-high"]))
        allowed, reason = admin_approval_gate(100)
        assert allowed is True
        assert reason == ""

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_gated_without_approval_blocks_and_notifies_once(self, mock_run):
        """গেটেড ইস্যু ব্লক হবে + প্রথমবার মার্কার-কমেন্ট (নোটিফিকেশন) যাবে।"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout=_issue_view_payload(["gate:admin-approval"])
        )
        allowed, reason = admin_approval_gate(101)
        assert allowed is False
        assert "gate:admin-approval" in reason
        # নোটিফিকেশন-কমেন্ট পোস্ট হয়েছে — run() একটি লিস্ট-আর্গিউমেন্ট নেয়
        commented = any(
            c.args
            and isinstance(c.args[0], list)
            and c.args[0][:3] == ["gh", "issue", "comment"]
            for c in mock_run.call_args_list
        )
        assert commented

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_gated_with_dedup_marker_does_not_renotify(self, mock_run):
        """আগেই নোটিফাই হয়ে থাকলে আর কমেন্ট যাবে না (dedup)।"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=_issue_view_payload(
                ["gate:admin-approval"],
                comments=[{"body": f"{_AWAITING_MARKER}\nalready notified"}],
            ),
        )
        allowed, _ = admin_approval_gate(102)
        assert allowed is False
        # শুধু view-কল — comment-কল নেই
        assert all("comment" not in (c.args[3] if len(c.args) > 3 else "") for c in mock_run.call_args_list)

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_gated_with_approved_label_releases(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=_issue_view_payload(["gate:admin-approval", "approved-by:admin"]),
        )
        allowed, reason = admin_approval_gate(103)
        assert allowed is True
        assert "admin-approved" in reason

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_gh_failure_fail_closed(self, mock_run):
        """gh-ব্যর্থতায় fail-closed — অনুমোদন-বাইপাসের অজুহাত নয়।"""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        allowed, reason = admin_approval_gate(104)
        assert allowed is False
        assert "fail-closed" in reason


# ═══════════════════════════════════════════════════════════════════════
# Issue #2944 — acquire_next_issue, claim_issue, get_effective_role
# ═══════════════════════════════════════════════════════════════════════

from scripts.agents.continuous_agent_loop import (
    acquire_next_issue,
    claim_issue,
    get_effective_role,
)


class TestAcquireNextIssue:
    @patch("scripts.agents.continuous_agent_loop.run")
    def test_acquire_next_issue_json_format_passed_and_parsed(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"issue": 2902, "role": "coder", "branch_name": "coder-2-2902"}',
        )
        task = acquire_next_issue("coder", "coder-1")
        assert task is not None
        assert task["issue"] == 2902
        assert task["branch_name"] == "coder-2-2902"
        # Check that --format json was passed
        cmd = mock_run.call_args[0][0]
        assert "--format" in cmd
        idx = cmd.index("--format")
        assert cmd[idx + 1] == "json"

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_acquire_next_issue_mixed_stdout(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Notice: slot fetched\n{"issue": 2944, "role": "coder"}\nEnd of line',
        )
        task = acquire_next_issue("coder", "coder-1")
        assert task is not None
        assert task["issue"] == 2944

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_acquire_next_issue_text_regex_fallback(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "⚡ [Autonomous Queue Resolver] Next priority issue: #2902 (feat...)\n"
                "🎯 Assigned Role: coder\n"
                "🌿 Acquired Slot: coder-2-2902-p0-group\n"
            ),
        )
        task = acquire_next_issue("coder", "coder-1")
        assert task is not None
        assert task["issue"] == 2902
        assert task["branch_name"] == "coder-2-2902-p0-group"


class TestClaimIssue:
    @patch("scripts.agents.continuous_agent_loop.run")
    @patch("sys.platform", "win32")
    def test_claim_issue_uses_bash_on_win32(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success = claim_issue(2944, "coder-1")
        assert success is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "bash"
        assert "./scripts/ci/atomic_claim.sh" in cmd[1]


class TestGetEffectiveRole:
    @patch("scripts.agents.smart_dispatcher.SmartDispatcher._should_switch_role")
    def test_get_effective_role_switches_when_needed(self, mock_switch):
        mock_switch.return_value = ("ci-fixer", "CI RED on main")
        role = get_effective_role("coder")
        assert role == "ci-fixer"

    @patch("scripts.agents.smart_dispatcher.SmartDispatcher._should_switch_role")
    def test_get_effective_role_keeps_role_when_healthy(self, mock_switch):
        mock_switch.return_value = ("coder", "")
        role = get_effective_role("coder")
        assert role == "coder"



# ─────────────────── #2950: Script-Driven Role Assignment Tests ───────────────────


class TestDecideRole:
    """#2950 requirement 1: Script decides role based on unclaimed issue presence."""

    @patch("scripts.agents.continuous_agent_loop.has_unclaimed_work_issues")
    def test_decides_coder_when_unclaimed_issues_exist(self, mock_has):
        from scripts.agents.continuous_agent_loop import decide_role
        mock_has.return_value = True
        assert decide_role() == "coder"

    @patch("scripts.agents.continuous_agent_loop.has_unclaimed_work_issues")
    def test_decides_auditor_when_no_unclaimed_issues(self, mock_has):
        from scripts.agents.continuous_agent_loop import decide_role
        mock_has.return_value = False
        assert decide_role() == "auditor"


class TestHasUnclaimedWorkIssues:
    """#2950: unclaimed = no in-progress/has-pr label, not ledger, not gated."""

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_returns_true_when_unclaimed_work_issue_exists(self, mock_run):
        from scripts.agents.continuous_agent_loop import has_unclaimed_work_issues
        # Issue with only P0-critical label — no in-progress/has-pr → unclaimed
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"number": 1, "labels": [{"name": "P0-critical"}]}]),
        )
        assert has_unclaimed_work_issues() is True

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_returns_false_when_all_in_progress(self, mock_run):
        from scripts.agents.continuous_agent_loop import has_unclaimed_work_issues
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"number": 1, "labels": [{"name": "status:in-progress"}]}]),
        )
        assert has_unclaimed_work_issues() is False

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_returns_false_when_all_have_pr(self, mock_run):
        from scripts.agents.continuous_agent_loop import has_unclaimed_work_issues
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"number": 1, "labels": [{"name": "has-pr"}]}]),
        )
        assert has_unclaimed_work_issues() is False

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_skips_type_ledger_issues(self, mock_run):
        from scripts.agents.continuous_agent_loop import has_unclaimed_work_issues
        # Ledger issue (PRIORITY-QUEUE-LEDGER) should not count as work issue
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"number": 1, "labels": [{"name": "type:ledger"}]}]),
        )
        assert has_unclaimed_work_issues() is False


class TestBuildTaskContract:
    """#2950 requirement 2 + 3 + 4: JSON TaskContract completeness."""

    def test_contract_contains_all_required_keys(self):
        from scripts.agents.continuous_agent_loop import build_task_contract
        task = {
            "issue": 2950,
            "title": "test issue",
            "labels": ["P1-high"],
            "branch_name": "coder-1-2950-test",
        }
        contract = build_task_contract("coder-1", "coder", task, "coder-1-2950-test")
        # Required keys per #2950 spec
        assert "agent" in contract
        assert "role" in contract
        assert "issue" in contract
        assert "branch" in contract
        assert "applicable_rules" in contract
        assert "prohibited_rules" in contract
        assert "scoped_credentials" in contract
        assert "mcp_payload" in contract
        assert "cooldown_after_seconds" in contract

    def test_contract_agent_name_matches_input(self):
        from scripts.agents.continuous_agent_loop import build_task_contract
        task = {"issue": 1, "title": "t", "labels": []}
        contract = build_task_contract("coder-5", "coder", task, "b")
        assert contract["agent"]["name"] == "coder-5"

    def test_contract_role_matches_input(self):
        from scripts.agents.continuous_agent_loop import build_task_contract
        task = {"issue": 1, "title": "t", "labels": []}
        contract = build_task_contract("a", "auditor", task, "b")
        assert contract["role"] == "auditor"

    def test_contract_issue_block_has_number_title_labels(self):
        from scripts.agents.continuous_agent_loop import build_task_contract
        task = {"issue": 42, "title": "my title", "labels": ["bug"]}
        contract = build_task_contract("a", "coder", task, "b")
        assert contract["issue"]["number"] == 42
        assert contract["issue"]["title"] == "my title"
        assert contract["issue"]["labels"] == ["bug"]

    def test_contract_scoped_credentials_no_real_token(self):
        from scripts.agents.continuous_agent_loop import build_task_contract
        task = {"issue": 1, "title": "t", "labels": []}
        contract = build_task_contract("coder-1", "coder", task, "b")
        # Real tokens must NEVER appear in the contract
        assert contract["scoped_credentials"]["token_masked"] is True
        assert "allowed_env_keys" in contract["scoped_credentials"]
        # No raw token value should leak
        creds_json = json.dumps(contract["scoped_credentials"])
        assert "ghs_" not in creds_json  # GitHub token prefix
        assert "ghp_" not in creds_json

    def test_contract_mcp_payload_has_role_and_heartbeat(self):
        from scripts.agents.continuous_agent_loop import build_task_contract
        task = {"issue": 1, "title": "t", "labels": []}
        contract = build_task_contract("a", "auditor", task, "b")
        assert contract["mcp_payload"]["role"] == "auditor"
        assert contract["mcp_payload"]["heartbeat_interval"] == 30

    def test_contract_cooldown_default_120_seconds(self):
        from scripts.agents.continuous_agent_loop import build_task_contract
        task = {"issue": 1, "title": "t", "labels": []}
        contract = build_task_contract("a", "coder", task, "b")
        assert contract["cooldown_after_seconds"] == 120


class TestAcquireRoleWithLock:
    """#2950: single-agent-per-role lock — coder bypasses, others acquire."""

    @patch("scripts.agents.continuous_agent_loop.acquire_role_lock")
    def test_coder_bypasses_lock(self, mock_lock):
        from scripts.agents.continuous_agent_loop import acquire_role_with_lock
        # coder should NOT call acquire_role_lock — multiple agents allowed
        result = acquire_role_with_lock("coder", "coder-1")
        assert result is True
        mock_lock.assert_not_called()

    @patch("scripts.agents.continuous_agent_loop.acquire_role_lock")
    def test_auditor_acquires_lock(self, mock_lock):
        from scripts.agents.continuous_agent_loop import acquire_role_with_lock
        mock_lock.return_value = True
        result = acquire_role_with_lock("auditor", "auditor-1")
        assert result is True
        mock_lock.assert_called_once_with("auditor", "auditor-1", ttl=3600)

    @patch("scripts.agents.continuous_agent_loop.acquire_role_lock")
    @patch("scripts.agents.continuous_agent_loop.time.sleep", return_value=None)
    def test_auditor_retries_after_lock_failure(self, mock_sleep, mock_lock):
        from scripts.agents.continuous_agent_loop import acquire_role_with_lock
        # First attempt fails, retry succeeds
        mock_lock.side_effect = [False, True]
        result = acquire_role_with_lock("auditor", "auditor-1")
        assert result is True
        assert mock_lock.call_count == 2
        mock_sleep.assert_called_once()  # 10-min sleep before retry

    @patch("scripts.agents.continuous_agent_loop.acquire_role_lock")
    @patch("scripts.agents.continuous_agent_loop.time.sleep", return_value=None)
    def test_auditor_exits_after_retry_failure(self, mock_sleep, mock_lock):
        from scripts.agents.continuous_agent_loop import acquire_role_with_lock
        # Both attempts fail
        mock_lock.return_value = False
        result = acquire_role_with_lock("auditor", "auditor-1")
        assert result is False


class TestAgentIdentityModule:
    """#2950: agent_identity.py — persistent identity + cooldown + role lock."""

    def test_machine_id_is_stable(self, tmp_path, monkeypatch):
        from scripts.agents import agent_identity
        # Same machine → same machine_id
        id1 = agent_identity._machine_id()
        id2 = agent_identity._machine_id()
        assert id1 == id2

    def test_record_and_check_cooldown(self, tmp_path, monkeypatch):
        from scripts.agents import agent_identity
        # Patch COOLDOWN_REGISTRY to tmp_path
        registry = tmp_path / "cooldown.json"
        monkeypatch.setattr(agent_identity, "COOLDOWN_REGISTRY", registry)
        # Fresh agent — cooled down
        assert agent_identity.is_cooled_down("coder-1") is True
        # Record 60s cooldown
        agent_identity.record_cooldown("coder-1", seconds=60)
        # Immediately after — NOT cooled down
        assert agent_identity.is_cooled_down("coder-1") is False

    def test_cooldown_expires(self, tmp_path, monkeypatch):
        import time as _time
        from scripts.agents import agent_identity
        registry = tmp_path / "cooldown.json"
        monkeypatch.setattr(agent_identity, "COOLDOWN_REGISTRY", registry)
        # Record 1-second cooldown
        agent_identity.record_cooldown("coder-1", seconds=1)
        assert agent_identity.is_cooled_down("coder-1") is False
        # Wait for it to expire
        _time.sleep(1.1)
        assert agent_identity.is_cooled_down("coder-1") is True

    def test_role_lock_acquire_release(self, tmp_path, monkeypatch):
        from scripts.agents import agent_identity
        lock_dir = tmp_path / "role_locks"
        monkeypatch.setattr(agent_identity, "_role_lock_metadata_path",
                            lambda role: lock_dir / f"{role}.json")
        # Patch git push to always succeed (simulate clean CAS)
        monkeypatch.setattr(agent_identity, "_git_push_atomic", lambda b: True)
        # Acquire auditor lock
        assert agent_identity.acquire_role_lock("auditor", "auditor-1", ttl=3600) is True
        # Same agent can re-acquire (renew)
        assert agent_identity.acquire_role_lock("auditor", "auditor-1", ttl=3600) is True
        # Different agent CANNOT acquire (locked)
        assert agent_identity.acquire_role_lock("auditor", "auditor-2", ttl=3600) is False
        # Release by owner
        assert agent_identity.release_role_lock("auditor", "auditor-1") is True
        # Now different agent CAN acquire
        assert agent_identity.acquire_role_lock("auditor", "auditor-2", ttl=3600) is True

    def test_role_lock_not_released_by_non_owner(self, tmp_path, monkeypatch):
        from scripts.agents import agent_identity
        lock_dir = tmp_path / "role_locks"
        monkeypatch.setattr(agent_identity, "_role_lock_metadata_path",
                            lambda role: lock_dir / f"{role}.json")
        monkeypatch.setattr(agent_identity, "_git_push_atomic", lambda b: True)
        agent_identity.acquire_role_lock("auditor", "auditor-1", ttl=3600)
        # Non-owner tries to release — should fail
        assert agent_identity.release_role_lock("auditor", "auditor-2") is False
        # Lock still held by auditor-1
        assert agent_identity.acquire_role_lock("auditor", "auditor-3", ttl=3600) is False

    def test_coder_role_lock_always_succeeds(self, monkeypatch):
        """coder allows multiple agents — lock is always True (no lock needed)."""
        from scripts.agents import agent_identity
        assert agent_identity.acquire_role_lock("coder", "coder-1") is True
        assert agent_identity.acquire_role_lock("coder", "coder-2") is True
        assert agent_identity.acquire_role_lock("coder", "coder-999") is True


# ─────────────────── #2950-followup: Substring Bug + Dynamic Model + Heartbeat ───────────────────


class TestSubstringBugFix:
    """#2950 follow-up: atomic_claim.sh substring bug — regression test."""

    def test_canonical_marker_matches_exact_agent(self):
        """Atomic claim body with **Agent:** `coder-1` should match coder-1."""
        import re
        body = "### 🔒 Atomic Claim\n\n- **Agent:** `coder-1`\n- **Issue:** #100\n"
        pattern = re.compile(r'\*\*Agent:\*\*\s*`coder-1`')
        assert pattern.search(body) is not None

    def test_design_doc_substring_does_not_match(self):
        """Design doc with 'coder-1' as substring should NOT match (root-cause)."""
        import re
        body = """## Refined Design

Naming: `glm5.2-coder-1` (example)
identity.json: {"agent_name": "coder-1", "machine_id": "abc"}
"""
        pattern = re.compile(r'\*\*Agent:\*\*\s*`coder-1`')
        assert pattern.search(body) is None  # false-positive prevented

    def test_other_agent_name_does_not_match(self):
        """coder-10 should NOT match pattern for coder-1."""
        import re
        body = "- **Agent:** `coder-10`\n"
        pattern = re.compile(r'\*\*Agent:\*\*\s*`coder-1`')
        assert pattern.search(body) is None


class TestClaimIssueEnhanced:
    """#2950 follow-up: claim_issue() with --skip-assign + --files + error capture."""

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_passes_skip_assign_by_default(self, mock_run):
        # Success case
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert claim_issue(1234, "coder-1") is True
        cmd = mock_run.call_args[0][0]
        assert "--skip-assign" in cmd

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_passes_files_when_provided(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        claim_issue(1234, "coder-1", files="a.py, b.py")
        cmd = mock_run.call_args[0][0]
        assert "--files" in cmd
        assert "a.py, b.py" in cmd

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_captures_stdout_when_stderr_empty(self, mock_run):
        """#2950: atomic_claim.sh-এর error stdout-এ যায় — capture that."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="❌ Claim blocked by Rule #13", stderr=""
        )
        assert claim_issue(1234, "coder-1") is False


class TestModelSanitization:
    """#2950 follow-up: model name sanitization for branch-safe agent names."""

    def test_lowercase_and_hyphenate(self):
        from scripts.agents.agent_identity import _sanitize_model
        assert _sanitize_model("GLM 5.2") == "glm-5.2"
        assert _sanitize_model("Sonnet 3.5") == "sonnet-3.5"

    def test_special_chars_replaced(self):
        from scripts.agents.agent_identity import _sanitize_model
        assert _sanitize_model("claude@3.7") == "claude-3.7"
        assert _sanitize_model("gpt-4 (turbo)") == "gpt-4-turbo"

    def test_empty_returns_unknown(self):
        from scripts.agents.agent_identity import _sanitize_model
        assert _sanitize_model("") == "unknown"
        assert _sanitize_model(None) == "unknown"

    def test_already_clean_unchanged(self):
        from scripts.agents.agent_identity import _sanitize_model
        assert _sanitize_model("glm5.2") == "glm5.2"
        assert _sanitize_model("sonnet-3.5") == "sonnet-3.5"


class TestHeartbeatRegistry:
    """#2950 follow-up: heartbeat lifecycle — update, alive check, active agents."""

    def test_update_and_check_alive(self, tmp_path, monkeypatch):
        from scripts.agents import agent_identity
        registry = tmp_path / "heartbeat.json"
        monkeypatch.setattr(agent_identity, "HEARTBEAT_REGISTRY", registry)
        # Fresh agent — no heartbeat → not alive
        assert agent_identity.is_agent_alive("coder-1") is False
        # Update heartbeat
        agent_identity.update_heartbeat("coder-1", "coder", model="glm5.2")
        # Now alive
        assert agent_identity.is_agent_alive("coder-1") is True

    def test_heartbeat_expires_after_ttl(self, tmp_path, monkeypatch):
        import time as _time
        from scripts.agents import agent_identity
        registry = tmp_path / "heartbeat.json"
        monkeypatch.setattr(agent_identity, "HEARTBEAT_REGISTRY", registry)
        # Update with 1-second TTL
        agent_identity.update_heartbeat("coder-1", "coder")
        assert agent_identity.is_agent_alive("coder-1", ttl=1) is True
        _time.sleep(1.1)
        assert agent_identity.is_agent_alive("coder-1", ttl=1) is False

    def test_mark_exited_makes_agent_dead(self, tmp_path, monkeypatch):
        from scripts.agents import agent_identity
        registry = tmp_path / "heartbeat.json"
        monkeypatch.setattr(agent_identity, "HEARTBEAT_REGISTRY", registry)
        agent_identity.update_heartbeat("coder-1", "coder")
        assert agent_identity.is_agent_alive("coder-1") is True
        agent_identity.mark_heartbeat_exited("coder-1")
        assert agent_identity.is_agent_alive("coder-1") is False

    def test_get_active_agents_lists_only_fresh(self, tmp_path, monkeypatch):
        from scripts.agents import agent_identity
        registry = tmp_path / "heartbeat.json"
        monkeypatch.setattr(agent_identity, "HEARTBEAT_REGISTRY", registry)
        # Two agents: one fresh, one exited
        agent_identity.update_heartbeat("glm5.2-coder-1", "coder", model="glm5.2")
        agent_identity.update_heartbeat("glm5.2-coder-2", "coder", model="glm5.2")
        agent_identity.mark_heartbeat_exited("glm5.2-coder-2")
        active = agent_identity.get_active_agents()
        names = [a["agent_name"] for a in active]
        assert "glm5.2-coder-1" in names
        assert "glm5.2-coder-2" not in names  # exited

    def test_remove_stale_heartbeat(self, tmp_path, monkeypatch):
        from scripts.agents import agent_identity
        registry = tmp_path / "heartbeat.json"
        monkeypatch.setattr(agent_identity, "HEARTBEAT_REGISTRY", registry)
        agent_identity.update_heartbeat("old-agent", "coder")
        agent_identity.remove_stale_heartbeat("old-agent")
        assert agent_identity.is_agent_alive("old-agent") is False


class TestTokenRefresh:
    """#2950 follow-up: token refresh hook — checks file age."""

    def test_token_fresh_if_recent(self, tmp_path, monkeypatch):
        import time as _time
        from scripts.agents import agent_identity
        token_file = tmp_path / "token.txt"
        token_file.write_text("ghs_fake_token")
        monkeypatch.setattr(agent_identity, "TOKEN_FILE", token_file)
        assert agent_identity.is_token_fresh() is True

    def test_token_stale_if_old(self, tmp_path, monkeypatch):
        import time as _time
        from scripts.agents import agent_identity
        token_file = tmp_path / "token.txt"
        # Create file with old mtime (1 hour ago)
        token_file.write_text("ghs_fake_token")
        old_time = _time.time() - 3600
        import os as _os
        _os.utime(token_file, (old_time, old_time))
        monkeypatch.setattr(agent_identity, "TOKEN_FILE", token_file)
        assert agent_identity.is_token_fresh() is False

    def test_no_token_file_means_stale(self, tmp_path, monkeypatch):
        from scripts.agents import agent_identity
        token_file = tmp_path / "nonexistent.txt"
        monkeypatch.setattr(agent_identity, "TOKEN_FILE", token_file)
        assert agent_identity.is_token_fresh() is False


# ─────────────────── #2950-followup: on_complete (Rule 5 — continuous re-run) ───────────────────


class TestOnCompleteField:
    """#2950 follow-up: TaskContract-এ on_complete field — Rule 5 enforce."""

    def test_contract_has_on_complete_field(self):
        from scripts.agents.continuous_agent_loop import build_task_contract
        task = {"issue": 1, "title": "t", "labels": []}
        contract = build_task_contract("coder-1", "coder", task, "b")
        assert "on_complete" in contract

    def test_on_complete_action_is_rerun_script(self):
        """Default action = rerun_script (continuous execution per Rule 5)."""
        from scripts.agents.continuous_agent_loop import build_task_contract
        task = {"issue": 1, "title": "t", "labels": []}
        contract = build_task_contract("coder-1", "coder", task, "b")
        assert contract["on_complete"]["action"] == "rerun_script"

    def test_on_complete_condition_is_similar_tasks_remaining(self):
        from scripts.agents.continuous_agent_loop import build_task_contract
        task = {"issue": 1, "title": "t", "labels": []}
        contract = build_task_contract("coder-1", "coder", task, "b")
        assert contract["on_complete"]["condition"] == "similar_tasks_remaining"

    def test_on_complete_has_idle_wait_seconds(self):
        from scripts.agents.continuous_agent_loop import build_task_contract
        task = {"issue": 1, "title": "t", "labels": []}
        contract = build_task_contract("coder-1", "coder", task, "b")
        assert "idle_wait_seconds" in contract["on_complete"]
        assert contract["on_complete"]["idle_wait_seconds"] == 300  # 5 min

    def test_on_complete_has_description(self):
        from scripts.agents.continuous_agent_loop import build_task_contract
        task = {"issue": 1, "title": "t", "labels": []}
        contract = build_task_contract("coder-1", "coder", task, "b")
        assert "description" in contract["on_complete"]
        assert "Rule 5" in contract["on_complete"]["description"]

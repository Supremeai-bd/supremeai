#!/usr/bin/env python3
"""Contract tests for Persistent Branch Workflow (#4200).

বাংলা সারসংক্ষেপ:
------------------
#4200-র acceptance criteria-র জন্য contract tests:
  1. Branch state labels exist and are valid
  2. mark_branch_state transitions are correct
  3. MutationLease acquire/release works
  4. cleanup safety preserves active/paused/orphaned branches
  5. Branch discovery finds existing branches
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci.mark_branch_state import (
    VALID_STATES,
    STATE_LABELS,
    ALL_BRANCH_LABELS,
    mark_branch_state,
    discover_branch,
)
from scripts.ci.mutation_lease import MutationLease
from scripts.ci.cleanup_stale_branches import (
    PRESERVE_LABELS,
    extract_issue_number,
    is_branch_safe_to_delete,
)


class TestBranchStateLabels(unittest.TestCase):
    """Test #4200 §1: branch state labels exist and are valid."""

    def test_all_four_states_defined(self):
        """All 4 states from #4200 §2 are defined."""
        self.assertEqual(len(VALID_STATES), 4)
        self.assertIn("active", VALID_STATES)
        self.assertIn("paused", VALID_STATES)
        self.assertIn("orphaned", VALID_STATES)
        self.assertIn("ready", VALID_STATES)

    def test_state_labels_mapping(self):
        """Each state maps to correct label name."""
        self.assertEqual(STATE_LABELS["active"], "branch:active")
        self.assertEqual(STATE_LABELS["paused"], "branch:paused")
        self.assertEqual(STATE_LABELS["orphaned"], "branch:orphaned")
        self.assertEqual(STATE_LABELS["ready"], "branch:ready")

    def test_all_labels_in_set(self):
        """All branch labels are in ALL_BRANCH_LABELS set."""
        self.assertEqual(len(ALL_BRANCH_LABELS), 4)
        self.assertIn("branch:active", ALL_BRANCH_LABELS)
        self.assertIn("branch:paused", ALL_BRANCH_LABELS)
        self.assertIn("branch:orphaned", ALL_BRANCH_LABELS)
        self.assertIn("branch:ready", ALL_BRANCH_LABELS)


class TestBranchStateTransitions(unittest.TestCase):
    """Test #4200 §2: state transitions via mark_branch_state."""

    @patch("scripts.ci.mark_branch_state.get_gh_token", return_value="fake-token")
    @patch("scripts.ci.mark_branch_state.api_call")
    def test_mark_active_removes_old_labels(self, mock_api, mock_token):
        """Marking active removes old branch:* labels and adds branch:active."""
        # Mock: issue has branch:paused label
        mock_api.side_effect = [
            {"labels": [{"name": "branch:paused"}, {"name": "P1-high"}]},  # GET issue
            {},  # DELETE branch:paused
            {},  # POST add branch:active
            {},  # POST comment
        ]

        result = mark_branch_state(4200, "active", "agent/4200-test")
        self.assertTrue(result)

        # Verify DELETE was called for branch:paused
        calls = mock_api.call_args_list
        delete_calls = [c for c in calls if c.args[0] == "DELETE"]
        self.assertTrue(len(delete_calls) >= 1)

    @patch("scripts.ci.mark_branch_state.get_gh_token", return_value="fake-token")
    @patch("scripts.ci.mark_branch_state.api_call")
    def test_mark_ready_posts_comment(self, mock_api, mock_token):
        """Marking ready posts a comment with 'ready for PR' message."""
        mock_api.side_effect = [
            {"labels": []},  # GET issue (no branch labels)
            {},  # POST add branch:ready
            {},  # POST comment
        ]

        result = mark_branch_state(4200, "ready", "agent/4200-test")
        self.assertTrue(result)

    def test_invalid_state_rejected(self):
        """Invalid state returns False."""
        result = mark_branch_state(4200, "invalid", "agent/4200-test", token="fake")
        self.assertFalse(result)


class TestMutationLease(unittest.TestCase):
    """Test #4200 §6: mutation lease."""

    def test_acquire_succeeds_when_free(self):
        """Acquire succeeds when no existing lease."""
        with patch.object(MutationLease, "_load_leases", return_value={}):
            with patch.object(MutationLease, "_save_leases") as mock_save:
                lease = MutationLease("agent/4200-test", "coder-1", backend="local")
                self.assertTrue(lease.acquire())
                self.assertTrue(lease.acquired)
                mock_save.assert_called_once()

    def test_acquire_fails_when_held_by_other(self):
        """Acquire fails when another agent holds a fresh lease."""
        import time
        with patch.object(MutationLease, "_load_leases", return_value={
            "agent/4200-test": {
                "agent_id": "other-agent",
                "acquired_at": time.time(),
                "state": "MUTATING",
            }
        }):
            lease = MutationLease("agent/4200-test", "coder-1", backend="local")
            self.assertFalse(lease.acquire())

    def test_acquire_steals_stale_lease(self):
        """Acquire succeeds when existing lease is stale (> timeout)."""
        with patch.object(MutationLease, "_load_leases", return_value={
            "agent/4200-test": {
                "agent_id": "other-agent",
                "acquired_at": 0,  # epoch — very stale
                "state": "MUTATING",
            }
        }):
            with patch.object(MutationLease, "_save_leases"):
                lease = MutationLease("agent/4200-test", "coder-1", timeout=1, backend="local")
                self.assertTrue(lease.acquire())

    def test_release_clears_lease(self):
        """Release clears the lease."""
        with patch.object(MutationLease, "_load_leases", return_value={}):
            with patch.object(MutationLease, "_save_leases"):
                lease = MutationLease("agent/4200-test", "coder-1", backend="local")
                lease.acquire()
                lease.release()
                self.assertFalse(lease.acquired)

    def test_context_manager(self):
        """Context manager acquires and releases."""
        with patch.object(MutationLease, "_load_leases", return_value={}):
            with patch.object(MutationLease, "_save_leases"):
                with MutationLease("agent/4200-test", "coder-1", backend="local") as lease:
                    self.assertTrue(lease.acquired)
                self.assertFalse(lease.acquired)


class TestCleanupSafety(unittest.TestCase):
    """Test #4200 §9: cleanup preserves active/paused/orphaned branches."""

    def test_preserve_labels_set(self):
        """PRESERVE_LABELS contains the right labels."""
        self.assertIn("branch:active", PRESERVE_LABELS)
        self.assertIn("branch:paused", PRESERVE_LABELS)
        self.assertIn("branch:orphaned", PRESERVE_LABELS)
        self.assertNotIn("branch:ready", PRESERVE_LABELS)

    def test_extract_issue_number_agent_pattern(self):
        """Extract issue from agent/<issue>-<slug> pattern."""
        self.assertEqual(extract_issue_number("agent/4200-persistent-branch"), 4200)
        self.assertEqual(extract_issue_number("agent/123-fix"), 123)

    def test_extract_issue_number_slot_pattern(self):
        """Extract issue from coder-1-4200-slug pattern."""
        self.assertEqual(extract_issue_number("coder-1-4200-slug"), 4200)

    def test_extract_issue_number_no_match(self):
        """Returns None when no issue number found."""
        self.assertIsNone(extract_issue_number("main"))
        self.assertIsNone(extract_issue_number("develop"))

    @patch("scripts.ci.cleanup_stale_branches.get_issue_labels")
    @patch("scripts.ci.cleanup_stale_branches.get_pr_merge_state")
    def test_safe_to_delete_needs_labels_and_merge_proof(self, mock_pr, mock_labels):
        """#4204 corrected contract: no preserve labels is NOT enough —
        deletion additionally requires merged/completed proof."""
        mock_labels.return_value = {"P1-high", "status:in-progress"}
        # proof unavailable (PR API fails) → fail-closed, preserve
        mock_pr.return_value = None
        self.assertFalse(is_branch_safe_to_delete("agent/4200-test", "fake-token"))
        # merged PR proof present → safe
        mock_pr.return_value = "merged"
        self.assertTrue(is_branch_safe_to_delete("agent/4200-test", "fake-token"))

    @patch("scripts.ci.cleanup_stale_branches.get_issue_labels")
    @patch("scripts.ci.cleanup_stale_branches.get_pr_merge_state")
    def test_not_safe_to_delete_when_active(self, mock_pr, mock_labels):
        """Branch is NOT safe to delete when issue has branch:active."""
        mock_labels.return_value = {"P1-high", "branch:active"}
        mock_pr.return_value = "merged"
        self.assertFalse(is_branch_safe_to_delete("agent/4200-test", "fake-token"))

    @patch("scripts.ci.cleanup_stale_branches.get_issue_labels")
    @patch("scripts.ci.cleanup_stale_branches.get_pr_merge_state")
    def test_not_safe_to_delete_when_paused(self, mock_pr, mock_labels):
        """Branch is NOT safe to delete when issue has branch:paused."""
        mock_labels.return_value = {"branch:paused"}
        mock_pr.return_value = "merged"
        self.assertFalse(is_branch_safe_to_delete("coder-1-4200-test", "fake-token"))

    @patch("scripts.ci.cleanup_stale_branches.get_issue_labels")
    @patch("scripts.ci.cleanup_stale_branches.get_pr_merge_state")
    def test_not_safe_to_delete_when_orphaned(self, mock_pr, mock_labels):
        """Branch is NOT safe to delete when issue has branch:orphaned."""
        mock_labels.return_value = {"branch:orphaned"}
        mock_pr.return_value = "merged"
        self.assertFalse(is_branch_safe_to_delete("agent/4200-test", "fake-token"))


class TestBranchDiscovery(unittest.TestCase):
    """Test #4200 §3: branch discovery for session-independent continuation."""

    @patch("subprocess.run")
    def test_discover_finds_existing_branch(self, mock_run):
        """discover_branch returns branch name when it exists."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123\trefs/heads/agent/4200-persistent-branch\n",
        )

        result = discover_branch(4200, "fake-token")
        self.assertEqual(result, "agent/4200-persistent-branch")

    @patch("subprocess.run")
    def test_discover_returns_none_when_no_branch(self, mock_run):
        """discover_branch returns None when no branch exists."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        result = discover_branch(4200, "fake-token")
        self.assertIsNone(result)


# ═════════════════════════════════════════════════════════════════════════════
# #4207 — distributed MutationLease contract tests
# বাংলা: lease state আগে machine-local ফাইলে ছিল (runner-1-এর এজেন্ট runner-2-কে
# দেখত না)। এখন default backend = git-ref CAS (refs/leases/<branch>)। নিচের
# FakeLeaseGit একটি shared মেমরি-রিমোট সিমুলেট করে (প্রতি-ref CAS semantics
# সহ) — দুটি আলাদা store instance (দুই runner-এর অনুকরণ) একই ref-এ CAS করে।
# ═════════════════════════════════════════════════════════════════════════════

import json as _json
import subprocess as _sp
import time as _time

from scripts.ci.mutation_lease import (
    DEFAULT_TIMEOUT,
    GIT_BACKEND,
    LOCAL_BACKEND,
    LEASE_REF_PREFIX,
    LeaseRefStore,
    LeaseUnavailable,
    MutationLease,
    resolve_backend,
)

FAKE_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class FakeLeaseGit:
    """Shared in-memory git remote — প্রতি-ref CAS semantics সহ।

    বাংলা: non-force create of an EXISTING ref → reject (rc=1) — এটিই
    git-receive-pack-এর আসল আচরণ; commit-tree সময়েই sha→payload মনে রাখে,
    তাই show পথে আসল payload-ই ফেরত যায়।
    """

    def __init__(self):
        self.refs: dict[str, tuple[str, str]] = {}      # ref -> (sha, payload)
        self.commit_msg: dict[str, str] = {}            # sha -> payload
        self.calls: list[list[str]] = []

    def __call__(self, *args, **kwargs):
        # বাংলা: production LeaseRefStore._git(*git-args, timeout=..) — varargs;
        # timeout ইত্যাদি kwargs সিমুলেশনে অপ্রাসঙ্গিক। args list-এ normalize —
        # tuple-slice vs list তুলনা-ফাঁদ এড়াতে।
        args = list(args)
        self.calls.append(args)

        if args[:2] == ["commit-tree", FAKE_EMPTY_TREE]:
            payload = args[args.index("-m") + 1]
            sha = f"leasesha{len(self.commit_msg):04d}"
            self.commit_msg[sha] = payload
            return _sp.CompletedProcess(["git", *args], 0, stdout=sha + "\n", stderr="")

        if args[:1] == ["ls-remote"]:
            ref = args[2]
            if ref in self.refs:
                return _sp.CompletedProcess(["git", *args], 0, stdout=f"{self.refs[ref][0]}\t{ref}\n", stderr="")
            return _sp.CompletedProcess(["git", *args], 0, stdout="", stderr="")

        if args[:1] == ["fetch"]:
            spec = next(a for a in args if a.startswith("+"))
            remote_ref, local_ref = spec[1:].split(":", 1)
            if remote_ref in self.refs:
                self.refs[local_ref] = self.refs[remote_ref]
                return _sp.CompletedProcess(["git", *args], 0, stdout="", stderr="")
            return _sp.CompletedProcess(["git", *args], 1, stdout="", stderr="error: not found")

        if args[:1] == ["show"]:
            ref = args[-1]
            if ref in self.refs:
                sha, payload = self.refs[ref]
                return _sp.CompletedProcess(["git", *args], 0, stdout=f"1700000000\n{payload}\n", stderr="")
            return _sp.CompletedProcess(["git", *args], 1, stdout="", stderr="bad object")

        if args[:1] == ["push"]:
            force = "--force" in args
            spec = next(a for a in args if ":" in a and not a.startswith("--"))
            src, dst = spec.split(":", 1)
            if src == "" and dst in self.refs:  # ref delete
                del self.refs[dst]
                return _sp.CompletedProcess(["git", *args], 0, stdout="", stderr="")
            if dst in self.refs and not force:  # CAS: non-force create on existing → reject
                return _sp.CompletedProcess(["git", *args], 1, stdout="", stderr="! [rejected] (already exists)")
            self.refs[dst] = (src, self.commit_msg.get(src, "{}"))
            return _sp.CompletedProcess(["git", *args], 0, stdout="", stderr="")

        return _sp.CompletedProcess(["git", *args], 0, stdout="", stderr="")


class TestDistributedMutationLease4207(unittest.TestCase):
    """#4207: two simulated agents (separate store instances) cannot both acquire।"""

    BRANCH = "agent/4200-persistent"
    REF = LEASE_REF_PREFIX + "agent/4200-persistent"

    def _wire(self) -> tuple[FakeLeaseGit, LeaseRefStore, LeaseRefStore]:
        """দুটি store instance (দুই runner) — shared fake remote-এ।"""
        fake = FakeLeaseGit()
        stores = []
        for _ in range(2):
            store = LeaseRefStore(self.BRANCH)
            store._git = fake
            stores.append(store)
        return fake, stores[0], stores[1]

    def _payload(self, fake: FakeLeaseGit) -> dict:
        return _json.loads(fake.refs[self.REF][1])

    # ── the core #4207 acceptance criterion ──

    def test_two_agents_cannot_both_acquire(self):
        """বাংলা: দুই runner, একই branch — CAS-এ একজন-ই জেতে, দুজনে নয়।"""
        fake, a, b = self._wire()
        ok_a, _ = a.acquire("agent-A", timeout=DEFAULT_TIMEOUT)
        ok_b, holder = b.acquire("agent-B", timeout=DEFAULT_TIMEOUT)
        self.assertTrue(ok_a, "প্রথম এজেন্ট free store-এ acquire করে")
        self.assertFalse(ok_b, "দ্বিতীয় এজেন্ট একই ref-এ CAS হারায়")
        self.assertEqual(holder.get("agent_id"), "agent-A")

    def test_race_window_still_single_winner(self):
        """বাংলা: race window — B-এর read খালি দেখেও non-force push reject খায়।

        সিমুলেশন: B-এর ls-remote আগেই চলে গিয়ে খালি দেখলেও (A-এর push তখনো
        হয়নি ধরে নিয়ে) B-এর create-push A-এর push-এর পরে এলে reject হয়।
        FakeLeaseGit-এ create-অর্ডারই বিচারক — দুই create-এ দ্বিতীয়টি reject।
        """
        fake = FakeLeaseGit()
        a, b = LeaseRefStore(self.BRANCH), LeaseRefStore(self.BRANCH)
        a._git = b._git = fake
        # B আগে read করে (খালি দেখে), কিন্তু create-push পরে যায়:
        self.assertIsNone(b.read_lease())
        ok_a, _ = a.acquire("agent-A")
        ok_b, holder = b.acquire("agent-B")
        self.assertTrue(ok_a and not ok_b)
        self.assertEqual((holder or {}).get("agent_id"), "agent-A")

    def test_sequential_agents_see_each_other(self):
        fake, a, b = self._wire()
        a.acquire("agent-A")
        ok_b, holder = b.acquire("agent-B")
        self.assertFalse(ok_b)
        self.assertEqual(holder.get("agent_id"), "agent-A")

    def test_reentrant_acquire_by_same_agent(self):
        fake, a, _b = self._wire()
        ok1, _ = a.acquire("agent-A")
        ok2, again = a.acquire("agent-A")
        self.assertTrue(ok1 and ok2, "একই এজেন্টের re-acquire = idempotent True")
        self.assertEqual(again.get("agent_id"), "agent-A")

    def test_stale_foreign_lease_is_stolen(self):
        fake, a, b = self._wire()
        a.acquire("agent-A")
        # payload-এ acquired_at প্রাচীন করে দাও (epoch-ঘেঁষা = stale)
        stale = _json.dumps({"agent_id": "agent-A", "branch": self.BRANCH,
                             "acquired_at": 1, "state": "RESERVED"}, sort_keys=True)
        fake.refs[self.REF] = (fake.refs[self.REF][0], stale)
        ok_b, _ = b.acquire("agent-B", timeout=300)
        self.assertTrue(ok_b, "stale lease (>timeout) force-steal করা যায়")
        self.assertEqual(b.read_lease().get("agent_id"), "agent-B")

    def test_fresh_foreign_lease_not_stolen_before_timeout(self):
        fake, a, b = self._wire()
        a.acquire("agent-A")
        ok_b, _ = b.acquire("agent-B", timeout=3600)
        self.assertFalse(ok_b, "সতেজ lease timeout-এর আগে steal নয়")

    def test_release_is_holder_only_and_idempotent(self):
        fake, a, b = self._wire()
        a.acquire("agent-A")
        self.assertFalse(b.release("agent-B"), "হোল্ডার নয় — release refuse")
        self.assertTrue(a.release("agent-A"), "হোল্ডারের release True")
        self.assertTrue(a.release("agent-A"), "already-free release = idempotent True")
        self.assertIsNone(a.read_lease())

    def test_state_transition_holder_only(self):
        fake, a, b = self._wire()
        a.acquire("agent-A")
        original_at = self._payload(fake)["acquired_at"]
        self.assertTrue(a.update_state("agent-A", "MUTATING"))
        self.assertFalse(b.update_state("agent-B", "MUTATING"), "অ-হোল্ডার state বদলাতে পারে না")
        payload = self._payload(fake)
        self.assertEqual(payload["state"], "MUTATING")
        self.assertEqual(payload["acquired_at"], original_at,
                         "state-update stale-clock রিসেট করে না")

    # ── fail-closed contract (#4207 মূল বাগ-শ্রেণির বিরুদ্ধে) ──

    def test_network_failure_is_fail_closed_deny(self):
        fake, a, _b = self._wire()
        def dead_git(*args, **kwargs):
            return _sp.CompletedProcess(["git", *args], 1, stdout="", stderr="Could not resolve host")
        a._git = dead_git
        lease = MutationLease(self.BRANCH, "agent-A")  # default backend = git
        lease._ref_store = a
        self.assertFalse(lease.acquire(), "distributed store অপ্রাপ্য = acquire deny (fail-closed)")

    def test_read_lease_raises_on_network_failure(self):
        fake, a, _b = self._wire()
        def dead_git(*args, **kwargs):
            return _sp.CompletedProcess(["git", *args], 1, stdout="", stderr="offline")
        a._git = dead_git
        with self.assertRaises(LeaseUnavailable):
            a.read_lease()

    def test_no_silent_local_fallback_on_git_backend(self):
        """বাংলা: git backend ব্যর্থ হলে /tmp store-এ লেখা হয় না — সেটিই প্রমাণ।"""
        fake, a, _b = self._wire()
        def dead_git(*args, **kwargs):
            return _sp.CompletedProcess(["git", *args], 1, stdout="", stderr="offline")
        a._git = dead_git
        lease = MutationLease(self.BRANCH, "agent-A")
        lease._ref_store = a
        with patch.object(MutationLease, "_save_leases") as save_mock:
            lease.acquire()
        save_mock.assert_not_called()


class TestMutationLeaseBackendSelection4207(unittest.TestCase):
    """বাংলা: backend নির্বাচন চুক্তি — git default, local explicit, unknown ব্যর্থ।"""

    def setUp(self):
        os.environ.pop("SUPREMEAI_LEASE_BACKEND", None)

    def tearDown(self):
        os.environ.pop("SUPREMEAI_LEASE_BACKEND", None)

    def test_default_backend_is_distributed_git(self):
        self.assertEqual(resolve_backend(), GIT_BACKEND)
        lease = MutationLease("agent/4200-x", "a1")
        self.assertEqual(lease.backend, GIT_BACKEND)

    def test_local_is_explicit_opt_in(self):
        os.environ["SUPREMEAI_LEASE_BACKEND"] = "local"
        self.assertEqual(resolve_backend(), LOCAL_BACKEND)
        lease = MutationLease("agent/4200-x", "a1")
        self.assertEqual(lease.backend, LOCAL_BACKEND)

    def test_unknown_backend_fails_loud(self):
        os.environ["SUPREMEAI_LEASE_BACKEND"] = "redis"
        with self.assertRaises(ValueError):
            resolve_backend()

    def test_invalid_branch_name_rejected(self):
        with self.assertRaises(ValueError):
            LeaseRefStore("bad..branch-name")
        with self.assertRaises(ValueError):
            LeaseRefStore("/leading-slash")

    def test_two_local_store_instances_same_machine_mutex(self):
        """বাংলা: local backend — একই ফাইলে দুই instance = একই-মেশিন mutex (আগের চুক্তি)।"""
        with patch.object(MutationLease, "_load_leases", return_value={
            "agent/4200-x": {"agent_id": "A", "acquired_at": _time.time(), "state": "RESERVED"}}):
            b = MutationLease("agent/4200-x", "B", backend="local")
            self.assertFalse(b.acquire())


if __name__ == "__main__":
    unittest.main()

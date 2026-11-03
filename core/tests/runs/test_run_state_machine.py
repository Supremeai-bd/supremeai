"""M1-A — canonical Run lifecycle state machine tests (pure, offline).

Covers:
- the full happy-path lifecycle (user-approved verdict chain);
- EVERY edge declared in LEGAL_TRANSITIONS is legal (edge-matrix);
- unknown states rejected both sides;
- representative illegal transitions rejected (skip-ahead, resurrection,
  unsealed terminal mutation);
- retry guards (missing classification, non-retryable class, exhausted
  budget, valid retry);
- FINALIZED immutability + terminal helper consistency;
- retry classification enum: fixed 8-class set, retryability rules.
"""

from __future__ import annotations

import pytest

from runs import retry as run_retry
from runs import state_machine as sm

# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_full_lifecycle_chain(self):
        """REQUESTED → POLICY_CHECKED → PLANNED → RUNNING → SUCCEEDED → FINALIZED."""
        state = sm.REQUESTED
        for nxt in (
            sm.POLICY_CHECKED,
            sm.PLANNED,
            sm.RUNNING,
            sm.SUCCEEDED,
            sm.FINALIZED,
        ):
            state = sm.assert_transition(state, nxt)
        assert state == sm.FINALIZED

    def test_failed_path_with_retry_then_seal(self):
        """RUNNING → RETRYING → RUNNING → FAILED → FINALIZED (retry inside budget)."""
        state = sm.assert_transition(sm.RUNNING, sm.RETRYING, retry_class="transient")
        assert state == sm.RETRYING
        state = sm.assert_transition(state, sm.RUNNING)
        state = sm.assert_transition(state, sm.FAILED)
        assert sm.assert_transition(state, sm.FINALIZED) == sm.FINALIZED

    def test_hitl_path(self):
        """RUNNING → WAITING_APPROVAL → RUNNING (approval granted)."""
        state = sm.assert_transition(sm.RUNNING, sm.WAITING_APPROVAL)
        assert state == sm.WAITING_APPROVAL
        assert sm.assert_transition(state, sm.RUNNING) == sm.RUNNING

    def test_hitl_rejection_path(self):
        """WAITING_APPROVAL → FAILED (approval rejected) → FINALIZED."""
        state = sm.assert_transition(sm.RUNNING, sm.WAITING_APPROVAL)
        state = sm.assert_transition(state, sm.FAILED)
        assert sm.is_terminal(state)

    def test_degraded_recovers_and_succeeds(self):
        """RUNNING → DEGRADED → RUNNING → SUCCEEDED."""
        state = sm.assert_transition(sm.RUNNING, sm.DEGRADED)
        state = sm.assert_transition(state, sm.RUNNING)
        assert sm.assert_transition(state, sm.SUCCEEDED) == sm.SUCCEEDED

    def test_blocked_from_policy_and_unblock(self):
        """POLICY_CHECKED → BLOCKED → RUNNING (external resolution)."""
        state = sm.assert_transition(sm.POLICY_CHECKED, sm.BLOCKED)
        assert sm.assert_transition(state, sm.RUNNING) == sm.RUNNING

    def test_cancellation_from_every_non_terminal_state(self):
        """Cancellation legal from every pre-execution + running-cluster state."""
        cancellable = sm.PRE_EXECUTION_STATES | sm.RUNNING_CLUSTER
        assert cancellable == {
            sm.REQUESTED,
            sm.POLICY_CHECKED,
            sm.PLANNED,
            sm.RUNNING,
            sm.WAITING_APPROVAL,
            sm.RETRYING,
            sm.DEGRADED,
            sm.BLOCKED,
        }
        for state in sorted(cancellable):
            assert sm.CANCELLED in sm.LEGAL_TRANSITIONS[state], state


# ---------------------------------------------------------------------------
# Edge matrix + unknown states
# ---------------------------------------------------------------------------


class TestEdgeMatrix:
    def test_every_declared_edge_is_legal(self):
        """Each (state, nxt) pair in LEGAL_TRANSITIONS passes assert_transition."""
        for current, allowed in sm.LEGAL_TRANSITIONS.items():
            for nxt in sorted(allowed):
                if current == sm.RUNNING and nxt == sm.RETRYING:
                    # retry edge needs its guard inputs
                    assert (
                        sm.assert_transition(
                            current, nxt, retry_class="transient", retries_used=0, max_retries=3
                        )
                        == nxt
                    )
                else:
                    assert sm.assert_transition(current, nxt) == nxt

    def test_unknown_current_state_rejected(self):
        with pytest.raises(sm.IllegalTransition, match="unknown current run state"):
            sm.assert_transition("flying", sm.RUNNING)

    def test_unknown_next_state_rejected(self):
        with pytest.raises(sm.IllegalTransition, match="unknown next run state"):
            sm.assert_transition(sm.REQUESTED, "flying")


# ---------------------------------------------------------------------------
# Illegal transitions
# ---------------------------------------------------------------------------


class TestIllegalTransitions:
    def test_skip_ahead_rejected(self):
        """REQUESTED → PLANNED (policy check must happen) is illegal."""
        with pytest.raises(sm.IllegalTransition, match="illegal run transition"):
            sm.assert_transition(sm.REQUESTED, sm.PLANNED)

    def test_running_to_planned_rejected(self):
        with pytest.raises(sm.IllegalTransition):
            sm.assert_transition(sm.RUNNING, sm.PLANNED)

    def test_planned_cannot_succeed(self):
        """No execution, no success."""
        with pytest.raises(sm.IllegalTransition):
            sm.assert_transition(sm.PLANNED, sm.SUCCEEDED)

    def test_resurrection_from_terminal_rejected(self):
        with pytest.raises(sm.IllegalTransition):
            sm.assert_transition(sm.FAILED, sm.RUNNING)
        with pytest.raises(sm.IllegalTransition):
            sm.assert_transition(sm.SUCCEEDED, sm.RETRYING)
        with pytest.raises(sm.IllegalTransition):
            sm.assert_transition(sm.CANCELLED, sm.RUNNING)

    def test_finalized_is_frozen(self):
        for nxt in sm.STATES:
            with pytest.raises(sm.IllegalTransition):
                sm.assert_transition(sm.FINALIZED, nxt)


# ---------------------------------------------------------------------------
# Retry guards
# ---------------------------------------------------------------------------


class TestRetryGuards:
    def test_retry_without_classification_rejected(self):
        with pytest.raises(sm.IllegalTransition, match="requires a retry_class"):
            sm.assert_transition(sm.RUNNING, sm.RETRYING)

    def test_retry_with_non_retryable_class_rejected(self):
        for cls in ("policy_blocked", "invalid_input", "deterministic", "approval_required"):
            with pytest.raises(sm.IllegalTransition, match="not retryable"):
                sm.assert_transition(sm.RUNNING, sm.RETRYING, retry_class=cls)

    @pytest.mark.parametrize("cls", run_retry.RETRYABLE_CLASSES)
    def test_retry_with_retryable_class_within_budget_ok(self, cls):
        assert (
            sm.assert_transition(
                sm.RUNNING, sm.RETRYING, retry_class=cls, retries_used=1, max_retries=3
            )
            == sm.RETRYING
        )

    def test_retry_with_exhausted_budget_rejected(self):
        with pytest.raises(sm.IllegalTransition, match="retry budget exhausted"):
            sm.assert_transition(
                sm.RUNNING,
                sm.RETRYING,
                retry_class="transient",
                retries_used=3,
                max_retries=3,
            )

    def test_retry_without_cap_never_exhausts(self):
        assert (
            sm.assert_transition(
                sm.RUNNING,
                sm.RETRYING,
                retry_class="rate_limited",
                retries_used=50,
                max_retries=None,
            )
            == sm.RETRYING
        )

    def test_retry_edge_only_from_running(self):
        """RETRYING is not reachable from pre-execution states."""
        with pytest.raises(sm.IllegalTransition):
            sm.assert_transition(sm.PLANNED, sm.RETRYING, retry_class="transient")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_terminal_set(self):
        assert sm.is_terminal(sm.SUCCEEDED)
        assert sm.is_terminal(sm.FAILED)
        assert sm.is_terminal(sm.CANCELLED)
        assert sm.is_terminal(sm.FINALIZED)
        assert not sm.is_terminal(sm.RUNNING)
        assert not sm.is_terminal(sm.REQUESTED)

    def test_active_cluster(self):
        for state in sm.RUNNING_CLUSTER:
            assert sm.is_active(state)
        assert not sm.is_active(sm.PLANNED)
        assert not sm.is_active(sm.FAILED)

    def test_immutable(self):
        assert sm.is_immutable(sm.FINALIZED)
        assert not sm.is_immutable(sm.FAILED)

    def test_every_state_has_transition_entry(self):
        """No hidden states: STATES ↔ LEGAL_TRANSITIONS keys are identical."""
        assert set(sm.STATES) == set(sm.LEGAL_TRANSITIONS)

    def test_terminal_states_have_only_seal_or_nothing(self):
        for state in sm.TERMINAL_STATES:
            outgoing = sm.LEGAL_TRANSITIONS[state]
            assert outgoing <= {sm.FINALIZED}, state


# ---------------------------------------------------------------------------
# Retry classification (runs/retry.py)
# ---------------------------------------------------------------------------


class TestRetryClassification:
    def test_fixed_eight_class_enum(self):
        """The roadmap's fixed 8-class set — no more, no less."""
        assert {rc.value for rc in run_retry.RetryClass} == {
            "transient",
            "rate_limited",
            "dependency_unavailable",
            "policy_blocked",
            "invalid_input",
            "deterministic",
            "resource_exhausted",
            "approval_required",
        }

    def test_retryable_set_matches_spec(self):
        assert {
            "transient",
            "rate_limited",
            "dependency_unavailable",
            "resource_exhausted",
        } == run_retry.RETRYABLE_CLASSES

    def test_none_is_never_retryable(self):
        assert run_retry.is_retryable(None) is False

    def test_str_and_enum_roundtrip(self):
        assert run_retry.is_retryable("transient")
        assert run_retry.is_retryable(run_retry.RetryClass.rate_limited)
        assert not run_retry.is_retryable("invalid_input")

    def test_approval_required_maps_to_waiting_approval(self):
        assert run_retry.maps_to_waiting_approval("approval_required")
        assert run_retry.maps_to_waiting_approval(run_retry.RetryClass.approval_required)
        assert not run_retry.maps_to_waiting_approval("transient")
        assert not run_retry.maps_to_waiting_approval(None)

    def test_state_machine_guard_uses_same_retryable_set(self):
        """No drift between retry.py truth and the state-machine guard."""
        # A class marked retryable in retry.py must pass the guard, and any
        # non-retryable class must fail it (spot both directions).
        for cls in run_retry.RetryClass:
            if run_retry.is_retryable(cls):
                assert (
                    sm.assert_transition(sm.RUNNING, sm.RETRYING, retry_class=str(cls))
                    == sm.RETRYING
                )
            else:
                with pytest.raises(sm.IllegalTransition):
                    sm.assert_transition(sm.RUNNING, sm.RETRYING, retry_class=str(cls))

"""M1-B — budget enforcement tests (pure, offline).

Covers the roadmap M1 budget contract: wall-clock / token / tool-call /
retry — plain columns + pure enforcement helper, colibrì-free.

Semantics under test:
- ``None`` cap = uncapped dimension (never violates);
- consuming EXACTLY the budget is legal, exceeding is not;
- all violations reported together (not first-only);
- admission control projects the would-be consumption BEFORE spending;
- retry-budget predicate matches the state-machine guard semantics.
"""

from __future__ import annotations

import pytest

from runs.budgets import (
    BudgetDimension,
    BudgetSnapshot,
    can_admit_attempt,
    can_retry,
    check_budgets,
)


class TestCheckBudgets:
    def test_all_within_budget_ok(self):
        v = check_budgets(
            BudgetSnapshot(
                max_wall_clock_ms=30_000,
                max_tokens=1_000,
                max_tool_calls=10,
                max_retries=3,
                tokens_used=999,
                tool_calls_used=10,
                retries_used=3,
                wall_clock_ms_used=29_999,
            )
        )
        assert v.ok
        assert v.violations == ()

    def test_uncapped_never_violates(self):
        v = check_budgets(
            BudgetSnapshot(
                max_wall_clock_ms=None,
                max_tokens=None,
                max_tool_calls=None,
                max_retries=None,
                tokens_used=10**9,
                tool_calls_used=10**9,
                retries_used=10**9,
                wall_clock_ms_used=10**9,
            )
        )
        assert v.ok

    def test_exact_consumption_is_legal(self):
        v = check_budgets(
            BudgetSnapshot(max_tokens=100, tokens_used=100, max_tool_calls=5, tool_calls_used=5)
        )
        assert v.ok

    def test_each_dimension_violates_individually(self):
        # tokens
        v = check_budgets(BudgetSnapshot(max_tokens=10, tokens_used=11))
        assert not v.ok and v.violations == (BudgetDimension.tokens,)
        # tool calls
        v = check_budgets(BudgetSnapshot(max_tool_calls=2, tool_calls_used=3))
        assert not v.ok and v.violations == (BudgetDimension.tool_calls,)
        # wall clock
        v = check_budgets(BudgetSnapshot(max_wall_clock_ms=1_000, wall_clock_ms_used=1_001))
        assert not v.ok and v.violations == (BudgetDimension.wall_clock,)
        # retries
        v = check_budgets(BudgetSnapshot(max_retries=1, retries_used=2))
        assert not v.ok and v.violations == (BudgetDimension.retries,)

    def test_all_violations_reported_together(self):
        v = check_budgets(
            BudgetSnapshot(
                max_wall_clock_ms=1,
                max_tokens=1,
                max_tool_calls=1,
                max_retries=1,
                tokens_used=2,
                tool_calls_used=2,
                retries_used=2,
                wall_clock_ms_used=2,
            )
        )
        assert v.violations == (
            BudgetDimension.wall_clock,
            BudgetDimension.tokens,
            BudgetDimension.tool_calls,
            BudgetDimension.retries,
        )

    def test_verdict_detail_lists_dimension_names(self):
        v = check_budgets(BudgetSnapshot(max_tokens=0, tokens_used=1))
        assert v.as_detail() == {"violations": ["tokens"]}

    def test_snapshot_as_detail_covers_all_fields(self):
        d = BudgetSnapshot(max_tokens=5).as_detail()
        assert set(d) == {
            "max_wall_clock_ms",
            "max_tokens",
            "max_tool_calls",
            "max_retries",
            "tokens_used",
            "tool_calls_used",
            "retries_used",
            "wall_clock_ms_used",
        }


class TestAdmissionControl:
    def test_attempt_fits(self):
        snap = BudgetSnapshot(max_tool_calls=3, tool_calls_used=2)
        assert can_admit_attempt(snap, extra_tool_calls=1).ok

    def test_attempt_would_exceed_refused(self):
        snap = BudgetSnapshot(max_tool_calls=3, tool_calls_used=2)
        v = can_admit_attempt(snap, extra_tool_calls=1 + 1)
        assert not v.ok and v.violations == (BudgetDimension.tool_calls,)

    def test_admission_never_mutates_snapshot(self):
        snap = BudgetSnapshot(max_tokens=10, tokens_used=9)
        can_admit_attempt(snap, extra_tokens=5)  # refused projection
        assert snap.tokens_used == 9  # unchanged

    def test_frozen_snapshot_immutable(self):
        snap = BudgetSnapshot(max_tokens=1)
        with pytest.raises(Exception):  # FrozenInstanceError
            snap.tokens_used = 5  # type: ignore[misc]


class TestRetryBudgetPredicate:
    def test_matches_state_machine_semantics(self):
        assert can_retry(BudgetSnapshot(max_retries=None, retries_used=999))
        assert can_retry(BudgetSnapshot(max_retries=3, retries_used=2))
        assert not can_retry(BudgetSnapshot(max_retries=3, retries_used=3))
        assert not can_retry(BudgetSnapshot(max_retries=3, retries_used=5))

"""Tests for core.evolution.merge_learning_learner (#1939)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from core.evolution.merge_learning_learner import learn_from_merge_reports


class _FakeFitnessEngine:
    """Minimal FitnessEngine stub recording track_execution calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, bool, float]] = []

    def track_execution(self, skill_name: str, success: bool, latency: float) -> None:
        self.calls.append((skill_name, success, latency))


@pytest.fixture
def fake_fitness() -> _FakeFitnessEngine:
    return _FakeFitnessEngine()


@pytest.fixture
def recent_merges():
    """3 merges in the last 24h: 2 held (coder, ci), 1 clean (coder)."""
    now_iso = datetime.now(UTC).isoformat()
    return [
        {
            "pr_number": 100,
            "lane": "coder",
            "merged_at": now_iso,
            "held_history": [{"reason": "conflict"}, {"reason": "scope"}],  # 2 holds
        },
        {
            "pr_number": 101,
            "lane": "coder",
            "merged_at": now_iso,
            "held_history": [],  # clean
        },
        {
            "pr_number": 102,
            "lane": "ci",
            "merged_at": now_iso,
            "held_history": [{"reason": "format"}],  # 1 hold
        },
    ]


@pytest.fixture
def old_merge():
    """A merge older than the lookback window — must be ignored."""
    old_iso = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    return {
        "pr_number": 50,
        "lane": "coder",
        "merged_at": old_iso,
        "held_history": [{"reason": "ancient"}],
    }


@pytest.mark.asyncio
async def test_learn_aggregates_by_lane(fake_fitness, recent_merges):
    """Held entries → failures, clean merges → successes, per lane."""
    with patch(
        "models.merge_learning_report.list_merge_learning",
        new=AsyncMock(return_value=recent_merges),
    ):
        summary = await learn_from_merge_reports(
            fake_fitness, lookback_days=7, hold_penalty=1.0, clean_reward=1.0
        )

    # coder: 2 holds + 1 clean → 2 failures + 1 success
    assert "coder:merge-execution" in summary
    assert summary["coder:merge-execution"]["holds"] == 2
    assert summary["coder:merge-execution"]["cleans"] == 1

    # ci: 1 hold → 1 failure
    assert "ci:merge-execution" in summary
    assert summary["ci:merge-execution"]["holds"] == 1
    assert summary["ci:merge-execution"]["cleans"] == 0

    # track_execution called: coder 3x (2 fail + 1 success), ci 1x (1 fail)
    coder_calls = [c for c in fake_fitness.calls if c[0] == "coder:merge-execution"]
    assert len(coder_calls) == 3
    assert sum(1 for c in coder_calls if not c[1]) == 2  # 2 failures
    assert sum(1 for c in coder_calls if c[1]) == 1  # 1 success

    ci_calls = [c for c in fake_fitness.calls if c[0] == "ci:merge-execution"]
    assert len(ci_calls) == 1
    assert not ci_calls[0][1]  # failure


@pytest.mark.asyncio
async def test_learn_respects_lookback_window(fake_fitness, recent_merges, old_merge):
    """Merges older than lookback_days are ignored."""
    all_rows = recent_merges + [old_merge]
    with patch(
        "models.merge_learning_report.list_merge_learning", new=AsyncMock(return_value=all_rows)
    ):
        summary = await learn_from_merge_reports(
            fake_fitness, lookback_days=7, hold_penalty=1.0, clean_reward=1.0
        )

    # The old merge (pr 50) must NOT appear — coder holds should stay at 2 (not 3)
    assert summary["coder:merge-execution"]["holds"] == 2


@pytest.mark.asyncio
async def test_learn_applies_config_weights(fake_fitness, recent_merges):
    """Fractional weights round down (int(0.5 × 2) = 1 call)."""
    with patch(
        "models.merge_learning_report.list_merge_learning",
        new=AsyncMock(return_value=recent_merges),
    ):
        await learn_from_merge_reports(
            fake_fitness, lookback_days=7, hold_penalty=0.5, clean_reward=0.5
        )

    # coder: 2 holds × 0.5 = 1.0 → 1 failure call; 1 clean × 0.5 = 0.5 → 0 success calls
    coder_calls = [c for c in fake_fitness.calls if c[0] == "coder:merge-execution"]
    assert len(coder_calls) == 1  # only 1 failure (int(2 * 0.5) = 1)


@pytest.mark.asyncio
async def test_learn_handles_null_lane(fake_fitness, recent_merges):
    """NULL lane → 'unknown:merge-execution' skill."""
    recent_merges.append(
        {
            "pr_number": 103,
            "lane": None,
            "merged_at": datetime.now(UTC).isoformat(),
            "held_history": [],
        }
    )
    with patch(
        "models.merge_learning_report.list_merge_learning",
        new=AsyncMock(return_value=recent_merges),
    ):
        summary = await learn_from_merge_reports(
            fake_fitness, lookback_days=7, hold_penalty=1.0, clean_reward=1.0
        )

    assert "unknown:merge-execution" in summary
    assert summary["unknown:merge-execution"]["cleans"] == 1


@pytest.mark.asyncio
async def test_learn_handles_string_held_history(fake_fitness, recent_merges):
    """held_history may arrive as a JSON string (some DB drivers)."""
    recent_merges[0]["held_history"] = json.dumps([{"reason": "conflict"}])
    with patch(
        "models.merge_learning_report.list_merge_learning",
        new=AsyncMock(return_value=recent_merges),
    ):
        summary = await learn_from_merge_reports(
            fake_fitness, lookback_days=7, hold_penalty=1.0, clean_reward=1.0
        )

    # coder: 1 hold (from JSON string) + 1 clean
    assert summary["coder:merge-execution"]["holds"] == 1


@pytest.mark.asyncio
async def test_learn_skips_when_db_unavailable(fake_fitness):
    """If list_merge_learning raises, the function returns {} (graceful skip)."""
    with patch(
        "models.merge_learning_report.list_merge_learning",
        new=AsyncMock(side_effect=RuntimeError("DB down")),
    ):
        summary = await learn_from_merge_reports(fake_fitness, lookback_days=7)

    assert summary == {}
    assert fake_fitness.calls == []  # no mutations


@pytest.mark.asyncio
async def test_learn_empty_when_no_recent(fake_fitness):
    """No merges in window → empty summary, no track_execution calls."""
    with patch("models.merge_learning_report.list_merge_learning", new=AsyncMock(return_value=[])):
        summary = await learn_from_merge_reports(fake_fitness, lookback_days=7)

    assert summary == {}
    assert fake_fitness.calls == []

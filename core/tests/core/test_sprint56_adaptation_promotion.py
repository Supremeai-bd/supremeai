"""Sprint 5/6 regression tests — bounded adaptation + promotion gates.

Covers the Self-Evolution Zero-Cost plan:
  * provider scoring: measured inputs only, sample tiers (§7.2), insufficient
    evidence can never be preferred (§8.1), exploration candidate (§8.2)
  * request coalescing: leader/follower, bounded wait, cancellation handling,
    bounded map (§13.3)
  * smart TTL: bounded multipliers (§13.2)
  * adaptive threshold: bounds, change-rate limit, min samples (§7.3)
  * promotion: rollback-target rule (§19) — no rollback target = no promotion
"""

from __future__ import annotations

import asyncio

import pytest

from core.learning.dedup import RequestCoalescer, dedup_key
from core.learning.policies import (
    MAX_TTL_MULTIPLIER,
    MIN_TTL_MULTIPLIER,
    adaptive_threshold,
    smart_ttl,
)
from core.learning.provider_scorer import (
    exploration_candidate,
    get_adaptive_routing_enabled,
    refresh_score_snapshot,
)

# ----------------------------------------------------------- provider scoring


def _metric_row(
    provider: str,
    model: str,
    requests: int,
    successes: int,
    rate_limited: int = 0,
    p95: int | None = 500,
    cost: float = 0.001,
) -> dict:
    return {
        "provider": provider,
        "model": model,
        "window_start": "2026-09-02T10:00:00+00:00",
        "requests": requests,
        "successes": successes,
        "failures": requests - successes,
        "rate_limited": rate_limited,
        "latency_p50_ms": 300,
        "latency_p95_ms": p95,
        "estimated_cost": cost,
        "actual_cost": cost,
    }


def test_insufficient_samples_never_preferred() -> None:
    scores = refresh_score_snapshot(
        [
            _metric_row("tiny", "tiny/m1", requests=5, successes=5),  # insufficient
            _metric_row("solid", "solid/m1", requests=100, successes=92),
        ]
    )
    by_provider = {s.provider: s for s in scores}
    assert by_provider["tiny"].sample_tier == "insufficient"
    assert by_provider["tiny"].score == 0.0
    assert by_provider["solid"].sample_tier == "normal"
    assert by_provider["solid"].score > by_provider["tiny"].score  # §8.1


def test_cautious_tier_discounted() -> None:
    scores = refresh_score_snapshot([_metric_row("mid", "mid/m1", requests=30, successes=29)])
    assert scores[0].sample_tier == "cautious"
    assert scores[0].score <= 0.5 + 1e-6  # discounted 50% of bounded raw


def test_exploration_candidate_returns_alternative() -> None:
    scores = refresh_score_snapshot(
        [
            _metric_row("leader", "leader/m1", requests=100, successes=95),
            _metric_row("alt", "alt/m1", requests=60, successes=50),
        ]
    )
    candidate = exploration_candidate(scores)
    assert candidate is not None
    assert candidate.provider == "alt"  # never the leader (§8.2)
    # single measured provider → no exploration possible
    assert exploration_candidate(scores[:1]) is None


def test_adaptive_routing_flag_switchable_default_true(monkeypatch: pytest.MonkeyPatch) -> None:
    # M05 P-A দ্বিতীয় অর্ধ: সুইটেবল-ডিফল্ট true; kill-switch অক্ষত; অজানা-মান
    # fail-closed।
    monkeypatch.delenv("ENABLE_ADAPTIVE_ROUTING", raising=False)
    assert get_adaptive_routing_enabled() is True  # default: bounded খোলা
    monkeypatch.setenv("ENABLE_ADAPTIVE_ROUTING", "true")
    assert get_adaptive_routing_enabled() is True
    monkeypatch.setenv("ENABLE_ADAPTIVE_ROUTING", "false")  # kill-switch
    assert get_adaptive_routing_enabled() is False
    monkeypatch.setenv("ENABLE_ADAPTIVE_ROUTING", "garbage")  # fail-closed
    assert get_adaptive_routing_enabled() is False


def test_exploration_candidate_never_explores_on_thin_evidence() -> None:
    # M05 P-A sample-tier guardrail: cautious/insufficient প্রমাণ কখনো
    # exploration-এ যায় না — কেবল normal-tier (≥50 observation)।
    scores = refresh_score_snapshot(
        [
            _metric_row("lead_c", "lead_c/m1", requests=30, successes=29),  # cautious
            _metric_row("alt_c", "alt_c/m1", requests=20, successes=18),  # cautious
        ]
    )
    assert exploration_candidate(scores) is None  # পাতলা প্রমাণে নীরব অন্বেষণ নয়

    mixed = refresh_score_snapshot(
        [
            _metric_row("tiny", "tiny/m1", requests=5, successes=5),  # insufficient
            _metric_row("solid", "solid/m1", requests=100, successes=92),  # normal
        ]
    )
    assert exploration_candidate(mixed) is None  # <2 normal-tier → অন্বেষণ অসম্ভব


# ------------------------------------------------------------- dedup


@pytest.mark.asyncio
async def test_coalescer_leader_follower_share_response() -> None:
    coalescer = RequestCoalescer()
    key = dedup_key("m", "chat", [{"role": "user", "content": "hello"}])

    leader_entry = coalescer.try_claim(key)
    assert leader_entry is None  # first caller becomes the leader

    async def follower() -> dict | None:
        entry = coalescer.try_claim(key)
        assert entry is not None
        return await coalescer.wait_for_leader(entry)

    follower_task = asyncio.create_task(follower())
    await asyncio.sleep(0.01)
    coalescer.publish_success(key, {"success": True, "text": "shared"})
    shared = await follower_task
    assert shared == {"success": True, "text": "shared"}


@pytest.mark.asyncio
async def test_coalescer_timeout_degrades_to_execute() -> None:
    coalescer = RequestCoalescer(follower_timeout=0.05)
    key = "k-timeout"
    assert coalescer.try_claim(key) is None  # leader never publishes
    entry = coalescer.try_claim(key)
    assert entry is not None
    assert await coalescer.wait_for_leader(entry) is None  # bounded → execute


@pytest.mark.asyncio
async def test_coalescer_leader_failure_follower_executes() -> None:
    coalescer = RequestCoalescer()
    key = "k-fail"
    coalescer.try_claim(key)
    entry = coalescer.try_claim(key)
    assert entry is not None
    coalescer.publish_failure(key, RuntimeError("leader exploded"))
    assert await coalescer.wait_for_leader(entry) is None


def test_coalescer_map_bounded() -> None:
    coalescer = RequestCoalescer(max_inflight=3)
    for i in range(10):
        coalescer.try_claim(f"k{i}")
    assert len(coalescer._inflight) <= 3


# ------------------------------------------------------------- policies


def test_smart_ttl_bounded() -> None:
    base = 3600
    # perfect hit rate + reuse → at most 2x
    assert smart_ttl(base, hit_rate=1.0, reuse_count=100) == int(base * MAX_TTL_MULTIPLIER)
    # zero hits → at most 0.5x
    assert smart_ttl(base, hit_rate=0.0, reuse_count=100) == int(base * MIN_TTL_MULTIPLIER)
    # no reuse evidence → never grows
    assert smart_ttl(base, hit_rate=0.9, reuse_count=1) == base
    assert smart_ttl(base, hit_rate=0.0, reuse_count=0) == int(base * MIN_TTL_MULTIPLIER)


def test_adaptive_threshold_bounds_and_min_samples() -> None:
    baseline = 0.8
    # insufficient evidence → unchanged (plan Principle 1)
    assert adaptive_threshold(baseline, [0.9, 0.95], min_bound=0.5, max_bound=0.95) == baseline
    # strong history → moves toward median but within change-rate + bounds
    history = [0.6] * 50
    adjusted = adaptive_threshold(baseline, history, min_bound=0.5, max_bound=0.95)
    assert baseline - 0.05 <= adjusted < baseline  # change-rate limited
    assert 0.5 <= adjusted <= 0.95  # absolute bounds
    # extremes can never exceed bounds
    assert adaptive_threshold(0.94, [1.0] * 100, min_bound=0.5, max_bound=0.95) <= 0.95
    assert adaptive_threshold(0.51, [0.0] * 100, min_bound=0.5, max_bound=0.95) >= 0.5

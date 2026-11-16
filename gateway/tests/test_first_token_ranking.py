"""Phase-2 regression tests: rank candidates by time-to-first-token latency.

A slot that has served streaming requests records an EWMA first-token latency
(``ewma_first_token_ms``); ranking must prefer that over the general
``ewma_latency_ms`` so a provider slow to produce its first token is deprioritised
even if its overall call latency looks fine.
"""

from gateway.service.adaptive_routing import RouteSnapshot, route_score
from gateway.service.pool import KeySlot, ProviderKeyPool


def _make_pool(slots):
    pool = ProviderKeyPool.__new__(ProviderKeyPool)
    pool.provider = "test"
    pool.prefixes = ["TEST_API_KEY"]
    pool.slots = slots
    pool._index = 0
    return pool


def test_rank_latency_prefers_first_token():
    slot = KeySlot(name="k", key="x", provider="p")
    assert slot.rank_latency_ms == 0.0
    slot.ewma_latency_ms = 500.0
    assert slot.rank_latency_ms == 500.0  # fallback when no first-token data
    slot.ewma_first_token_ms = 120.0
    assert slot.rank_latency_ms == 120.0  # first-token wins once known


def test_report_success_updates_first_token_ewma():
    pool = _make_pool([])
    slot = KeySlot(name="k", key="x", provider="test", ewma_latency_ms=300.0)
    pool.report_success(slot, latency_ms=200.0, first_token_ms=100.0)
    assert slot.ewma_latency_ms == 270.0  # 300*0.7 + 200*0.3
    assert slot.ewma_first_token_ms == 100.0


def test_report_success_without_first_token_leaves_it_zero():
    pool = _make_pool([])
    slot = KeySlot(name="k", key="x", provider="test", ewma_latency_ms=300.0)
    pool.report_success(slot, latency_ms=200.0)
    assert slot.ewma_first_token_ms == 0.0


def test_report_injury_raises_first_token_estimate():
    pool = _make_pool([])
    slot = KeySlot(name="k", key="x", provider="test", ewma_first_token_ms=100.0)
    pool.report_injury(slot, status_code=504, latency_ms=8000.0)
    assert slot.ewma_first_token_ms > 100.0


def test_pool_ranks_by_first_token_over_general_latency():
    # slow: great overall latency but terrible first-token latency.
    slow = KeySlot(
        name="slow", key="b", provider="test",
        ewma_first_token_ms=2000.0, ewma_latency_ms=100.0,
        free_limit=100, remaining_free=100,
    )
    fast = KeySlot(
        name="fast", key="a", provider="test",
        ewma_first_token_ms=100.0, ewma_latency_ms=100.0,
        free_limit=100, remaining_free=100,
    )
    pool = _make_pool([slow, fast])
    assert pool.get_next_key().name == "fast"


def test_route_score_prefers_lower_first_token():
    fast = RouteSnapshot(name="fast", latency_ms=100.0, remaining=100, limit=100)
    slow = RouteSnapshot(name="slow", latency_ms=2000.0, remaining=100, limit=100)
    assert route_score(fast) > route_score(slow)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
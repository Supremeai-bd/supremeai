from gateway.service.adaptive_routing import RouteSnapshot, choose_route, route_score
from gateway.service.pool import FederationSquad


def test_route_prefers_remaining_free_budget_over_unknown_quota_when_latency_is_close():
    known = RouteSnapshot("known", latency_ms=100, remaining=80, limit=100)
    unknown = RouteSnapshot("unknown", latency_ms=100)
    assert route_score(known) > route_score(unknown)
    assert choose_route([known, unknown]) == "known"


def test_route_skips_exhausted_budget():
    assert choose_route([
        RouteSnapshot("exhausted", remaining=0, limit=100),
        RouteSnapshot("healthy", remaining=2, limit=100),
    ]) == "healthy"


def test_pool_ranks_keys_by_latency_and_quota_without_provider_order(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g" * 20)
    monkeypatch.setenv("GEMINI_API_KEY", "e" * 20)
    monkeypatch.setenv("SUPREMEAI_FREE_LIMIT_GROQ", "10")
    monkeypatch.setenv("SUPREMEAI_FREE_LIMIT_GEMINI", "100")
    squad = FederationSquad()
    groq = squad.pools["groq"].slots[0]
    gemini = squad.pools["gemini"].slots[0]
    groq.ewma_latency_ms = 10
    gemini.ewma_latency_ms = 10
    groq.remaining_free = 2
    candidates = squad.get_candidate_slots()
    assert candidates[0][0] == "gemini"

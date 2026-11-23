"""HTTP 402 withdraws a model, even if it remains in the local approval list."""

from gateway.service.free_route_policy import ApprovedRoute
from gateway.service.providers import adapters


def test_paid_avoid_cannot_be_bypassed_by_client_or_slot_preference(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(adapters, "approved_route", lambda provider, url, _key, **_kw: ApprovedRoute((provider, url, "fixture-tag"), ("paid-fixture", "other-approved")))
    monkeypatch.setattr(adapters, "_PAID_MODELS", {("groq", "paid-fixture")})
    slot = SimpleNamespace(preferred_model="paid-fixture")
    assert adapters._resolve_candidate_models("groq", "fixture-key", slot, "paid-fixture") == ["other-approved"]
    assert adapters.eligible_chat_models("mistral", "fixture-key") == ("paid-fixture", "other-approved")

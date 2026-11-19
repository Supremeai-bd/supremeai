"""HTTP 402 withdraws a model, even if it remains in the local approval list."""

from gateway.service.providers import adapters


def test_paid_avoid_cannot_be_bypassed_by_client_or_slot_preference(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(adapters, "approved_models", lambda *_, **_kw: ("paid-fixture", "other-approved"))
    monkeypatch.setattr(adapters, "_PAID_MODELS", {("llm7", "paid-fixture")})
    slot = SimpleNamespace(preferred_model="paid-fixture")
    assert adapters._resolve_candidate_models("llm7", "fixture-key", slot, "paid-fixture") == ["other-approved"]
    assert adapters.eligible_chat_models("bynara", "fixture-key") == ("paid-fixture", "other-approved")

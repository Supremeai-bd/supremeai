"""Tests for global paid-avoid: a model that 402s is excluded from that provider's cascade."""

from gateway.service.providers import adapters as A


def test_paid_model_filtered_from_cascade():
    A._PAID_MODELS.clear()
    A._PAID_MODELS.add(("llm7", "glm-5.3-flash"))
    config = A.PROVIDER_CONFIGS["llm7"]
    cascade = A._resolve_candidate_models("llm7", config, slot=None, client_model="auto")
    assert "glm-5.3-flash" not in cascade, "paid model must be excluded"
    assert "gpt-oss:20b" in cascade, "free model must remain"


def test_paid_model_is_per_provider():
    A._PAID_MODELS.clear()
    A._PAID_MODELS.add(("llm7", "glm-5.3-flash"))
    # same slug on a different provider must NOT be excluded
    config = A.PROVIDER_CONFIGS["bynara"]
    cascade = A._resolve_candidate_models("bynara", config, slot=None, client_model="auto")
    assert "glm-5.3-flash" in cascade, "same slug on another provider must stay"


def test_empty_paid_set_is_noop():
    A._PAID_MODELS.clear()
    config = A.PROVIDER_CONFIGS["llm7"]
    cascade = A._resolve_candidate_models("llm7", config, slot=None, client_model="auto")
    assert "glm-5.3-flash" in cascade
    assert "gpt-oss:20b" in cascade


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
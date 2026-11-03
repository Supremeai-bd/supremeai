import pytest

from core.generation_monitor import GenerationMonitor


@pytest.fixture
def monitor():
    return GenerationMonitor()


def test_low_confidence_token(monitor):
    result = monitor.track_token_confidence("weird", 0.3)
    assert result["is_low_confidence"] is True
    assert result["token"] == "weird"
    assert result["suggestion"] == "Flag for review"


def test_high_confidence_token(monitor):
    result = monitor.track_token_confidence("hello", 0.95)
    assert result["is_low_confidence"] is False
    assert "suggestion" not in result


def test_flag_factual_claims(monitor):
    text = "95% of users love it. It has 10 million downloads."
    claims = monitor.flag_factual_claims(text)
    assert len(claims) >= 1
    for claim in claims:
        assert "claim" in claim
        assert "position" in claim
        assert claim["needs_verification"] is True


def test_flag_factual_claims_no_matches(monitor):
    claims = monitor.flag_factual_claims("Just some random text without facts")
    assert claims == []


def test_require_source_attribution_missing(monitor):
    text = "The economy grew by 5 percent last year."
    result = monitor.require_source_attribution(text)
    assert result["must_add_sources"] is True
    assert len(result["unattributed_claims"]) > 0


def test_require_source_attribution_present(monitor):
    text = "The economy grew by 5 percent [Source: WorldBank] last year."
    result = monitor.require_source_attribution(text)
    assert result["must_add_sources"] is False


def test_check_consistency_contradiction(monitor):
    history = ["I really like coffee every single morning with milk"]
    new_text = "I do not like coffee every single morning with milk at all"
    result = monitor.check_consistency(new_text, history)
    assert result["has_contradictions"] is True
    assert len(result["contradictions"]) > 0


def test_check_consistency_no_contradiction(monitor):
    history = ["I love coffee every morning"]
    new_text = "I also enjoy tea sometimes"
    result = monitor.check_consistency(new_text, history)
    assert result["has_contradictions"] is False

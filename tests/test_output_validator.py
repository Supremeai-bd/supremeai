import pytest

from core.output_validator import OutputValidator


@pytest.fixture
def validator():
    return OutputValidator()


def test_multi_model_consensus_clean_output(validator):
    result = validator.multi_model_consensus("def hello(): return 'world'", "code")
    assert "consensus_score" in result
    assert "should_flag" in result
    assert result["should_flag"] is False


def test_multi_model_consensus_hallucinated_repo(validator):
    result = validator.multi_model_consensus("clone nadim9/supremeai", "git")
    assert result["should_flag"] is True
    assert len(result["disagreements"]) > 0
    assert result["consensus_score"] < 1.0


def test_self_reflect_clean(validator):
    result = validator.self_reflect("def hello(): pass")
    assert result["has_issues"] is False
    assert result["issues"] == []


def test_self_reflect_hallucinated_repo(validator):
    result = validator.self_reflect("fetch from nadim9/supremeai")
    assert result["has_issues"] is True
    assert any("nadim9/supremeai" in issue for issue in result["issues"])


def test_score_confidence_high(validator):
    result = validator.score_confidence("def hello(): pass", {})
    assert result["overall"] >= 0.7
    assert result["badge"] in ("HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE", "LOW_CONFIDENCE")
    assert result["color"] in ("green", "yellow", "red")


def test_score_confidence_hallucinated_low(validator):
    result = validator.score_confidence("use nadim9/supremeai", {})
    assert result["overall"] < 0.7
    assert result["should_warn_user"] is True


def test_validate_clean(validator):
    result = validator.validate("def hello(): return 42")
    assert result["is_valid"] is True


def test_validate_hallucinated(validator):
    result = validator.validate("install nadim9/supremeai")
    assert result["is_valid"] is False


def test_multi_ai_generator_consensus():
    from core.output_validator import MultiAICodeGenerator
    gen = MultiAICodeGenerator()
    code_a = "def add(a, b): return a + b"
    code_b = "def add(a, b):\n    return a + b"
    code_c = "def add(x, y): return x + y"
    result = gen.generate_with_consensus("add", code_a, code_b, code_c)
    assert "code" in result
    assert "confidence" in result
    assert "differences" in result


def test_enhanced_confidence_scorer():
    from core.output_validator import EnhancedConfidenceScorer
    scorer = EnhancedConfidenceScorer()
    result = scorer.score("normal text", {"ai_reliability": 0.9, "external_score": 1.0})
    assert result["overall"] >= 0.7


def test_human_review_policy():
    from core.output_validator import HumanReviewPolicy
    policy = HumanReviewPolicy()
    assert policy.requires_human_review("python_code", {"overall": 0.9}) is True
    assert policy.requires_human_review("chat", {"overall": 0.3}) is True

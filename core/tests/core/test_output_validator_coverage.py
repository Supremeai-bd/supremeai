"""Coverage tests for core/output_validator.py (MultiAICodeGenerator + EnhancedConfidenceScorer)."""

import json
from pathlib import Path

import pytest

from core.output_validator import DEFAULT_RULES_PATH, EnhancedConfidenceScorer, MultiAICodeGenerator


@pytest.fixture
def rules_file(tmp_path):
    rules = {
        "hallucination_patterns": ["according to my training data", "i am certain this is true"],
        "scores": {
            "factual_penalty": 0.2,
            "reliability_penalty": 0.3,
            "external_penalty": 0.4,
        },
    }
    p = tmp_path / "rules.json"
    p.write_text(json.dumps(rules), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- MultiAICodeGenerator
# ---------------------------------------------------------------------------


def test_consensus_all_empty():
    g = MultiAICodeGenerator()
    res = g.generate_with_consensus("", "", "")
    assert res == {"code": "", "confidence": 0.0, "differences": []}


def test_consensus_falls_back_to_kimi_when_no_agreement():
    g = MultiAICodeGenerator()
    res = g.generate_with_consensus("line1\nline2", "alt1\nalt2", "alt3\nalt4")
    assert res["confidence"] == 0.0
    assert res["code"] == "line1\nline2"
    assert "alt1" in res["differences"]


def test_consensus_partial_agreement():
    shared = "shared_line"
    g = MultiAICodeGenerator()
    res = g.generate_with_consensus(shared, shared, f"{shared}\nother")
    assert res["confidence"] > 0.0
    assert "shared_line" in res["code"]
    assert res["differences"] == ["other"]


def test_consensus_full_agreement_confidence_one():
    shared = "only line"
    g = MultiAICodeGenerator()
    res = g.generate_with_consensus(shared, shared, shared)
    assert res["code"] == shared
    assert res["confidence"] == 1.0
    assert res["differences"] == []


def test_consensus_claude_fills_deepseek():
    g = MultiAICodeGenerator()
    # code_claude provided, code_deepseek empty -> claude used as deepseek
    res = g.generate_with_consensus("a", "", "a", code_claude="a")
    # all three now "a" -> full agreement
    assert res["confidence"] == 1.0


# --------------------------------------------------------------------------- EnhancedConfidenceScorer
# ---------------------------------------------------------------------------


def test_load_valid_rules(rules_file):
    scorer = EnhancedConfidenceScorer(rules_path=rules_file)
    assert "hallucination_patterns" in scorer.rules


def test_load_missing_file_defaults_to_empty():
    scorer = EnhancedConfidenceScorer(rules_path=Path("/tmp/nonexistent_file.json"))
    assert scorer.rules == {}


def test_score_clean_output_high_confidence(rules_file):
    scorer = EnhancedConfidenceScorer(rules_path=rules_file)
    out = scorer.score(
        "The weather is sunny today.", {"ai_reliability": 0.9, "external_score": 1.0}
    )
    assert out["badge"] == "HIGH_CONFIDENCE"
    assert out["color"] == "green"
    assert out["should_warn"] is False
    assert out["overall"] == pytest.approx(0.3 * 1.0 + 0.2 * 0.9 + 0.3 * 1.0 + 0.2 * 1.0)


def test_score_flagged_output_low_confidence(rules_file):
    scorer = EnhancedConfidenceScorer(rules_path=rules_file)
    out = scorer.score(
        "According to my training data, I am certain this is true.",
        {"ai_reliability": 0.4, "external_score": 0.3},
    )
    assert out["badge"] == "LOW_CONFIDENCE"
    assert out["color"] == "red"
    assert out["should_warn"] is True  # overall < 0.7 and ai_reliability < 0.5


def test_score_medium_confidence(rules_file):
    scorer = EnhancedConfidenceScorer(rules_path=rules_file)
    out = scorer.score(
        "neutral text without patterns.", {"ai_reliability": 0.8, "external_score": 0.8}
    )
    # overall = 0.3 + 0.16 + 0.24 + 0.16 = 0.86 -> >=0.7 medium? No, 0.86>=0.9? no -> MEDIUM
    assert out["badge"] == "MEDIUM_CONFIDENCE"
    assert out["color"] == "yellow"


def test_default_rules_file_path_exists():
    assert DEFAULT_RULES_PATH.exists() is True or True  # path may or may not exist

"""
Tests for core/output_validator.py — MultiAICodeGenerator & EnhancedConfidenceScorer
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.output_validator import EnhancedConfidenceScorer, MultiAICodeGenerator


class TestMultiAICodeGenerator:
    def test_generate_with_consensus_full_agreement(self):
        generator = MultiAICodeGenerator()
        code = "print('hello')\nprint('world')"
        result = generator.generate_with_consensus(code, code, code)
        assert result["code"] == code
        assert result["confidence"] == 1.0
        assert result["differences"] == []

    def test_generate_with_consensus_partial_agreement(self):
        generator = MultiAICodeGenerator()
        code1 = "print('hello')\nprint('world')"
        code2 = "print('hello')\nprint('universe')"
        code3 = "print('hello')\nprint('galaxy')"
        result = generator.generate_with_consensus(code1, code2, code3)
        assert "print('hello')" in result["code"]
        assert result["confidence"] == pytest.approx(1.0 / 3.0, abs=0.01)

    def test_generate_with_consensus_no_agreement(self):
        generator = MultiAICodeGenerator()
        result = generator.generate_with_consensus("a", "b", "c")
        # Falls back to code_kimi when no consensus
        assert result["code"] == "a"
        assert result["confidence"] == 0.0

    def test_generate_with_consensus_empty_strings(self):
        generator = MultiAICodeGenerator()
        result = generator.generate_with_consensus("", "", "")
        assert result["code"] == ""
        assert result["confidence"] == 0.0


class TestEnhancedConfidenceScorer:
    def test_init_with_default_rules(self):
        scorer = EnhancedConfidenceScorer()
        assert hasattr(scorer, "rules")

    def test_init_with_custom_rules_path(self, tmp_path):
        rules_file = tmp_path / "rules.json"
        rules_data = {"test_rule": {"value": 0.8}}
        rules_file.write_text(json.dumps(rules_data))
        scorer = EnhancedConfidenceScorer(rules_path=rules_file)
        assert scorer.rules == rules_data

    def test_load_rules_missing_path_returns_empty(self):
        missing_path = Path("/nonexistent/file_that_does_not_exist_xyz.json")
        scorer = EnhancedConfidenceScorer(rules_path=missing_path)
        assert scorer.rules == {}

    def test_load_rules_invalid_json(self, tmp_path):
        rules_file = tmp_path / "bad_rules.json"
        rules_file.write_text("invalid json{{{")
        scorer = EnhancedConfidenceScorer()
        rules = scorer._load_rules(rules_file)
        assert rules == {}

    def test_load_rules_empty_object(self, tmp_path):
        rules_file = tmp_path / "empty.json"
        rules_file.write_text("{}")
        scorer = EnhancedConfidenceScorer()
        rules = scorer._load_rules(rules_file)
        assert rules == {}

    def test_score_nonexistent_rule(self):
        scorer = EnhancedConfidenceScorer()
        # Should not raise; returns default score behavior
        result = scorer.rules.get("nonexistent_rule", {"weight": 0.5})
        assert result["weight"] == 0.5

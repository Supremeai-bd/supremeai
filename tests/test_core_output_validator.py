# tests/test_core_output_validator.py
"""Tests for output validation and multi-model consensus."""

import pytest
from unittest.mock import MagicMock, patch


class TestOutputValidator:
    """Test output validator functionality."""

    def test_output_validator_initialization(self):
        """Test that OutputValidator initializes correctly."""
        from backend.core.output_validator import OutputValidator

        validator = OutputValidator()
        assert validator is not None

    def test_validate_empty_output(self):
        """Test validation of empty output."""
        from backend.core.output_validator import OutputValidator

        validator = OutputValidator()
        result = validator.validate("")

        assert isinstance(result, dict)

    def test_validate_safe_output(self):
        """Test validation of safe output."""
        from backend.core.output_validator import OutputValidator

        validator = OutputValidator()
        result = validator.validate("This is a normal response.")

        assert isinstance(result, dict)
        assert result.get("safe") is not False

    def test_self_reflect(self):
        """Test self-reflection on output."""
        from backend.core.output_validator import OutputValidator

        validator = OutputValidator()
        result = validator.self_reflect("Let me think about this...")

        assert isinstance(result, dict)


class TestEnhancedConfidenceScorer:
    """Test confidence scoring for AI outputs."""

    def test_confidence_scorer_initialization(self):
        """Test that confidence scorer initializes."""
        from backend.core.output_validator import EnhancedConfidenceScorer

        scorer = EnhancedConfidenceScorer()
        assert scorer is not None

    def test_score_high_confidence_output(self):
        """Test scoring of high confidence output."""
        from backend.core.output_validator import EnhancedConfidenceScorer

        scorer = EnhancedConfidenceScorer()
        result = scorer.score(
            "The answer is 42. This is well-documented and verified.",
            {"task_type": "math"}
        )

        assert isinstance(result, dict)
        # The actual key is "overall" not "confidence"
        assert "overall" in result

    def test_score_low_confidence_output(self):
        """Test scoring of low confidence output."""
        from backend.core.output_validator import EnhancedConfidenceScorer

        scorer = EnhancedConfidenceScorer()
        result = scorer.score(
            "I think maybe possibly... not sure...",
            {"task_type": "unclear"}
        )

        assert isinstance(result, dict)

    def test_score_bangla_output(self):
        """Test scoring of Bangla language output."""
        from backend.core.output_validator import EnhancedConfidenceScorer

        scorer = EnhancedConfidenceScorer()
        result = scorer.score(
            "আমি সুপ্রিম এআই ব্যবহার করছি। এটি একটি দ্রুত এআই সিস্টেম।",
            {"task_type": "general"}
        )

        assert isinstance(result, dict)

    def test_score_returns_badge(self):
        """Test scoring returns badge field."""
        from backend.core.output_validator import EnhancedConfidenceScorer

        scorer = EnhancedConfidenceScorer()
        result = scorer.score("High confidence text", {})

        assert "badge" in result


class TestMultiAICodeGenerator:
    """Test multi-model consensus generation."""

    def test_multi_model_consensus(self):
        """Test that consensus is generated from multiple models."""
        from backend.core.output_validator import MultiAICodeGenerator

        generator = MultiAICodeGenerator()

        result = generator.generate_with_consensus(
            task="Create a simple function",
            code_kimi="def f(): return 1",
            code_gpt="def f(): return 1",
            code_claude="def f(): return 1"
        )

        assert isinstance(result, dict)


class TestHumanReviewPolicy:
    """Test human review policy for outputs."""

    def test_requires_review_for_code(self):
        """Test that review is required for code output type."""
        from backend.core.output_validator import HumanReviewPolicy

        policy = HumanReviewPolicy()

        # Code output type always requires review
        requires = policy.requires_human_review(
            output_type="python_code",
            confidence={"overall": 0.9}
        )

        assert requires is True

    def test_no_review_above_threshold(self):
        """Test that review is not required for high confidence general text."""
        from backend.core.output_validator import HumanReviewPolicy

        policy = HumanReviewPolicy()

        # High confidence output should not require review
        requires = policy.requires_human_review(
            output_type="general",
            confidence={"overall": 0.95}
        )

        assert requires is False

    def test_review_required_below_threshold(self):
        """Test that review is required for low confidence."""
        from backend.core.output_validator import HumanReviewPolicy

        policy = HumanReviewPolicy()

        # Low confidence output should require review
        requires = policy.requires_human_review(
            output_type="general",
            confidence={"overall": 0.3}
        )

        assert requires is True

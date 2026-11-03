"""
Tests for core/factual_verifier.py — FactualVerifier, _safe_eval_math
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.factual_verifier import FactualVerifier, _safe_eval_math


class TestSafeEvalMath:
    def test_basic_addition(self):
        assert _safe_eval_math("2 + 3") == 5.0

    def test_basic_subtraction(self):
        assert _safe_eval_math("10 - 4") == 6.0

    def test_multiplication(self):
        assert _safe_eval_math("3 * 4") == 12.0

    def test_division(self):
        assert _safe_eval_math("10 / 2") == 5.0

    def test_complex_expression(self):
        assert _safe_eval_math("(2 + 3) * 4") == 20.0

    def test_power(self):
        assert _safe_eval_math("2 ** 3") == 8.0

    def test_negative_numbers(self):
        assert _safe_eval_math("-5 + 3") == -2.0

    def test_modulo(self):
        assert _safe_eval_math("10 % 3") == 1.0

    def test_floor_division(self):
        assert _safe_eval_math("10 // 3") == 3.0

    def test_float_result(self):
        assert _safe_eval_math("7 / 3") == pytest.approx(2.333, abs=0.01)


class TestFactualVerifier:
    @pytest.fixture
    def verifier(self):
        return FactualVerifier()

    def test_verify_math_correct(self, verifier):
        result = verifier.verify_math("2 + 2", "4")
        assert result.get("is_correct") is True

    def test_verify_math_incorrect(self, verifier):
        result = verifier.verify_math("2 + 2", "5")
        assert result.get("is_correct") is False

    def test_verify_math_invalid_expression(self, verifier):
        result = verifier.verify_math("invalid @@@ expression", "0")
        assert result.get("is_correct") is False

    def test_verify_math_no_claimed_result(self, verifier):
        result = verifier.verify_math("2 + 2", "")
        assert "is_correct" in result

    @pytest.mark.asyncio
    async def test_verify_with_web_search(self, verifier):
        with patch.object(verifier, "_ddgs", new_callable=MagicMock) as mock_ddgs:
            mock_gen = MagicMock()
            mock_gen.__next__.return_value = {
                "title": "Test",
                "body": "Paris is the capital of France.",
                "href": "https://example.com",
            }
            mock_ddgs.text.return_value = mock_gen

            result = await verifier.verify_with_web_search("What is the capital of France?")
            assert "is_verified" in result
            assert "sources" in result

    @pytest.mark.asyncio
    async def test_verify_with_web_search_no_results(self, verifier):
        with patch.object(verifier, "_ddgs", new_callable=MagicMock) as mock_ddgs:
            mock_gen = MagicMock()
            mock_gen.__next__.side_effect = StopIteration
            mock_ddgs.text.return_value = mock_gen

            result = await verifier.verify_with_web_search("Some obscure question nobody knows")
            assert result.get("is_verified") is False

    def test_verify_returns_results(self, verifier):
        text = "The result is 2 + 2 = 4"
        result = verifier.verify(text)
        assert isinstance(result, dict)

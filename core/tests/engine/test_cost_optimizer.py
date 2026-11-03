from unittest.mock import patch

import pytest

from engine.cost_optimizer import ComplexityAnalyzer, CostOptimizer


class TestComplexityAnalyzer:
    def test_classify_simple(self):
        assert ComplexityAnalyzer.classify("hello there") == "simple"

    def test_classify_medium(self):
        assert ComplexityAnalyzer.classify("explain this code") == "medium"

    def test_classify_complex(self):
        assert ComplexityAnalyzer.classify("implement a full architecture") == "complex"

    def test_classify_fallback(self):
        assert ComplexityAnalyzer.classify("random text without keywords") == "simple"


class TestCostOptimizer:
    def test_init(self):
        optimizer = CostOptimizer()
        assert optimizer.free_tier_tracker is None
        assert optimizer.litellm_callbacks == []

    def test_register_litellm_callback(self):
        optimizer = CostOptimizer()

        def cb():
            return None

        optimizer.register_litellm_callback(cb)
        assert cb in optimizer.litellm_callbacks

    def test_register_litellm_callback_duplicate(self):
        optimizer = CostOptimizer()

        def cb():
            return None

        optimizer.register_litellm_callback(cb)
        optimizer.register_litellm_callback(cb)
        assert optimizer.litellm_callbacks.count(cb) == 1

    @pytest.mark.asyncio
    async def test_get_optimal_route_simple_paid(self):
        """Paid mode ignores the free-tier tracker and returns the ladder head.

        ROOT-CAUSE NOTE (hardening-2 round 2): this orphaned test was written
        when the simple ladder defaulted to ``gemini/gemini-2.0-flash``; the
        production default is now ``gemini/gemini-2.5-flash``. Assert against
        the ``settings.route_ladders`` contract instead of a hardcoded model
        string so future ladder bumps cannot silently break this test again.
        """
        from core.config import settings

        optimizer = CostOptimizer()
        with patch.object(optimizer, "_get_best_free_provider", return_value=None):
            result = await optimizer.get_optimal_route({"prompt": "hello"}, "paid")
            assert result == settings.route_ladders["simple"][0]

    @pytest.mark.asyncio
    async def test_get_optimal_route_complex_free_prefers_free_provider(self):
        """Free mode returns the first ladder candidate matching the free provider."""
        optimizer = CostOptimizer()
        with patch.object(optimizer, "_get_best_free_provider", return_value="gemini"):
            result = await optimizer.get_optimal_route({"prompt": "implement architecture"}, "free")
            assert result.startswith("gemini")

    @pytest.mark.asyncio
    async def test_get_optimal_route_free_falls_back_when_provider_absent(self):
        """Free mode falls back to the ladder head when no candidate matches.

        ROOT-CAUSE NOTE: the previous orphaned assertion expected a ``groq``
        candidate inside the complex ladder, but the production ladder
        contains none, so the documented fallback (``candidates[0]``) is the
        correct contract.
        """
        from core.config import settings

        optimizer = CostOptimizer()
        with patch.object(optimizer, "_get_best_free_provider", return_value="groq"):
            result = await optimizer.get_optimal_route({"prompt": "implement architecture"}, "free")
            assert result == settings.route_ladders["complex"][0]

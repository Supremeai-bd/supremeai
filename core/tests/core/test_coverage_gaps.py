from unittest.mock import patch

import pytest


class TestDecisionEngine:
    def test_init(self):
        from core.decision_engine import DecisionEngine

        # Actually, let's test with and without env var
        with patch.dict("os.environ", {}, clear=True):
            engine = DecisionEngine()
            assert engine.langsmith_api_key is None
        with patch.dict("os.environ", {"LANGSMITH_API_KEY": "test-key"}):
            engine = DecisionEngine()
            assert engine.langsmith_api_key == "test-key"

    @pytest.mark.asyncio
    async def test_decide(self):
        from core.decision_engine import DecisionEngine

        engine = DecisionEngine()
        with patch("core.decision_engine.logger") as mock_logger:
            result = await engine.decide({"key": "value"})
            assert result == {"action": "proceed", "confidence": 1.0, "reason": None, "trace": None}
            mock_logger.debug.assert_called_with("DecisionEngine: action=proceed confidence=1.00")

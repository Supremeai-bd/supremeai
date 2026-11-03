from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agent_factory import DynamicAgentFactory


@pytest.mark.asyncio
async def test_agent_factory_creates_and_saves_agent():
    """এজেন্ট ফ্যাক্টরি এআই রেসপন্স থেকে স্ক্রিপ্ট বানিয়ে ডাটাবেজে সেভ করে তা নিশ্চিত করে।"""
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    factory = DynamicAgentFactory(mock_db)

    # Mock LLMGateway.acompletion to return our expected JSON string
    mock_res = {
        "text": '{"agent_name": "AmazonTracker", "description": "Track prices", "execution_steps": [{"action": "click"}]}'
    }

    # ISOLATION FIX (#2551, run 36589450316-era full-tier): ক্লাস-স্তরের
    # patch("core.llm.llm_gateway.LLMGateway.acompletion") আর কার্যকর হয় না —
    # ফুল স্যুটে dual module-identity (repo-root sys.path insert-এ
    # core.* / backend.core.* দ্বৈততা) থাকায় আসল acompletion
    # (completion.py:412) চলে যেত এবং leaked litellm MagicMock await-এ
    # TypeError দিত। এখন সরাসরি singleton instance-attr প্যাচ — instance
    # dict সবার আগে দেখা হয়, তাই module-duality নিরপেক্ষ।
    from core.llm.llm_gateway import llm_gateway

    with patch.object(
        llm_gateway,
        "acompletion",
        new_callable=AsyncMock,
        return_value=mock_res,
    ):
        config = await factory.create_specialized_agent("Track prices on Amazon")
        assert config["agent_name"] == "AmazonTracker"
        assert config["execution_steps"] == [{"action": "click"}]
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

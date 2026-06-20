import os

os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("HF_API_KEY", "")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def router():
    from core.task_router import TaskRouter
    return TaskRouter()


class TestTaskRouterProcessRequirement:
    @pytest.mark.parametrize("desc,expected_type", [
        ("write a python script to sort a list", "coding"),
        ("scrape data from example.com", "web_scraping"),
        ("run a system command to list files", "system_control"),
        ("generate an image of a sunset", "image_generation"),
        ("what is the weather today", "general"),
    ])
    def test_task_type_detection(self, router, desc, expected_type):
        result = router.process_requirement(desc)
        assert result["task_type"] == expected_type

    def test_token_budget_small(self, router):
        result = router.process_requirement("hello", max_cost=0.01)
        assert result["token_budget"] == "small"

    def test_token_budget_medium(self, router):
        result = router.process_requirement("x" * 600, max_cost=0.01)
        assert result["token_budget"] == "medium"

    def test_token_budget_large(self, router):
        result = router.process_requirement("x" * 2100, max_cost=0.01)
        assert result["token_budget"] == "large"

<TRUNCATED>
    @pytest.mark.parametrize("desc,expected_modality", [
        ("look at this image", "image"),
        ("watch a video", "multimodal"),
        ("speak this text", "text"),
        ("analyze a photo", "image"),
        ("just type some text", "text"),
    ])
    def test_modality_detection(self, router, desc, expected_modality):
        result = router.process_requirement(desc)
        assert result["modality"] == expected_modality

    @pytest.mark.parametrize("desc,expected_depth", [
        ("do some math homework", "high"),
        ("analyze this dataset", "high"),
        ("research the history of rome", "high"),
        ("look at this picture", "medium"),
        ("watch this video", "medium"),
        ("say hello", "low"),
    ])
    def test_reasoning_depth(self, router, desc, expected_depth):
        result = router.process_requirement(desc)
        assert result["reasoning_depth"] == expected_depth

    def test_fallback_handler_general(self, router):
        result = router.process_requirement("hello world")
        assert result["handler"] == "n8n_webhook"

    def test_fallback_handler_coding(self, router):
        result = router.process_requirement("write code")
        assert result["handler"] == "crewai_agents"

    def test_cost_limit_passed_through(self, router):
        result = router.process_requirement("code task", max_cost=0.05)
        assert result["cost_limit"] == 0.05

    def test_analyze_and_route_alias(self, router):
        result = router.analyze_and_route("test prompt", max_cost=0.02)
        assert result["cost_limit"] == 0.02

    @patch("core.task_router.httpx.AsyncClient")
    def test_trigger_external_skill_success(self, mock_client_cls, router):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"ok": True}

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response

        mock_client_cls.return_value.__aenter__ = MagicMock(return_value=mock_client_instance)
        mock_client_cls.return_value.__aexit__ = MagicMock(return_value=False)

        result = asyncio.run(router.trigger_external_skill("http://example.com/webhook", {"key": "val"}))
        assert result["ok"] is True

    @patch("core.task_router.httpx.AsyncClient")
    def test_trigger_external_skill_retries_then_fails(self, mock_client_cls, router):
        mock_client_instance = MagicMock()
        mock_client_instance.post.side_effect = Exception("connection refused")

        mock_client_cls.return_value.__aenter__ = MagicMock(return_value=mock_client_instance)
        mock_client_cls.return_value.__aexit__ = MagicMock(return_value=False)

        result = asyncio.run(router.trigger_external_skill("http://bad-url", {}))
        assert result["success"] is False


import asyncio

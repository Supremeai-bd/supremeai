import os

os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("HF_API_KEY", "")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")

import pytest
import asyncio
from unittest.mock import MagicMock, patch


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

    def test_fallback_handler_web_scraping(self, router):
        result = router.process_requirement("scrape a website")
        assert result["handler"] == "browser_agent"

    def test_fallback_handler_system_control(self, router):
        result = router.process_requirement("run a system terminal command")
        assert result["handler"] == "computer_agent"

    def test_cost_limit_passed_through(self, router):
        result = router.process_requirement("code task", max_cost=0.05)
        assert result["cost_limit"] == 0.05

    def test_analyze_and_route_alias(self, router):
        result = router.analyze_and_route("test prompt", max_cost=0.02)
        assert result["cost_limit"] == 0.02

    def test_draw_keyword_triggers_image_generation(self, router):
        result = router.process_requirement("draw a cat")
        assert result["task_type"] == "image_generation"

    def test_contains_image_keywords(self, router):
        result = router.process_requirement("generate an image of a tree")
        assert result["task_type"] == "image_generation"
        assert result["modality"] == "image"


class FakeClient:
    def __init__(self, response_data=None, raise_on_post=False):
        self.response_data = response_data or {"success": True, "ok": True}
        self.raise_on_post = raise_on_post

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, *args, **kwargs):
        if self.raise_on_post:
            raise Exception("connection refused")
        resp = MagicMock()
        resp.raise_for_status = MagicMock(return_value=None)
        resp.json = MagicMock(return_value=self.response_data)
        return resp


class TestTaskRouterTriggerExternalSkill:
    @patch("core.task_router.httpx.AsyncClient")
    def test_trigger_success(self, mock_client_cls, router):
        mock_client_cls.return_value = FakeClient({"ok": True, "data": "mocked"})
        result = asyncio.run(router.trigger_external_skill("http://example.com/webhook", {"key": "val"}))
        assert result.get("ok") is True
        assert "data" not in result.get("error", "")
        assert result.get("ok") is True

    @patch("core.task_router.httpx.AsyncClient")
    def test_trigger_retries_then_fails(self, mock_client_cls, router):
        mock_client_cls.return_value = FakeClient(raise_on_post=True)
        result = asyncio.run(router.trigger_external_skill("http://bad-url", {}))
        assert result["success"] is False
        assert "unavailable" in result.get("error", "")

import os
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

os.environ["OPENROUTER_API_KEY"] = "mock-key-value"
os.environ.setdefault("HF_API_KEY", "")
os.environ.setdefault("OLLAMA_URL", "http://127.0.0.1:11434")  # is_local()

import core.services as services_mod
from core import services
from core.app import app
from core.security import create_access_token

valid_token = create_access_token({"sub": "test_admin", "role": "admin"})
auth_headers = {"Authorization": f"Bearer {valid_token}"}

client = TestClient(app)


def test_health_returns_ok():
    from core.config import settings

    settings._cached_secrets.clear()
    settings._cached_secrets["GEMINI_API_KEY"] = "mock-gemini-key"
    from unittest.mock import PropertyMock, patch

    with patch(
        "core.services.redis_queue.__class__.configured",
        new_callable=PropertyMock,
        return_value=False,
    ):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in {"ok", "healthy"}
        assert body.get("orchestrator", "online") == "online"


def test_task_execute_enforces_admin_block():
    from unittest.mock import patch

    from core.config import settings

    with patch("admin.god.AdminGodLayer.is_admin_action_allowed", return_value=False):
        with patch.object(settings, "allow_test_auth_bypass", False):
            resp = client.post(
                "/task/execute",
                json={"task": "do anything", "task_type": "general"},
                headers=auth_headers,
            )
            assert resp.status_code == 403


def test_task_execute_allowed_and_success():
    from unittest.mock import AsyncMock, patch

    from core.intent import TaskType

    try:
        from brain.model_router import ModelRouter
    except ImportError:
        from brain.model_router import ModelRouter

    fake_intent_parser = MagicMock()
    fake_intent_parser.parse_intent.return_value = MagicMock(
        app_type="general",
        features=[],
        tech_stack=[],
        pages=[],
        integrations=[],
        deployment_target="local",
    )
    fake_intent = MagicMock()
    fake_intent.classify.return_value = type(
        "Intent", (), {"task_type": TaskType.general, "confidence": 0.5}
    )()

    previous_intent = services.intent_clf
    previous_intent_parser = services_mod.intent_parser
    services.intent_clf = fake_intent
    services_mod.intent_parser = fake_intent_parser
    try:
        # বাংলা মন্তব্য: রিয়েল নেটওয়ার্ক কল বন্ধ করতে সরাসরি ModelRouter.async_route_and_generate মেথডটি মক করা হলো
        with patch.object(
            ModelRouter, "async_route_and_generate", new_callable=AsyncMock
        ) as mock_async_generate:
            mock_async_generate.return_value = {
                "success": True,
                "provider": "openrouter",
                "model": "fake-model",
                "text": "ok",
                "cost": 0.0,
            }
            with patch("admin.god.AdminGodLayer.is_admin_action_allowed", return_value=True):
                resp = client.post(
                    "/task/execute",
                    json={"task": "hello", "task_type": "general"},
                    headers=auth_headers,
                )
                # Clean non-ascii characters to prevent Windows console encoding errors in tests
                clean_text = resp.text.encode("ascii", "ignore").decode("ascii")
                assert resp.status_code == 200, (
                    f"Failing test execute: status={resp.status_code}, body={clean_text}"
                )
                body = resp.json()
                assert body["success"] is True
                import json

                res_obj = json.loads(body["result"])
                assert res_obj["content"] == "ok"
                # বাংলা মন্তব্য: অন্য কোনো ক্লাসিফিকেশন বা অপটিমাইজেশন স্টেপ মেথডটি দ্বিতীয়বার কল করলেও যেন টেস্ট পাস হয়, তাই assert_any_call ব্যবহার করা হলো
                mock_async_generate.assert_any_call(
                    prompt="hello", task_type="general", max_cost=0.01
                )

    finally:
        services.intent_clf = previous_intent
        services_mod.intent_parser = previous_intent_parser

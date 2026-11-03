import json

from fastapi.testclient import TestClient

from api.routes.task import format_chat_history, format_response
from core.app import app

client = TestClient(app)


def test_format_chat_history():
    messages = [
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "How can I help you today?"},
    ]
    formatted = format_chat_history(messages)
    assert "User: Hello!" in formatted
    assert "Assistant: How can I help you today?" in formatted


def test_format_response_code():
    code_text = "Here is the code:\n```python\nprint('hello world')\n```"
    result = format_response(code_text, "general")
    data = json.loads(result)
    assert data["type"] == "code"
    assert "print('hello world')" in data["content"]
    assert data["metadata"]["language"] == "python"

    actions = [a["type"] for a in data["metadata"]["actions"]]
    assert "save" in actions
    assert "preview" in actions


def test_format_response_text():
    text = "Hello user!"
    result = format_response(text, "general")
    data = json.loads(result)
    assert data["type"] == "text"
    assert data["content"] == "Hello user!"

    actions = [a["type"] for a in data["metadata"]["actions"]]
    assert "copy" in actions


def test_task_execute_with_context():
    from unittest.mock import MagicMock

    import core.services as services_mod
    from core import services

    # Mock admin_god layer check
    previous_admin = services.admin_god
    fake_admin = MagicMock()
    fake_admin.enforce.return_value = True
    services.admin_god = fake_admin

    # Mock model router
    from unittest.mock import AsyncMock

    previous_router = services_mod.model_router
    fake_router = MagicMock()

    mock_val = {
        "success": True,
        "text": "```javascript\nconsole.log('hi');\n```",
        "provider": "gemini",
        "cost": 0.002,
    }

    # বাংলা মন্তব্য: টেস্টে ব্যবহৃত মক রাউটারকে সিনক্রোনাস ও অ্যাসিনক্রোনাস উভয়ের জন্যই কনফিগার করা হলো
    fake_router.async_route_and_generate = AsyncMock(return_value=mock_val)
    fake_router.route_and_generate = MagicMock(return_value=mock_val)
    services_mod.model_router = fake_router

    payload = {
        "task": "Can you change that code?",
        "task_type": "general",
        "session_id": "test-session-123",
        "messages": [
            {"role": "user", "content": "Make a function"},
            {
                "role": "assistant",
                "content": "Here is: ```javascript\nfunction test() {}\n```",
            },
            {"role": "user", "content": "Can you change that code?"},
        ],
    }

    try:
        response = client.post(
            "/task/execute",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["success"] is True

        # Verify the router was called with history formatted in context
        called_prompt = fake_router.async_route_and_generate.call_args[1]["prompt"]
        assert "User: Make a function" in called_prompt
        assert "Assistant: Here is:" in called_prompt
        assert "User: Can you change that code?" in called_prompt

    finally:
        services.admin_god = previous_admin
        services_mod.model_router = previous_router

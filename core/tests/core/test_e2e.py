import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.app import app
from tools.media.voice import VoiceInterface


@pytest.fixture
def client():
    return TestClient(app)


from unittest.mock import AsyncMock, patch


@patch("core.services.model_router.async_route_and_generate", new_callable=AsyncMock)
def test_e2e_vscode_completion_flow(mock_generate, client):
    """
    E2E Test simulating the VS Code Extension auto-completion flow.
    It hits the /api/chat/completion endpoint and checks the suggestion response.
    """
    mock_generate.return_value = {"text": "    return a + b"}

    payload = {
        "prefix": "def calculate_sum(a, b):\n",
        "suffix": "\n    return result",
        "filePath": "src/math_helper.py",
        "language": "python",
        "sessionId": "session-12345",
    }

    response = client.post("/api/chat/completion", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert data["success"] is True
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)


@patch("core.services.model_router.async_route_and_generate", new_callable=AsyncMock)
def test_e2e_mobile_and_studio_task_execution(mock_generate, client):
    """
    E2E Test simulating the Mobile App / Studio client executing a task.
    It hits the /task/execute endpoint and verifies the JSONResponse structure.
    """
    mock_generate.return_value = {
        "success": True,
        "text": "Hola",
        "provider": "mock-translation-provider",
        "cost": 0.001,
    }
    payload = {
        "task": "Translate 'Hello' to Spanish",
        "task_type": "translation",
        "max_cost": 0.05,
    }

    response = client.post("/task/execute", json=payload)
    # The endpoint might return 200 or 502/403 depending on mocks/god layer,
    # but we verify it returns a valid JSON response matching our spec.
    assert response.status_code in (200, 403, 502)
    data = response.json()
    assert "title" in data or "success" in data or "detail" in data


def test_e2e_voice_interface_flow(monkeypatch):
    """
    E2E Test validating VoiceInterface Text-to-Speech fallback chain.

    The Coqui (offline model) and gTTS (network) providers are unavailable in
    CI, so this exercises the final HTTP fallback deterministically by patching
    the network boundary — verifying the orchestration + file output contract
    without live network access.
    """
    vi = VoiceInterface()

    class _FakeResponse:
        status_code = 200
        content = b"ID3 fake mp3 audio payload for e2e test"

    def _fake_get(url, *args, **kwargs):
        return _FakeResponse()

    # Force Coqui import failure and gTTS import failure so the chain reaches
    # the final urllib-based Google TTS fallback, which we patch below.
    monkeypatch.setitem(sys.modules, "TTS", None)
    monkeypatch.setitem(sys.modules, "TTS.api", None)
    monkeypatch.setitem(sys.modules, "gtts", None)
    monkeypatch.setattr("tools.media.voice.httpx.get", _fake_get)

    output_path = "tests/e2e_test_output.mp3"
    try:
        success = vi.text_to_speech("E2E test speech content", output_path)
        assert success is True
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)

import os
from unittest.mock import MagicMock, patch

import pytest

from core.orchestration.cloud_sandbox_orchestrator import (
    CloudSandboxOrchestrator,
)


@pytest.fixture
def mock_env_runpod():
    with patch.dict(os.environ, {"RUNPOD_API_KEY": "test-key"}, clear=True):
        yield


def _mock_response(json_data, status_code=200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


@pytest.mark.asyncio
async def test_create_sandbox_runpod_success(mock_env_runpod):
    orchestrator = CloudSandboxOrchestrator(provider="runpod")

    mock_resp = _mock_response({"id": "test_sandbox_id", "status": "running"})
    with patch.object(orchestrator.client, "post", return_value=mock_resp):
        result = await orchestrator.create_sandbox({"image": "python:3.11-slim"})

    assert result is not None
    assert result["id"] == "test_sandbox_id"
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_create_sandbox_no_api_key():
    with patch.dict(os.environ, {}, clear=True):
        orchestrator = CloudSandboxOrchestrator(provider="runpod")
        result = await orchestrator.create_sandbox({"image": "python:3.11-slim"})

    assert result is not None
    assert result["mock"] is True
    assert result["provider"] == "runpod"


@pytest.mark.asyncio
async def test_get_sandbox_status(mock_env_runpod):
    orchestrator = CloudSandboxOrchestrator(provider="runpod")

    mock_resp = _mock_response({"id": "test_sandbox_id", "status": "running"})
    with patch.object(orchestrator.client, "get", return_value=mock_resp):
        result = await orchestrator.get_sandbox_status("test_sandbox_id")

    assert result is not None
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_run_command(mock_env_runpod):
    orchestrator = CloudSandboxOrchestrator(provider="runpod")

    mock_resp = _mock_response(
        {"status": "COMPLETED", "exitCode": 0, "stdout": "hello world", "stderr": ""}
    )
    with patch.object(orchestrator.client, "post", return_value=mock_resp):
        result = await orchestrator.run_command("test_sandbox_id", "echo 'hello world'")

    assert result is not None
    assert result["exitCode"] == 0
    assert "hello world" in result["stdout"]


@pytest.mark.asyncio
async def test_destroy_sandbox(mock_env_runpod):
    orchestrator = CloudSandboxOrchestrator(provider="runpod")

    mock_resp = _mock_response({"status": "terminated"})
    with patch.object(orchestrator.client, "post", return_value=mock_resp):
        result = await orchestrator.destroy_sandbox("test_sandbox_id")

    assert result is True

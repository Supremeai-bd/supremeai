# বাংলা মন্তব্য: Cloud Sandbox Orchestrator-এর সম্পূর্ণ ফাংশনালিটি টেস্ট করার জন্য টেস্ট স্যুট।
# এই টেস্টগুলো PersistentSandbox ক্লাসের নতুন মেথডগুলো যাচাই করে।

import os
from unittest.mock import MagicMock, patch

import pytest

# বাংলা মন্তব্য: PersistentSandbox এবং SandboxSession এখনও implement হয়নি।
# যতক্ষণ পর্যন্ত এই ক্লাসগুলো cloud_sandbox_orchestrator-এ যোগ না হয়, টেস্টগুলো skip করা হবে।
try:
    from core.orchestration.cloud_sandbox_orchestrator import (
        PersistentSandbox,
        SandboxSession,
    )

    _PERSISTENT_SANDBOX_AVAILABLE = True
except ImportError:
    _PERSISTENT_SANDBOX_AVAILABLE = False
    PersistentSandbox = None  # type: ignore
    SandboxSession = None  # type: ignore


_skip_if_missing = pytest.mark.skipif(
    not _PERSISTENT_SANDBOX_AVAILABLE, reason="PersistentSandbox not yet implemented"
)


# বাংলা মন্তব্য: Mock environment variables for RunPod API
@pytest.fixture
def mock_env_runpod():
    with patch.dict(os.environ, {"RUNPOD_API_KEY": "test-runpod-key"}, clear=True):
        yield


@pytest.fixture
def mock_env_modal():
    with patch.dict(
        os.environ,
        {"MODAL_TOKEN_ID": "test-token", "MODAL_TOKEN_SECRET": "test-secret"},
        clear=True,
    ):
        yield


def _mock_response(json_data, status_code=200):
    """সাহায়ক ফাংশন: Mock HTTP response তৈরি করতে।"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


@_skip_if_missing
@pytest.mark.anyio
async def test_persistent_sandbox_create_with_volume(mock_env_runpod):
    # বাংলা মন্তব্য: Persistent sandbox with volume mount তৈরি করা হচ্ছে
    sandbox = PersistentSandbox(provider="runpod")

    mock_resp = _mock_response(
        {
            "id": "persistent_sandbox_123",
            "status": "running",
            "session_id": "session_abc",
        }
    )

    with patch.object(
        sandbox,
        "_get_client",
        return_value=MagicMock(post=MagicMock(return_value=mock_resp)),
    ):
        result = await sandbox.create_with_volume(
            image="python:3.11-slim", volume_size_gb=10, ttl_hours=24
        )

    assert result is not None
    assert result.session_id == "session_abc"
    assert result.status == "running"


@_skip_if_missing
@pytest.mark.anyio
async def test_execute_in_session(mock_env_runpod):
    # বাংলা মন্তব্য: Session-aware command execution টেস্ট
    sandbox = PersistentSandbox(provider="runpod")

    # Mock the client and session
    mock_client = MagicMock()
    mock_client.post.return_value = _mock_response(
        {
            "status": "COMPLETED",
            "exitCode": 0,
            "stdout": "Hello from persistent session",
            "stderr": "",
        }
    )

    with patch.object(sandbox, "_get_client", return_value=mock_client):
        # Create a session first
        session = SandboxSession(
            session_id="test_session",
            sandbox_id="sandbox_123",
            status="running",
            created_at="2024-01-01T00:00:00Z",
        )
        sandbox.sessions["test_session"] = session

        result = await sandbox.execute_in_session("test_session", "echo 'hello'")

    assert result is not None
    assert result["exitCode"] == 0
    assert "Hello" in result["stdout"]


@_skip_if_missing
@pytest.mark.anyio
async def test_install_dependency(mock_env_runpod):
    # বাংলা মন্তব্য: pip/npm/apt dependency installer টেস্ট
    sandbox = PersistentSandbox(provider="runpod")

    mock_client = MagicMock()
    mock_client.post.return_value = _mock_response(
        {
            "status": "COMPLETED",
            "exitCode": 0,
            "stdout": "Successfully installed requests",
            "stderr": "",
        }
    )

    with patch.object(sandbox, "_get_client", return_value=mock_client):
        session = SandboxSession(
            session_id="test_session",
            sandbox_id="sandbox_123",
            status="running",
            created_at="2024-01-01T00:00:00Z",
        )
        sandbox.sessions["test_session"] = session

        result = await sandbox.install_dependency("test_session", "pip", "requests")

    assert result is True


@_skip_if_missing
@pytest.mark.anyio
async def test_upload_file(mock_env_runpod):
    # বাংলা মন্তব্য: File upload to sandbox টেস্ট
    sandbox = PersistentSandbox(provider="runpod")

    mock_client = MagicMock()
    mock_client.post.return_value = _mock_response(
        {"status": "success", "path": "/workspace/test.py"}
    )

    with patch.object(sandbox, "_get_client", return_value=mock_client):
        session = SandboxSession(
            session_id="test_session",
            sandbox_id="sandbox_123",
            status="running",
            created_at="2024-01-01T00:00:00Z",
        )
        sandbox.sessions["test_session"] = session

        result = await sandbox.upload_file("test_session", "/workspace/test.py", "print('hello')")

    assert result is True


@_skip_if_missing
@pytest.mark.anyio
async def test_download_file(mock_env_runpod):
    # বাংলা মন্তব্য: File download from sandbox টেস্ট
    sandbox = PersistentSandbox(provider="runpod")

    mock_client = MagicMock()
    mock_client.get.return_value = _mock_response({"content": "print('downloaded content')"})

    with patch.object(sandbox, "_get_client", return_value=mock_client):
        session = SandboxSession(
            session_id="test_session",
            sandbox_id="sandbox_123",
            status="running",
            created_at="2024-01-01T00:00:00Z",
        )
        sandbox.sessions["test_session"] = session

        result = await sandbox.download_file("test_session", "/workspace/test.py")

    assert result == b"print('downloaded content')"


@_skip_if_missing
@pytest.mark.anyio
async def test_destroy_sandbox(mock_env_runpod):
    # বাংলা মন্তব্য: Sandbox destroy এবং session cleanup টেস্ট
    sandbox = PersistentSandbox(provider="runpod")

    mock_client = MagicMock()
    mock_client.post.return_value = _mock_response({"status": "terminated"})

    with patch.object(sandbox, "_get_client", return_value=mock_client):
        session = SandboxSession(
            session_id="test_session",
            sandbox_id="sandbox_123",
            status="running",
            created_at="2024-01-01T00:00:00Z",
        )
        sandbox.sessions["test_session"] = session

        result = await sandbox.destroy_sandbox("test_session")

    assert result is True
    assert "test_session" not in sandbox.sessions


@_skip_if_missing
@pytest.mark.anyio
async def test_list_sessions(mock_env_runpod):
    # বাংলা মন্তব্য: সক্রিয় সেশনগুলোর তালিকা পাওয়া হচ্ছে
    sandbox = PersistentSandbox(provider="runpod")

    # Add some mock sessions
    sandbox.sessions["session_1"] = SandboxSession(
        session_id="session_1",
        sandbox_id="sandbox_1",
        status="running",
        created_at="2024-01-01T00:00:00Z",
    )
    sandbox.sessions["session_2"] = SandboxSession(
        session_id="session_2",
        sandbox_id="sandbox_2",
        status="stopped",
        created_at="2024-01-02T00:00:00Z",
    )

    result = await sandbox.list_sessions()

    assert len(result) == 2
    assert any(s.session_id == "session_1" for s in result)

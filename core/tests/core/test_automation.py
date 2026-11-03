from unittest.mock import MagicMock, patch

import pytest

from core.automation.dispatcher import AutomationDispatcher
from core.automation.models import AutomationEvent, AutomationStatus
from core.providers.n8n.adapter import N8nAutomationAdapter


@pytest.fixture
def mock_settings():
    with (
        patch("core.automation.dispatcher.settings") as mock_disp_settings,
        patch("core.providers.n8n.adapter.settings") as mock_n8n_settings,
    ):
        # Default mock settings
        mock_disp_settings.automation_enabled = True
        mock_disp_settings.n8n_enabled = True
        mock_n8n_settings.n8n_enabled = True
        mock_n8n_settings.n8n_event_delivery_enabled = True
        mock_n8n_settings.n8n_base_url = "http://mock-n8n"
        mock_n8n_settings.n8n_timeout_seconds = 5
        mock_n8n_settings.n8n_verify_tls = False

        # Mock SecretStr for n8n_webhook_secret
        mock_secret = MagicMock()
        mock_secret.get_secret_value.return_value = "test-secret"
        mock_n8n_settings.n8n_webhook_secret = mock_secret

        yield mock_disp_settings, mock_n8n_settings


@pytest.mark.asyncio
async def test_automation_disabled_globally(mock_settings):
    disp_settings, _ = mock_settings
    disp_settings.automation_enabled = False

    dispatcher = AutomationDispatcher()

    event = AutomationEvent(workflow_key="USER_REGISTERED", payload={"user_id": 1})
    result = await dispatcher.dispatch(event)

    assert result.status == AutomationStatus.SKIPPED
    assert "disabled globally" in result.message


@pytest.mark.asyncio
async def test_automation_n8n_disabled(mock_settings):
    disp_settings, n8n_settings = mock_settings
    disp_settings.n8n_enabled = False
    n8n_settings.n8n_enabled = False

    dispatcher = AutomationDispatcher()

    event = AutomationEvent(workflow_key="USER_REGISTERED", payload={"user_id": 1})
    result = await dispatcher.dispatch(event)

    assert result.status == AutomationStatus.SKIPPED
    assert "No automation provider configured" in result.message


@pytest.mark.asyncio
async def test_n8n_adapter_dispatch_success(mock_settings):
    _, n8n_settings = mock_settings

    adapter = N8nAutomationAdapter()
    event = AutomationEvent(workflow_key="USER_REGISTERED", payload={"user_id": 1})

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"X-N8N-Execution-Id": "test-exec-123"}
        mock_post.return_value = mock_response

        result = await adapter.dispatch(event)

        assert result.status == AutomationStatus.DELIVERED
        assert result.execution_id == "test-exec-123"
        assert result.provider == "n8n"


@pytest.mark.asyncio
async def test_n8n_adapter_invalid_workflow(mock_settings):
    adapter = N8nAutomationAdapter()

    event = AutomationEvent(workflow_key="INVALID_KEY", payload={})
    result = await adapter.dispatch(event)

    assert result.status == AutomationStatus.FAILED
    assert "Unknown workflow key" in result.message

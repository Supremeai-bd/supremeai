from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.plugins.capability_resolver import CapabilityResolver


@pytest.mark.asyncio
async def test_resolve_user_capabilities():
    mock_session = AsyncMock()

    # Mock installation
    mock_inst = MagicMock()
    mock_inst.is_enabled = True
    mock_inst.plugin_id = "plugin_1"
    mock_inst.granted_capabilities = ["read", "write"]

    # Mock manifest
    mock_manifest = MagicMock()
    mock_manifest.id = "plugin_1"
    mock_manifest.is_active = True
    mock_manifest.execution_type = "mcp"
    mock_manifest.tools_provided = [
        {"name": "tool_allowed", "permissions": ["read"]},
        {"name": "tool_forbidden", "permissions": ["admin"]},
    ]

    with (
        patch(
            "core.plugins.capability_resolver.PluginLifecycleManager.get_user_installations",
            new_callable=AsyncMock,
        ) as mock_get_inst,
        patch(
            "core.plugins.capability_resolver.PluginManifestRegistry.get_manifest_by_id",
            new_callable=AsyncMock,
        ) as mock_get_manifest,
    ):
        mock_get_inst.return_value = [mock_inst]
        mock_get_manifest.return_value = mock_manifest

        result = await CapabilityResolver.resolve_user_capabilities(mock_session, "user_123")

        assert "tools" in result
        assert len(result["tools"]) == 1
        assert result["tools"][0]["name"] == "tool_allowed"
        assert result["tools"][0]["_source_plugin"] == "plugin_1"
        assert result["tools"][0]["_execution_type"] == "mcp"

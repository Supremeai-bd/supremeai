from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from core.config_proxy import DynamicConfigProxy


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.mark.asyncio
async def test_dynamic_config_proxy_loads_default_when_no_doc(mock_db):
    doc_ref = MagicMock()
    # Mocking snapshot.exists = False
    snapshot = MagicMock()
    snapshot.exists = False
    doc_ref.get.return_value = snapshot

    mock_db.collection.return_value.document.return_value = doc_ref

    proxy = DynamicConfigProxy("tenant-123", mock_db)

    # Should load the fallback defaults
    thresholds = await proxy.get("DEFAULT_CODE_SMELL_THRESHOLDS")
    assert thresholds is not None
    assert thresholds["complexity"] == 10


@pytest.mark.asyncio
async def test_dynamic_config_proxy_loads_from_db(mock_db):
    doc_ref = MagicMock()
    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = {
        "DEFAULT_CODE_SMELL_THRESHOLDS": {"complexity": 20},
        "COMMON_STRINGS_TO_IGNORE": ["a", "b"],
    }
    doc_ref.get.return_value = snapshot
    mock_db.collection.return_value.document.return_value = doc_ref

    proxy = DynamicConfigProxy("tenant-123", mock_db)

    thresholds = await proxy.get("DEFAULT_CODE_SMELL_THRESHOLDS")
    assert thresholds["complexity"] == 20

    strings = await proxy.get("COMMON_STRINGS_TO_IGNORE")
    assert "a" in strings


@pytest.mark.asyncio
async def test_dynamic_config_proxy_raises_runtime_error_on_db_failure(mock_db):
    doc_ref = MagicMock()
    # Simulate DB connection error
    doc_ref.get.side_effect = Exception("DB Connection Timeout")
    mock_db.collection.return_value.document.return_value = doc_ref

    proxy = DynamicConfigProxy("tenant-123", mock_db)

    with pytest.raises(
        RuntimeError, match="Failed to refresh config from DB: DB Connection Timeout"
    ):
        await proxy.get("DEFAULT_CODE_SMELL_THRESHOLDS")


@pytest.mark.asyncio
async def test_dynamic_config_proxy_caches_values(mock_db):
    doc_ref = MagicMock()
    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = {"TEST_KEY": "TEST_VALUE"}
    doc_ref.get.return_value = snapshot
    mock_db.collection.return_value.document.return_value = doc_ref

    proxy = DynamicConfigProxy("tenant-123", mock_db)

    val1 = await proxy.get("TEST_KEY")
    assert val1 == "TEST_VALUE"

    # Change DB value
    snapshot.to_dict.return_value = {"TEST_KEY": "NEW_VALUE"}

    # Should still return cached value because TTL is 1 min
    val2 = await proxy.get("TEST_KEY")
    assert val2 == "TEST_VALUE"

    # Force expire cache
    proxy._expiry = datetime.min.replace(tzinfo=UTC)

    # Now it should fetch the new value
    val3 = await proxy.get("TEST_KEY")
    assert val3 == "NEW_VALUE"

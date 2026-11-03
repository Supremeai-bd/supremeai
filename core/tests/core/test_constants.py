from unittest.mock import MagicMock

import pytest

from core.config_proxy import DynamicConfigProxy
from core.constants import (
    get_common_strings_to_ignore,
    get_default_code_smell_thresholds,
)


@pytest.fixture
def mock_proxy():
    db = MagicMock()
    doc_ref = MagicMock()
    snapshot = MagicMock()
    snapshot.exists = False
    doc_ref.get.return_value = snapshot
    db.collection.return_value.document.return_value = doc_ref

    proxy = DynamicConfigProxy("tenant-123", db)
    return proxy


@pytest.mark.asyncio
async def test_constants_via_proxy(mock_proxy):
    thresholds = await get_default_code_smell_thresholds(mock_proxy)
    assert isinstance(thresholds, dict)
    assert thresholds["complexity"] == 10

    strings_to_ignore = await get_common_strings_to_ignore(mock_proxy)
    assert "utf-8" in strings_to_ignore
    assert "rb" in strings_to_ignore

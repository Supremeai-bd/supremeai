# tests/test_cost_guard_coverage_full.py
"""Comprehensive unit tests for backend/core/cost_guard.py targeting 80%+ line coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.cost_guard import CostGuard


@pytest.mark.asyncio
async def test_connect():
    cg = CostGuard()
    res = await cg.connect()
    assert res == cg


@pytest.mark.asyncio
async def test_check_budget_no_db():
    cg = CostGuard(db=None)
    res = await cg.check_budget("tenant_1", 0.05)
    assert res is True


@pytest.mark.asyncio
async def test_check_budget_with_db_success():
    mock_db = MagicMock()
    mock_doc = MagicMock()
    mock_snapshot = MagicMock()
    mock_snapshot.exists = True
    mock_snapshot.to_dict.return_value = {"monthly_limit": 10.0, "spent_amount": 2.0}
    mock_doc.get.return_value = mock_snapshot
    mock_db.collection.return_value.document.return_value = mock_doc

    cg = CostGuard(db=mock_db)
    res = await cg.check_budget("tenant_1", 1.0)
    assert res is True


@pytest.mark.asyncio
async def test_check_budget_exceeded_raises_http_exception():
    mock_db = MagicMock()
    mock_doc = MagicMock()
    mock_snapshot = MagicMock()
    mock_snapshot.exists = True
    mock_snapshot.to_dict.return_value = {"monthly_limit": 5.0, "spent_amount": 4.5}
    mock_doc.get.return_value = mock_snapshot
    mock_db.collection.return_value.document.return_value = mock_doc

    cg = CostGuard(db=mock_db)
    with pytest.raises(HTTPException) as exc_info:
        await cg.check_budget("tenant_1", 1.0)
    assert exc_info.value.status_code == 402


@pytest.mark.asyncio
async def test_validate_budget_free_tier():
    cg = CostGuard()
    res = await cg.validate_budget("tenant_1", "free")
    assert res is True


@pytest.mark.asyncio
async def test_validate_budget_economy_tier_success():
    cg = CostGuard()
    with patch(
        "core.cache.redis_manager.redis_manager.get_cache", new_callable=AsyncMock
    ) as mock_redis:
        mock_redis.return_value = "0.05"
        res = await cg.validate_budget("tenant_1", "economy")
        assert res is True


@pytest.mark.asyncio
async def test_record_spend():
    cg = CostGuard()
    with patch(
        "core.cache.redis_manager.redis_manager.incrbyfloat", new_callable=AsyncMock
    ) as mock_incr:
        await cg.record_spend("tenant_1", "economy", 0.02)
        mock_incr.assert_called_once()

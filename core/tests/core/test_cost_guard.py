from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from core.cost_guard import CostGuard


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.mark.asyncio
async def test_cost_guard_allows_when_under_budget(mock_db):
    doc_ref = MagicMock()
    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = {"monthly_limit": 10.0, "spent_amount": 5.0}
    doc_ref.get.return_value = snapshot
    mock_db.collection.return_value.document.return_value = doc_ref

    guard = CostGuard(mock_db)
    result = await guard.check_budget("tenant-1", 1.0)
    assert result is True


@pytest.mark.asyncio
async def test_cost_guard_blocks_when_over_budget(mock_db):
    doc_ref = MagicMock()
    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = {"monthly_limit": 10.0, "spent_amount": 9.5}
    doc_ref.get.return_value = snapshot
    mock_db.collection.return_value.document.return_value = doc_ref

    guard = CostGuard(mock_db)
    with pytest.raises(HTTPException) as exc:
        await guard.check_budget("tenant-1", 1.0)

    assert exc.value.status_code == 402
    assert "Budget Exceeded" in exc.value.detail


@pytest.mark.asyncio
async def test_cost_guard_blocks_when_no_budget_doc(mock_db):
    doc_ref = MagicMock()
    snapshot = MagicMock()
    snapshot.exists = False
    doc_ref.get.return_value = snapshot
    mock_db.collection.return_value.document.return_value = doc_ref

    guard = CostGuard(mock_db)
    with pytest.raises(HTTPException) as exc:
        await guard.check_budget("tenant-1", 1.0)

    assert exc.value.status_code == 402
    assert "No budget configured" in exc.value.detail


@pytest.mark.asyncio
async def test_cost_guard_raises_runtime_error_on_db_failure(mock_db):
    doc_ref = MagicMock()
    doc_ref.get.side_effect = Exception("Firestore Offline")
    mock_db.collection.return_value.document.return_value = doc_ref

    guard = CostGuard(mock_db)
    with pytest.raises(RuntimeError, match="CostGuard failed to verify budget: Firestore Offline"):
        await guard.check_budget("tenant-1", 1.0)

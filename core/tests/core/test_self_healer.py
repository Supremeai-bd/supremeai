import re
from unittest.mock import MagicMock

import pytest

from core.health.self_healer import SelfHealerService


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.mark.asyncio
async def test_self_healer_propose_fix_success(mock_db):
    doc_ref = MagicMock()
    mock_db.collection.return_value.document.return_value = doc_ref

    service = SelfHealerService(mock_db)

    fix_id = await service.propose_fix(
        tenant_id="tenant-1",
        error_pattern="ValueError: unknown field",
        proposed_fix="def fix():\n    pass",
        impact_score=0.5,
        dependency_tree=["core.utils"],
    )

    assert fix_id.startswith("fix-")
    doc_ref.set.assert_called_once()

    # Verify the payload
    call_args = doc_ref.set.call_args[0][0]
    assert call_args["status"] == "pending_review"
    assert call_args["error_pattern"] == "ValueError: unknown field"
    assert call_args["impact_score"] == 0.5
    assert call_args["dependency_tree"] == ["core.utils"]
    assert call_args["trace_id"].startswith("err-trace-")


@pytest.mark.asyncio
async def test_self_healer_rejects_dangerous_code(mock_db):
    service = SelfHealerService(mock_db)

    with pytest.raises(ValueError, match="Dangerous keyword 'exec\\(' detected"):
        await service.propose_fix(
            tenant_id="tenant-1",
            error_pattern="Any error",
            proposed_fix="exec('echo malicious_payload_blocked')",
            impact_score=0.1,
            dependency_tree=[],
        )


@pytest.mark.asyncio
async def test_self_healer_rejects_invalid_impact_score(mock_db):
    service = SelfHealerService(mock_db)

    with pytest.raises(ValueError, match=re.escape("Impact score must be between 0.0 and 1.0")):
        await service.propose_fix(
            tenant_id="tenant-1",
            error_pattern="Any error",
            proposed_fix="valid code",
            impact_score=1.5,
            dependency_tree=[],
        )


@pytest.mark.asyncio
async def test_self_healer_test_sandbox_placeholder(mock_db):
    service = SelfHealerService(mock_db)
    result = await service.propose_fix(
        tenant_id="tenant-1",
        error_pattern="Any error",
        proposed_fix="pass",
        impact_score=0.1,
        dependency_tree=[],
    )
    assert isinstance(result, str)

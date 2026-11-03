from unittest.mock import AsyncMock, Mock

import pytest

from core.knowledge_contract import KnowledgeContractError, request_from_user
from core.knowledge_facade import KnowledgeFacade


def test_request_requires_security_context():
    with pytest.raises(KnowledgeContractError):
        request_from_user("hello", {"sub": "actor"})


def test_request_normalizes_limit_and_context():
    request = request_from_user(
        "hello", {"sub": "actor", "tenant_id": "tenant", "role": "Admin"}, 99
    )
    assert request.tenant_id == "tenant"
    assert request.actor_id == "actor"
    assert request.role == "admin"
    assert request.limit == 5


@pytest.mark.asyncio
async def test_facade_adapts_public_request_to_legacy_service():
    service = Mock()
    service.answer = AsyncMock(return_value={"answer": "grounded", "citations": []})
    result = await KnowledgeFacade(service).ask(
        request_from_user("hello", {"sub": "a", "tenant_id": "t", "role": "Admin"})
    )
    assert result["answer"] == "grounded"
    service.answer.assert_awaited_once()
    assert service.answer.await_args.args[1] == {"tenant_id": "t", "sub": "a", "role": "admin"}

import pytest

from core.orchestration.conversation_orchestrator import (
    ConversationCommand,
    get_conversation_orchestrator,
)


@pytest.mark.asyncio
async def test_task_spoke_returns_scoped_task(monkeypatch):
    orchestrator = get_conversation_orchestrator()
    result = await orchestrator.dispatch(
        ConversationCommand("create a task to inspect the project", "user-1", "tenant-1")
    )
    assert result.status == "completed"
    assert result.response["spoke"] == "task"
    assert result.response["tenant_id"] == "tenant-1"
    assert result.response["task_id"]


@pytest.mark.asyncio
async def test_admin_spoke_fails_closed_for_user():
    result = await get_conversation_orchestrator().dispatch(
        ConversationCommand("show admin system settings", "user-1", "tenant-1")
    )
    assert result.status == "denied"
    assert result.error == "Admin permission required"

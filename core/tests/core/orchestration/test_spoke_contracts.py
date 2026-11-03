import pytest

from core.orchestration.conversation_orchestrator import get_conversation_orchestrator


@pytest.mark.parametrize(
    "capability",
    ["chat", "memory", "browser", "task", "realtime", "artifact", "external", "admin", "evolution"],
)
def test_all_core_spokes_are_registered(capability):
    names = {item["name"] for item in get_conversation_orchestrator().capabilities()}
    assert capability in names


@pytest.mark.asyncio
async def test_unknown_capability_is_fail_closed(monkeypatch):
    orchestrator = get_conversation_orchestrator()
    monkeypatch.setattr(orchestrator, "classify", staticmethod(lambda _: "unknown"))
    from core.orchestration.conversation_orchestrator import ConversationCommand

    result = await orchestrator.dispatch(ConversationCommand("x", "u", "t"))
    assert result.status == "failed"
    assert result.error == "Capability unavailable"

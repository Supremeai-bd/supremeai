"""Owned vector memory must fail closed across the real backend seams."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from core.services import memory_service as ms

pytestmark = pytest.mark.asyncio

OWNER = "fixture-owner"
SESSION = "fixture-session"
OWNED = {"user_id": OWNER, "session_id": SESSION, "similarity": 0.9, "summary": "in scope"}
ROWS = [
    {**OWNED, "user_id": "fixture-other", "summary": "other owner"},
    {**OWNED, "session_id": "other-session", "summary": "other session"},
    {"session_id": SESSION, "similarity": 1.0, "summary": "unverifiable"},
    {**OWNED, "similarity": 0.3, "summary": "below threshold"},
    OWNED,
]


async def test_recall_requires_owner_before_backend_access(monkeypatch):
    get_backend = Mock(side_effect=AssertionError("unexpected vector client"))
    monkeypatch.setattr(ms, "_get_supabase", get_backend)
    assert await ms.recall_memories(task_description="prompt", session_id=SESSION) == []
    get_backend.assert_not_called()


async def test_scoped_rpc_and_its_returned_rows_are_verified(monkeypatch):
    sb = Mock()
    sb.rpc.return_value.execute.return_value = SimpleNamespace(data=ROWS)
    monkeypatch.setattr(ms, "_get_supabase", lambda: sb)
    monkeypatch.setattr(ms, "get_embedding", lambda _: [0.1])
    result = await ms.recall_memories(task_description="prompt", user_id=OWNER, session_id=SESSION)
    assert result == [OWNED]
    sb.rpc.assert_called_once_with(
        "match_ai_memories",
        {"query_embedding": [0.1], "match_count": 10, "match_threshold": 0.65,
         "filter_user_id": OWNER, "filter_session_id": SESSION},
    )


async def test_rpc_failure_cannot_return_unfiltered_cascade_rows(monkeypatch):
    sb = Mock()
    sb.rpc.side_effect = RuntimeError("fixture stale schema")
    cascade = Mock(return_value=ROWS)
    monkeypatch.setattr(ms, "_get_supabase", lambda: sb)
    monkeypatch.setattr(ms, "get_embedding", lambda _: [0.1])
    monkeypatch.setattr(ms.memory_service, "query_context", cascade)
    result = await ms.recall_memories(task_description="prompt", user_id=OWNER, session_id=SESSION)
    cascade.assert_called_once_with("prompt", user_id=OWNER, session_id=SESSION, top_k=10)
    assert result == [OWNED]


@pytest.mark.parametrize("degraded", [False, True])
async def test_owner_cannot_use_unscoped_file_memory(monkeypatch, tmp_path, degraded):
    if degraded:
        monkeypatch.setattr(ms.pooled_pg, "is_available", lambda: False)
        monkeypatch.setattr(ms, "sqlite_fallback_allowed", lambda _: False)
        monkeypatch.setattr(ms, "durable_state", lambda _: Mock(mirror_items=lambda: {}))
        store = ms.CascadeMemoryService()
    else:
        store = ms.CascadeMemoryService(db_path=str(tmp_path / "memory.db"))
    monkeypatch.setattr(store, "_embed", lambda _: [1.0])
    store.store_memory("some-file", "unscoped contents", "legacy fixture", "{}")
    assert store.retrieve_memories()
    assert store.query_context("legacy fixture")
    assert store.retrieve_memories(user_id=OWNER) == []
    assert store.query_context("legacy fixture", user_id=OWNER, session_id=SESSION) == []
    monkeypatch.setattr(ms, "_get_supabase", lambda: None)
    monkeypatch.setattr(ms, "get_embedding", lambda _: [1.0])
    monkeypatch.setattr(ms, "memory_service", store)
    assert await ms.recall_memories(task_description="legacy fixture", user_id=OWNER) == []
    outcome = await ms.save_memory(session_id=SESSION, summary="private entry", user_id=OWNER)
    assert outcome["success"] is False
    assert all(row["summary"] != "private entry" for row in store.retrieve_memories())


async def test_checkpoint_and_window_namespace_keep_distinct_subjects():
    from api.routes.memory import _owned_checkpoint_key, _owned_window_session

    for key in (_owned_checkpoint_key, _owned_window_session):
        assert key({"sub": "fixture:a"}, "same") != key({"sub": "fixture_a"}, "same")
        assert key({"sub": "fixture/a"}, "same") != key({"sub": "fixture_a"}, "same")
        assert key({"sub": "fixture_a"}, "same") != key({"sub": "fixture_a"}, "other")
        with pytest.raises(HTTPException) as exc:
            key({"tenant_id": "not-a-subject"}, "same")
        assert exc.value.status_code == 401


async def test_vector_route_uses_verified_subject_before_contacting_store(monkeypatch):
    from api.routes.memory import VectorRecallRequest, vector_recall
    from services import memory_service
    recall = AsyncMock(return_value=[OWNED])
    monkeypatch.setattr(memory_service, "recall_memories", recall)
    req = VectorRecallRequest(task_description="same prompt")
    with pytest.raises(HTTPException) as exc:
        await vector_recall(req, {"tenant_id": OWNER})
    assert exc.value.status_code == 401
    recall.assert_not_awaited()
    resp = await vector_recall(req, {"sub": OWNER, "tenant_id": "workspace"})
    assert resp["memories"] == [OWNED]
    recall.assert_awaited_once_with(task_description="same prompt", user_id=OWNER, limit=5, threshold=0.6)


async def test_orchestrated_recall_keeps_requested_session_with_verified_owner(monkeypatch):
    from core.orchestration.conversation_orchestrator import ConversationCommand, _memory_handler
    from services import memory_service

    recall = AsyncMock(return_value=[OWNED])
    monkeypatch.setattr(memory_service, "recall_memories", recall)
    command = ConversationCommand("fixture", OWNER, "workspace", metadata={"session_id": SESSION})
    assert await _memory_handler(command) == [OWNED]
    recall.assert_awaited_once_with(
        task_description="fixture", limit=3, threshold=0.55, user_id=OWNER, session_id=SESSION,
    )


async def test_orchestrated_chat_is_attributed_and_rejects_failure(monkeypatch):
    from core.llm.llm_gateway import llm_gateway
    from core.orchestration.conversation_orchestrator import ConversationCommand, _chat_handler

    complete = AsyncMock(side_effect=[{"success": True, "text": "actual reply"}, {"success": False, "text": "error"}])
    monkeypatch.setattr(llm_gateway, "acompletion", complete)
    command = ConversationCommand("fixture", OWNER, "workspace", metadata={"correlation_id": "fixture-trace"})
    assert await _chat_handler(command) == "actual reply"
    context = complete.await_args.kwargs["context"]
    assert (context.tenant_id, context.task_type, context.correlation_id) == ("workspace", "chat", "fixture-trace")
    with pytest.raises(RuntimeError, match="No chat result"):
        await _chat_handler(command)

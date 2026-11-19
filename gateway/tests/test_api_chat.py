from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from api.routes import chat
from api.routes.chat import ChatPayload, get_completion, stream_chat


class FakeCache:
    def __init__(self, value=None):
        self.value = value
        self.saved = None

    async def get(self, **scope):
        self.read = scope
        return self.value

    async def set(
        self,
        prompt: str,
        response: str,
        model_name: str,
        session_id: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ):
        self.saved = {
            "prompt": prompt,
            "response": response,
            "model_name": model_name,
            "session_id": session_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
        }


@pytest.fixture(autouse=True)
def _isolate_chat_backends(monkeypatch):
    monkeypatch.setattr(chat, "main_llm_circuit", SimpleNamespace(
        should_attempt_external=AsyncMock(return_value=True),
        record_failure=AsyncMock(), record_success=AsyncMock(),
    ))
    monkeypatch.setattr(chat, "llm_gateway", SimpleNamespace(
        performance_optimizer=SimpleNamespace(optimize_model_selection=AsyncMock(return_value="fixture/selected")),
        acompletion=AsyncMock(side_effect=AssertionError("Unexpected completion")),
    ))
    monkeypatch.setattr(chat, "language_loop_enabled", lambda: False)
    monkeypatch.setattr(chat, "context_engine_enabled", lambda: True)
    monkeypatch.setattr("services.memory_service.recall_memories", AsyncMock(return_value=[]))


def _db(owner):
    return SimpleNamespace(tenant_id=owner, workspace_id="fixture-workspace")


@pytest.mark.asyncio
async def test_get_completion_returns_cached_result(monkeypatch):
    fake_cache = FakeCache(
        value={
            "success": True,
            "response": "cached-response",
            "source": "L5_CACHE",
            "latency_ms": 10,
        }
    )
    monkeypatch.setattr("api.routes.chat.multi_layer_cache", fake_cache)
    request = SimpleNamespace(headers={"X-Session-ID": "session-1"})
    payload = ChatPayload(prompt="hello")
    result = await get_completion(request, payload, db=_db("tenant-1"))

    assert result["cached"] is True
    assert result["response"] == "cached-response"
    assert result["cache_source"] == "L5_CACHE"


@pytest.mark.asyncio
async def test_get_completion_generates_response_and_saves_cache(monkeypatch):
    fake_cache = FakeCache(value=None)
    monkeypatch.setattr("api.routes.chat.multi_layer_cache", fake_cache)

    captured: dict = {}

    async def mock_acompletion(
        prompt, context=None, model=None, **_kwargs
    ):  # #2829: নতুন গেটওয়ে-চুক্তি — model-ওভাররাইড (#2726) + persona-enriched prompt (#2728)
        captured["prompt"] = prompt
        captured["model"] = model
        captured["context"] = context
        if prompt == "raise-error":
            raise RuntimeError("boom")
        return {"success": True, "model": model, "text": f"generated:{prompt}"}

    recall = AsyncMock(return_value=[{"summary": "recalled fixture context"}])
    monkeypatch.setattr(chat.llm_gateway, "acompletion", mock_acompletion)
    monkeypatch.setattr("services.memory_service.recall_memories", recall)

    request = SimpleNamespace(headers={"X-Session-ID": "session-2"})
    payload = ChatPayload(prompt="live-prompt", model_name="untrusted-model-hint")
    result = await get_completion(request, payload, db=_db("tenant-2"))

    assert result["cached"] is False
    # #2828/#2829 পরিবার: enriched prompt-চুক্তি — persona ব্লক (#2728) + raw prompt দুটোই
    # gateway-প্রম্পটে উপস্থিত; রেসপন্স আর বিশুদ্ধ "generated:live-prompt" নয়।
    assert result["response"].startswith("generated:")
    assert "recalled fixture context" in captured["prompt"]
    assert "live-prompt" in captured["prompt"]
    assert "live-prompt" in result["response"]
    # Model selection is server-owned and shared by cache and inference.
    assert captured["model"] == "fixture/selected"
    assert captured["context"] is not None
    assert captured["context"].tenant_id == "tenant-2"
    assert fake_cache.saved == {**fake_cache.read, "response": result["response"]}
    assert fake_cache.saved["prompt"] == captured["prompt"]
    assert fake_cache.saved["user_id"] == "tenant-2"
    assert fake_cache.saved["tenant_id"] == "fixture-workspace"
    assert fake_cache.saved["session_id"] == "session-2"
    assert fake_cache.saved["model_name"] == captured["model"]
    chat.llm_gateway.performance_optimizer.optimize_model_selection.assert_awaited_once_with("chat", captured["prompt"])
    recall.assert_awaited_once_with(
        task_description="live-prompt", user_id="tenant-2", session_id="session-2", limit=3, threshold=0.55,
    )


@pytest.mark.asyncio
async def test_get_completion_returns_graceful_fallback_on_model_failure(monkeypatch):
    fake_cache = FakeCache(value=None)
    monkeypatch.setattr("api.routes.chat.multi_layer_cache", fake_cache)

    async def mock_acompletion(
        prompt, context=None, model=None, **_kwargs
    ):  # #2829: সিগনেচার-চুক্তি বর্তমান গেটওয়ে-কলের সাথে সঙ্গত — ফলব্যাক
        # পথ এখন সত্যিকারের মডেল-ব্যর্থতা (RuntimeError) থেকেই অনুশীলিত হয়,
        # স্টেল-সিগনেচার TypeError থেকে নয়।
        raise RuntimeError("boom")

    async def mock_recall_memories(*args, **kwargs):
        return []

    monkeypatch.setattr(chat.llm_gateway, "acompletion", mock_acompletion)
    monkeypatch.setattr("services.memory_service.recall_memories", mock_recall_memories)

    request = SimpleNamespace(headers={"X-Session-ID": "session-3"})
    payload = ChatPayload(prompt="raise-error")

    result = await get_completion(request, payload, db=_db("tenant-3"))

    assert result["success"] is False
    assert result["source"] == "no_match"
    assert "দুঃখিত" in result["response"]


@pytest.mark.asyncio
async def test_stream_chat_yields_sse_chunks(monkeypatch):
    async def mock_acompletion(
        prompt, context=None, model=None, **_kwargs
    ):  # #2829: streaming পথেও একই চুক্তি — model-ওভাররাইড (#2726) +
        # persona-enriched prompt (#2728) + InferenceContext(stream=True)
        class Response:
            async def __aiter__(self):
                yield "chunk-one"
                yield "chunk-two"

        return Response()

    monkeypatch.setattr(chat.llm_gateway, "acompletion", mock_acompletion)
    request_payload = ChatPayload(prompt="stream-prompt")
    response = await stream_chat(request_payload, db=_db("tenant-4"))

    assert response.media_type == "text/event-stream"

    body = b""
    async for chunk in response.body_iterator:
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")
        body += chunk

    assert b"chunk-one" in body
    assert b"chunk-two" in body


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("session_id", [None, "fixture-session"])
@pytest.mark.asyncio
async def test_provider_failure_never_opens_unscoped_recall(monkeypatch, stream, session_id):
    from services import memory_service

    recall = AsyncMock(return_value=[])
    monkeypatch.setattr(memory_service, "recall_memories", recall)
    monkeypatch.setattr(chat, "multi_layer_cache", FakeCache())
    llm = AsyncMock(side_effect=RuntimeError("fixture provider unavailable"))
    monkeypatch.setattr(chat.llm_gateway, "acompletion", llm)
    payload = ChatPayload(prompt="fixture question")
    if stream:
        response = await stream_chat(payload, db=_db("fixture-owner"), session_id=session_id)
        parts = [part async for part in response.body_iterator]
        assert not any("[DONE]" in part for part in parts)
        assert any('"error"' in part for part in parts)
    else:
        headers = {"X-Session-ID": session_id} if session_id else {}
        result = await get_completion(SimpleNamespace(headers=headers), payload, db=_db("fixture-owner"))
        assert result["source"] == "no_match"
    llm.assert_awaited_once()
    if session_id:
        assert [call.kwargs["threshold"] for call in recall.await_args_list] == [0.55, 0.75]
        assert all(call.kwargs["user_id"] == "fixture-owner" for call in recall.await_args_list)
        assert all(call.kwargs["session_id"] == session_id for call in recall.await_args_list)
    else:
        recall.assert_not_awaited()


@pytest.mark.asyncio
async def test_fallback_model_answer_is_not_reused_as_primary(monkeypatch):
    cache = FakeCache()
    monkeypatch.setattr(chat, "multi_layer_cache", cache)
    chat.llm_gateway.acompletion.side_effect = None
    chat.llm_gateway.acompletion.return_value = {"success": True, "model": "fixture/fallback", "text": "fallback"}
    request = SimpleNamespace(headers={"X-Session-ID": "same-session"})
    result = await get_completion(request, ChatPayload(prompt="hello"), db=_db("fixture-owner"))
    assert result["response"] == "fallback" and result["cached"] is False
    assert cache.saved is None


@pytest.mark.parametrize("provider_answer", [None, {"success": False, "text": "fake answer"}, {"success": True, "text": ""}])
@pytest.mark.asyncio
async def test_no_answer_is_not_reported_as_a_success(monkeypatch, provider_answer):
    cache = FakeCache()
    monkeypatch.setattr(chat, "multi_layer_cache", cache)
    chat.llm_gateway.acompletion.side_effect = None
    chat.llm_gateway.acompletion.return_value = provider_answer
    result = await get_completion(SimpleNamespace(headers={}), ChatPayload(prompt="hello"), db=_db("fixture-owner"))
    assert result["success"] is False and result["source"] == "no_match"
    assert cache.saved is None
    chat.main_llm_circuit.record_failure.assert_awaited_once()
    chat.main_llm_circuit.record_success.assert_not_awaited()


@pytest.mark.asyncio
async def test_cache_failure_does_not_hide_a_real_answer(monkeypatch):
    cache = SimpleNamespace(get=AsyncMock(side_effect=OSError), set=AsyncMock(side_effect=OSError))
    monkeypatch.setattr(chat, "multi_layer_cache", cache)
    chat.llm_gateway.acompletion.side_effect = None
    chat.llm_gateway.acompletion.return_value = {"success": True, "model": "fixture/selected", "text": "actual reply"}
    result = await get_completion(SimpleNamespace(headers={}), ChatPayload(prompt="hello"), db=_db("fixture-owner"))
    assert result["success"] and result["response"] == "actual reply" and not result["cached"]
    cache.get.assert_awaited_once()
    cache.set.assert_awaited_once()
    chat.main_llm_circuit.record_failure.assert_not_awaited()


@pytest.mark.asyncio
async def test_partial_stream_has_no_memory_replay_or_success_marker(monkeypatch):
    from services import memory_service

    async def interrupted():
        yield "partial provider reply"
        raise ConnectionError("fixture disconnect")

    chat.llm_gateway.acompletion.side_effect = None
    chat.llm_gateway.acompletion.return_value = interrupted()
    recall = AsyncMock(return_value=[])
    monkeypatch.setattr(memory_service, "recall_memories", recall)
    response = await stream_chat(ChatPayload(prompt="hello"), db=_db("fixture-owner"), session_id="fixture-session")
    body = "".join([chunk async for chunk in response.body_iterator])
    assert "partial provider reply" in body and '"error"' in body and "[DONE]" not in body
    recall.assert_awaited_once()
    chat.main_llm_circuit.record_success.assert_not_awaited()

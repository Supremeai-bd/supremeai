from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.routes.chat import ChatPayload, get_completion, stream_chat


class FakeCache:
    def __init__(self, value=None):
        self.value = value
        self.saved = None

    async def get(self, prompt: str, model_name: str, session_id: str = None, user_id: str = None):
        # AUD-5.6: chat now passes user_id for user-scoped cache keys.
        return self.value

    async def set(
        self,
        prompt: str,
        response: str,
        model_name: str,
        session_id: str = None,
        user_id: str = None,
    ):
        self.saved = {
            "prompt": prompt,
            "response": response,
            "model_name": model_name,
            "session_id": session_id,
            "user_id": user_id,
        }


class FakeModel:
    def __init__(self, model_name: str):
        self.model_name = model_name

    async def generate_content_async(self, prompt: str, stream: bool = False):
        if prompt == "raise-error":
            raise RuntimeError("boom")
        return SimpleNamespace(text=f"generated:{prompt}")


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
    result = await get_completion(request, payload, db=SimpleNamespace(tenant_id="tenant-1"))

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
        return {"text": f"generated:{prompt}"}

    async def mock_recall_memories(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "api.routes.chat.llm_gateway", SimpleNamespace(acompletion=mock_acompletion)
    )
    monkeypatch.setattr("services.memory_service.recall_memories", mock_recall_memories)

    request = SimpleNamespace(headers={"X-Session-ID": "session-2"})
    payload = ChatPayload(prompt="live-prompt")
    result = await get_completion(request, payload, db=SimpleNamespace(tenant_id="tenant-2"))

    assert result["cached"] is False
    # #2828/#2829 পরিবার: enriched prompt-চুক্তি — persona ব্লক (#2728) + raw prompt দুটোই
    # gateway-প্রম্পটে উপস্থিত; রেসপন্স আর বিশুদ্ধ "generated:live-prompt" নয়।
    assert result["response"].startswith("generated:")
    assert "[System Instructions]" in captured["prompt"]
    assert "live-prompt" in captured["prompt"]
    assert "live-prompt" in result["response"]
    # #2726-চুক্তি: ডিফল্ট model_name ("gemini-2.5-pro") → কোনো ওভাররাইড নয়;
    # context বাধ্যতামূলক InferenceContext, tenant-attribution সংরক্ষিত।
    assert captured["model"] is None
    assert captured["context"] is not None
    assert captured["context"].tenant_id == "tenant-2"
    # cache-চুক্তি অপরিবর্তিত: raw prompt + payload-এর model_name দিয়ে সেভ
    assert fake_cache.saved is not None
    assert fake_cache.saved["model_name"] == "gemini-2.5-pro"


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

    monkeypatch.setattr(
        "api.routes.chat.llm_gateway", SimpleNamespace(acompletion=mock_acompletion)
    )
    monkeypatch.setattr("services.memory_service.recall_memories", mock_recall_memories)

    request = SimpleNamespace(headers={"X-Session-ID": "session-3"})
    payload = ChatPayload(prompt="raise-error")

    result = await get_completion(request, payload, db=SimpleNamespace(tenant_id="tenant-3"))

    assert result["success"] is True
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

    monkeypatch.setattr(
        "api.routes.chat.llm_gateway", SimpleNamespace(acompletion=mock_acompletion)
    )
    request_payload = ChatPayload(prompt="stream-prompt")
    response = await stream_chat(request_payload, db=SimpleNamespace(tenant_id="tenant-4"))

    assert response.media_type == "text/event-stream"

    body = b""
    async for chunk in response.body_iterator:
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")
        body += chunk

    assert b"chunk-one" in body
    assert b"chunk-two" in body

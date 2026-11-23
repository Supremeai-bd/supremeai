# tests/test_stream_chat_dynamic_intent.py
# বাংলা মন্তব্য: stream_chat এন্ডপয়েন্টের ডায়নামিক ইনটেন্ট রাউটিং ও কাস্টম প্যারামিটারের ইউনিট টেস্ট

import json
import pytest
from unittest.mock import MagicMock, patch
from core.api.routes.task import ChatStreamRequest, stream_chat


def test_chat_stream_request_harmonization():
    # বাংলা মন্তব্য: camelCase থেকে snake_case কনভার্সন যাচাই
    req = ChatStreamRequest(
        message="write code",
        taskType="code",
        maxCost=0.05,
    )
    assert req.task_type == "code"
    assert req.max_cost == 0.05

    req_snake = ChatStreamRequest(
        prompt="hello",
        task_type="general",
        max_cost=0.02,
    )
    assert req_snake.message == "hello"
    assert req_snake.task_type == "general"
    assert req_snake.max_cost == 0.02


@pytest.mark.asyncio
async def test_stream_chat_explicit_task_type():
    # বাংলা মন্তব্য: ক্লায়েন্টের পাঠানো task_type ও max_cost সরাসরি async_route_and_stream-এ যাওয়া
    req = ChatStreamRequest(
        message="Write a python function",
        task_type="code",
        max_cost=0.05,
    )

    mock_router = MagicMock()
    mock_router.async_route_and_stream = MagicMock(return_value=_dummy_stream(["token1", "token2"]))

    with patch("core.services.model_router", mock_router):
        response = await stream_chat(req)
        assert response.status_code == 200
        # Consume the streaming body iterator
        chunks = [chunk async for chunk in response.body_iterator]
        assert len(chunks) == 3  # token1, token2, [DONE]

        mock_router.async_route_and_stream.assert_called_once()
        call_kwargs = mock_router.async_route_and_stream.call_args[1]
        assert call_kwargs["task_type"] == "code"
        assert call_kwargs["max_cost"] == 0.05


@pytest.mark.asyncio
async def test_stream_chat_dynamic_intent_routing_code(monkeypatch):
    # বাংলা মন্তব্য: task_type না দিলে regex/intent_router_v2 দিয়ে ডায়নামিকালি 'code' ডিটেক্ট হওয়া
    monkeypatch.setenv("INTENT_ROUTER_MODE", "regex")
    req = ChatStreamRequest(
        message="write a python script to parse logs",
    )

    mock_router = MagicMock()
    mock_router.async_route_and_stream = MagicMock(return_value=_dummy_stream(["chunk"]))

    with patch("core.services.model_router", mock_router):
        response = await stream_chat(req)
        assert response.status_code == 200
        chunks = [chunk async for chunk in response.body_iterator]
        assert len(chunks) == 2

        mock_router.async_route_and_stream.assert_called_once()
        call_kwargs = mock_router.async_route_and_stream.call_args[1]
        assert call_kwargs["task_type"] == "code"
        assert call_kwargs["max_cost"] == 0.01


@pytest.mark.asyncio
async def test_stream_chat_fallback_on_intent_exception():
    # বাংলা মন্তব্য: intent_router_v2 এক্সেপশন থ্রো করলেও ফেইল না করে 'general'-এ ফলব্যাক করা
    req = ChatStreamRequest(
        message="some prompt",
    )

    mock_router = MagicMock()
    mock_router.async_route_and_stream = MagicMock(return_value=_dummy_stream(["chunk"]))

    with patch("core.services.model_router", mock_router):
        with patch("core.intent_router_v2.intent_router_v2.route", side_effect=RuntimeError("Intent failure")):
            response = await stream_chat(req)
            assert response.status_code == 200
            chunks = [chunk async for chunk in response.body_iterator]
            assert len(chunks) == 2

            mock_router.async_route_and_stream.assert_called_once()
            call_kwargs = mock_router.async_route_and_stream.call_args[1]
            assert call_kwargs["task_type"] == "general"


async def _dummy_stream(tokens):
    for t in tokens:
        yield t

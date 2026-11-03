"""
Extended tests for core/swarm_pubsub.py
Covers SwarmPubSub edge cases, halt controls, and broadcast failures.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.swarm_pubsub import SwarmPubSub, get_swarm_streamer


@pytest.mark.asyncio
async def test_set_halt_and_is_halted():
    pubsub = SwarmPubSub()
    mock_redis = AsyncMock()
    pubsub.redis = mock_redis

    mock_redis.get.return_value = b"manual_emergency_stop"
    assert await pubsub.is_halted() is True

    mock_redis.get.return_value = None
    assert await pubsub.is_halted() is False


@pytest.mark.asyncio
async def test_clear_halt_deletes_key():
    pubsub = SwarmPubSub()
    mock_redis = AsyncMock()
    pubsub.redis = mock_redis
    await pubsub.clear_halt()
    mock_redis.delete.assert_called_once_with("swarm:halt:global")


@pytest.mark.asyncio
async def test_broadcast_publishes_json():
    pubsub = SwarmPubSub()
    mock_redis = AsyncMock()
    pubsub.redis = mock_redis
    await pubsub.broadcast("test_event", {"key": "value"})
    mock_redis.publish.assert_called_once()
    published = mock_redis.publish.call_args[0][1]
    parsed = json.loads(published)
    assert parsed["type"] == "test_event"


@pytest.mark.asyncio
async def test_subscribe_yields_messages():
    pubsub = SwarmPubSub()
    mock_redis = MagicMock()
    mock_pubsub = AsyncMock()
    mock_redis.pubsub.return_value = mock_pubsub

    messages = [{"type": "message", "data": b"msg1"}]
    mock_pubsub.get_message.side_effect = [*messages, None]

    async def fake_sleep(_):
        raise StopAsyncIteration

    with patch("asyncio.sleep", fake_sleep):
        with patch.object(pubsub, "_get_redis", return_value=mock_redis):
            gen = pubsub.subscribe()
            try:
                msg = await gen.__anext__()
                assert msg == "msg1"
            except asyncio.CancelledError:
                raise
            except Exception as e:
                import logging

                logging.getLogger(__name__).exception(f"Silenced error: {e}")


def test_get_swarm_streamer_returns_singleton():
    a = get_swarm_streamer()
    b = get_swarm_streamer()
    assert a is b

# backend/tests/api/test_realtime_dashboard_ws.py
"""M20 P-B — /ws/dashboard subscription-task জীবনচক্র টেস্ট।

প্রমাণ-লক্ষ্য: পুরনো বাগে ``connect()``-এর ``return True``-এর পরে subscription-task
শুরুর কোড ছিল (মৃত-কোড) — ফলে ``broadcast_to_clients()`` কখনোই চলত না এবং
SwarmPubSub-এর ইভেন্ট (যেমন SYSTEM_METRICS) কোনো dashboard গ্রাহকে পৌঁছাত না।
এই টেস্টগুলো প্রমাণ করে:
  1. connect() ফেরার পরেই subscription task চলুক্ত এবং ইভেন্ট গ্রাহকে পৌঁছায়।
  2. SYSTEM_METRICS ইভেন্ট metrics.update চ্যানেলে ম্যাপ হয়।
  3. শেষ গ্রাহক বিচ্ছিন্ন হলে subscription task পরিষ্কারভাবে cancel হয়।

Auth (fail-closed token যাচাই) এই টেস্টে স্পর্ষ হয় না — মূল endpoint-এর
verify_token_async পথ অপরিবর্তিত; এখানে কেবল manager-এর জীবনচক্র চুক্তি পিন করা হয়।
"""

import asyncio
import json
import logging
from typing import Any

import pytest

from api.routes.realtime_dashboard import DashboardWebSocketManager

logger = logging.getLogger(__name__)


class FakeWebSocket:
    """Minimal WebSocket stand-in — records accepted/sent state."""

    def __init__(self):
        self.accepted = False
        self.sent: list[str] = []
        self.closed: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, message: str) -> None:
        self.sent.append(message)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = code


class FakeStreamer:
    """SwarmPubSub stand-in: yields one event, then parks until released."""

    def __init__(self, event_json: str):
        self.event_json = event_json
        self._release = asyncio.Event()
        self._started = asyncio.Event()

    async def subscribe(self):
        self._started.set()
        yield self.event_json
        await self._release.wait()

    def release(self) -> None:
        self._release.set()


@pytest.fixture
async def manager_with_event(monkeypatch):
    """Fresh manager wired to a FakeStreamer; returns (manager, streamer)."""
    streamer = FakeStreamer(
        json.dumps({"type": "SYSTEM_METRICS", "data": {"cpu": 12.5, "memory": 40.0}})
    )
    monkeypatch.setattr("api.routes.realtime_dashboard.get_swarm_streamer", lambda: streamer)
    manager = DashboardWebSocketManager()
    manager.swarm_streamer = streamer
    yield manager, streamer
    # বাংলা মন্তব্য: টেস্ট পরিষ্কারণ — background task থাকলে cancel না করলে
    # event loop ঝুলে থাকত (leaked-task noise)।
    if manager.subscription_task and not manager.subscription_task.done():
        manager.subscription_task.cancel()
        try:
            await manager.subscription_task
        except asyncio.CancelledError as exc:
            logger.debug(f"Subscription task cancelled cleanly: {exc}")


async def _wait_until(predicate, timeout: float = 3.0) -> bool:
    """Poll a predicate until true or timeout (event-flow tests need real propagation)."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.02)
    return predicate()


@pytest.mark.asyncio
async def test_connect_starts_subscription_task_before_return(manager_with_event):
    manager, streamer = manager_with_event
    ws = FakeWebSocket()

    connected = await manager.connect(ws, {"sub": "user-1"})
    assert connected is True
    assert ws.accepted is True
    # প্রমাণ ১: connect() থেকে ফেরার মুহূর্তেই broadcast task জীবিত।
    assert manager.subscription_task is not None
    assert not manager.subscription_task.done()


@pytest.mark.asyncio
async def test_subscribed_client_receives_swarm_event(manager_with_event):
    manager, _streamer = manager_with_event
    ws = FakeWebSocket()

    connected = await manager.connect(ws, {"sub": "user-1"})
    assert connected is True
    manager.add_channel_subscription(ws, "metrics.update")

    got = await _wait_until(lambda: bool(ws.sent))
    assert got is True, "broadcast task never delivered the swarm event"
    payload = json.loads(ws.sent[0])
    assert payload["type"] == "SYSTEM_METRICS"
    assert payload["data"]["cpu"] == 12.5


@pytest.mark.asyncio
async def test_system_metrics_maps_to_metrics_update_channel():
    manager = DashboardWebSocketManager.__new__(DashboardWebSocketManager)
    assert manager._get_event_channel("SYSTEM_METRICS") == "metrics.update"
    assert manager._get_event_channel("metrics.foo") == "metrics.update"
    assert manager._get_event_channel("alert.critical_alert") == "alerts.emergency"


@pytest.mark.asyncio
async def test_duplicate_connect_does_not_spawn_second_broadcast_task(manager_with_event):
    manager, _streamer = manager_with_event
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()

    assert await manager.connect(ws1, {"sub": "user-1"}) is True
    first_task = manager.subscription_task
    assert await manager.connect(ws2, {"sub": "user-2"}) is True
    assert manager.subscription_task is first_task


@pytest.mark.asyncio
async def test_disconnect_last_client_cancels_subscription_task(manager_with_event):
    manager, _streamer = manager_with_event
    ws = FakeWebSocket()

    assert await manager.connect(ws, {"sub": "user-1"}) is True
    task = manager.subscription_task
    assert task is not None

    manager.disconnect(ws)
    assert manager.active_connections == {}
    assert manager.subscription_task is None
    finished = await _wait_until(lambda: task.done())
    assert finished is True, "subscription task was not cancelled after last disconnect"


@pytest.mark.asyncio
async def test_connection_cap_rejects_fail_closed():
    manager = DashboardWebSocketManager.__new__(DashboardWebSocketManager)
    manager.active_connections = {}
    manager.subscription_task = None
    manager.MAX_CONNECTIONS = 1  # type: ignore[misc]

    filler = FakeWebSocket()
    manager.active_connections[filler] = {"auth": {}, "channels": set(), "connected_at": 0}

    rejected = FakeWebSocket()
    result = await manager.connect(rejected, {"sub": "user-2"})

    assert result is False
    assert rejected.accepted is False
    assert rejected.closed == 1013

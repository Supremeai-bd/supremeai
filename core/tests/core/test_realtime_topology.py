"""#1832 — realtime transport topology contract tests.

বাংলা: ভয়েসে একটাই transport (WS — ফ্রন্টএন্ড সক্রিয়), orphan SSE নেই;
websocket_agent zombie (unmounted manager) কোথাও broadcast/metric/shutdown
করে না; task-completion নোটিফিকেশন লাইভ dashboard_events pubsub-এ যায়।
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"


class TestVoiceTransport:
    def test_orphan_sse_file_deleted(self):
        assert not (BACKEND / "api" / "routes" / "stream_voice_sse.py").exists(), (
            "stream_voice_sse had zero consumers — orphan must stay deleted"
        )

    def test_routers_no_longer_register_voice_sse(self):
        routers = (BACKEND / "api" / "routers.py").read_text(encoding="utf-8")
        active = [
            line
            for line in routers.splitlines()
            if "stream_voice_sse" in line and not line.strip().startswith("#")
        ]
        assert active == [], "stream_voice_sse must not be registered"

    def test_live_ws_voice_still_mounted(self):
        routers = (BACKEND / "api" / "routers.py").read_text(encoding="utf-8")
        ws_registered = any(
            '"path": "api.routes.websocket_voice"' in line and not line.strip().startswith("#")
            for line in routers.splitlines()
        )
        assert ws_registered, "websocket_voice (live transport) must stay mounted"


class TestZombieAgentManager:
    def test_websocket_agent_module_deleted(self):
        assert not (BACKEND / "api" / "routes" / "websocket_agent.py").exists()

    def test_no_runtime_references_remain(self):
        offenders: list[str] = []
        scan_roots = [BACKEND / "core", BACKEND / "api" / "routes"]
        for root in scan_roots:
            for py in root.rglob("*.py"):
                for line in py.read_text(encoding="utf-8").splitlines():
                    if "websocket_agent" in line and not line.strip().startswith("#"):
                        offenders.append(f"{py.name}: {line.strip()[:60]}")
        assert offenders == [], f"zombie references remain: {offenders}"

    def test_commandcenter_reports_no_fake_ws_metric(self):
        cc = (BACKEND / "api" / "routes" / "commandcenter" / "__init__.py").read_text(
            encoding="utf-8"
        )
        assert "active_connections" not in cc, "structurally-always-zero metric must stay removed"


class TestTaskCompletionNotifications:
    @pytest.mark.asyncio
    async def test_completion_publishes_to_live_dashboard_channel(self, monkeypatch):
        """The task-queue completion path publishes into the LIVE pubsub channel."""
        import core.queue.task_queue as tq
        from core.messaging.pubsub import global_pubsub

        published: list[Any] = []

        async def fake_publish(channel: str, message: dict):
            published.append((channel, message))

        monkeypatch.setattr(global_pubsub, "publish", fake_publish)

        captured: dict[str, Any] = {}

        class FakeRedis:
            async def set(self, key: str, value: str, ex: int | None = None):
                captured[key] = value

        queue = tq.RedisTaskQueue() if hasattr(tq, "RedisTaskQueue") else None
        assert queue is not None, "RedisTaskQueue class expected in task_queue.py"
        monkeypatch.setattr(queue, "redis", FakeRedis(), raising=False)

        async def handler(task_data: dict) -> dict:
            return {"ok": True}

        queue._handlers["unit"] = handler
        await queue._process_task(
            {"task_id": "t-1", "type": "unit", "task_type": "unit", "user_id": "u-1", "payload": {}}
        )

        assert published, "completion must publish to dashboard_events"
        channel, message = published[0]
        assert channel == "dashboard_events"
        assert message["type"] == "task_completed"
        assert message["task_id"] == "t-1"
        assert "task:t-1" in captured and json.loads(captured["task:t-1"])["status"] == "completed"

    def test_task_queue_sources_publish_to_pubsub_not_ws(self):
        text = (BACKEND / "core" / "queue" / "task_queue.py").read_text(encoding="utf-8")
        assert "websocket_agent" not in text
        assert "dashboard_events" in text
        assert "global_pubsub" in text

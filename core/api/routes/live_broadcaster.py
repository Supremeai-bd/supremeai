"""Swappable WebSocket Live Broadcaster for SupremeAI.

বাংলা: সোয়াপযোগ্য ওয়েবসকেট লাইভ ব্রডকাস্টার।
ইন-মেমোরি এবং Redis Pub/Sub অ্যাডাপ্টারের মাধ্যমে রিয়েল-টাইমে কাস্টমার আপডেট,
MCP টাওয়ার সার্ভিসেস এবং সিস্টেম ইভেন্ট ব্রডকাস্ট করে।
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.logging_config import logger

router = APIRouter(tags=["Live Broadcaster"])


class SwappableBroadcaster:
    """Manages WebSocket connections and dispatches events via In-Memory or Redis."""

    def __init__(self, max_connections: int = 100):
        self.max_connections = max_connections
        self.active_connections: set[WebSocket] = set()
        self._redis_client: Any = None
        self._is_redis_enabled = False

    async def init_redis_adapter(self, redis_url: str | None = None) -> bool:
        """Initialize optional Redis pub/sub transport for multi-replica broadcast."""
        url = redis_url or os.getenv("REDIS_URL")
        if not url:
            return False
        try:
            import redis.asyncio as aioredis

            self._redis_client = aioredis.from_url(url, decode_responses=True)
            await self._redis_client.ping()
            self._is_redis_enabled = True
            logger.info("📡 [Broadcaster] Swapped to Redis Pub/Sub adapter")
            return True
        except Exception as exc:
            logger.warning("📡 [Broadcaster] Redis unavailable, using local memory bus: %s", exc)
            self._is_redis_enabled = False
            return False

    async def connect(self, websocket: WebSocket) -> bool:
        """Accept new WebSocket connection with capacity checking."""
        if len(self.active_connections) >= self.max_connections:
            await websocket.close(code=1013, reason="Connection limit reached")
            return False

        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(
            "📡 [Broadcaster] Client connected. Active: %d/%d",
            len(self.active_connections),
            self.max_connections,
        )
        return True

    def disconnect(self, websocket: WebSocket) -> None:
        """Unregister a disconnected client."""
        self.active_connections.discard(websocket)
        logger.info(
            "📡 [Broadcaster] Client disconnected. Remaining: %d",
            len(self.active_connections),
        )

    async def broadcast(self, message_type: str, payload: dict[str, Any]) -> None:
        """Broadcast message to all connected clients."""
        envelope = {
            "type": message_type,
            "data": payload,
            "timestamp": asyncio.get_event_loop().time(),
        }
        # Backward compatibility for direct type matching in client
        if message_type == "customer_updated":
            envelope["customer"] = payload
        elif message_type == "mcp_service_updated":
            envelope["service"] = payload

        raw_json = json.dumps(envelope)

        # 1. Local connected clients broadcast
        stale: list[WebSocket] = []
        for ws in list(self.active_connections):
            try:
                await ws.send_text(raw_json)
            except Exception:
                stale.append(ws)

        for s in stale:
            self.disconnect(s)

        # 2. Redis broadcast if multi-worker swarm mode is active
        if self._is_redis_enabled and self._redis_client:
            try:
                await self._redis_client.publish("supremeai:live_broadcast", raw_json)
            except Exception as e:
                logger.warning("Broadcaster Redis publish failed: %s", e)

    async def broadcast_customer_updated(self, customer: dict[str, Any]) -> None:
        """Convenience method for customer mutation broadcast."""
        await self.broadcast("customer_updated", customer)

    async def broadcast_mcp_service_updated(self, service: dict[str, Any]) -> None:
        """Convenience method for MCP telemetry changes."""
        await self.broadcast("mcp_service_updated", service)

    async def broadcast_sync_complete(self, summary: dict[str, Any]) -> None:
        """Broadcast sync completion notification."""
        await self.broadcast("sync_complete", summary)


# Global singleton broadcaster instance
broadcaster = SwappableBroadcaster()


async def _handle_ws_lifecycle(websocket: WebSocket) -> None:
    connected = await broadcaster.connect(websocket)
    if not connected:
        return

    # Send initial connection acknowledgment
    try:
        await websocket.send_text(
            json.dumps({"type": "connection_ack", "status": "connected", "mode": "swappable_broadcaster"})
        )
    except Exception:
        broadcaster.disconnect(websocket)
        return

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                msg_type = msg.get("type") or msg.get("command")
                if msg_type == "ping":
                    await websocket.send_text(
                        json.dumps({"type": "pong", "timestamp": asyncio.get_event_loop().time()})
                    )
                elif msg_type == "sync_request":
                    await broadcaster.broadcast_sync_complete({"status": "acknowledged"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)
    except Exception as exc:
        logger.warning("Broadcaster WebSocket terminated: %s", exc)
        broadcaster.disconnect(websocket)


@router.websocket("/ws/live")
async def ws_live_endpoint(websocket: WebSocket) -> None:
    """Dedicated live broadcast endpoint for frontend websocketService."""
    await _handle_ws_lifecycle(websocket)


@router.websocket("/ws")
async def ws_root_endpoint(websocket: WebSocket) -> None:
    """Fallback alias /ws for standard websocket connections."""
    await _handle_ws_lifecycle(websocket)


@router.websocket("/api/ws")
async def ws_api_endpoint(websocket: WebSocket) -> None:
    """API-prefixed alias /api/ws."""
    await _handle_ws_lifecycle(websocket)

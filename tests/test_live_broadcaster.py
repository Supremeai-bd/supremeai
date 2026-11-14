"""Tests for Swappable WebSocket Live Broadcaster."""

import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.live_broadcaster import broadcaster, router as broadcaster_router


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(broadcaster_router)
    return application


def test_websocket_connection_ack_and_ping(app):
    """Test connecting to /ws/live, receiving connection_ack and ping/pong."""
    client = TestClient(app)
    with client.websocket_connect("/ws/live") as websocket:
        # 1. Verify connection acknowledgment
        ack_text = websocket.receive_text()
        ack = json.loads(ack_text)
        assert ack["type"] == "connection_ack"
        assert ack["status"] == "connected"

        # 2. Send ping and verify pong
        websocket.send_text(json.dumps({"type": "ping"}))
        pong_text = websocket.receive_text()
        pong = json.loads(pong_text)
        assert pong["type"] == "pong"
        assert "timestamp" in pong


@pytest.mark.asyncio
async def test_broadcaster_event_dispatch(app):
    """Test that broadcaster dispatches customer_updated and mcp_service_updated."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        # Receive ack
        websocket.receive_text()

        # Broadcast customer event
        sample_cust = {"id": "cust_live_01", "name": "Live Broadcaster User", "status": "active"}
        await broadcaster.broadcast_customer_updated(sample_cust)

        event_text = websocket.receive_text()
        event = json.loads(event_text)
        assert event["type"] == "customer_updated"
        assert event["customer"]["id"] == "cust_live_01"
        assert event["customer"]["name"] == "Live Broadcaster User"

        # Broadcast MCP service update
        sample_svc = {"id": "render-primary", "status": "healthy"}
        await broadcaster.broadcast_mcp_service_updated(sample_svc)

        svc_text = websocket.receive_text()
        svc_event = json.loads(svc_text)
        assert svc_event["type"] == "mcp_service_updated"
        assert svc_event["service"]["id"] == "render-primary"

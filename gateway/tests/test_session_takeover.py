"""গ্যাপ ফিক্স রিগ্রেশন টেস্ট: production-এ fake screencast frame আর পাঠানো হবে না,
এবং একই takeover token দ্বিতীয়বার ব্যবহার করা যাবে না (replay protection)।"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.routes import session_takeover


@pytest.mark.asyncio
async def test_verify_takeover_token_rejects_unknown_token():
    assert await session_takeover.verify_takeover_token("tok_not_in_allowlist") is False


@pytest.mark.asyncio
async def test_verify_takeover_token_rejects_replay_when_redis_available(monkeypatch):
    monkeypatch.setenv("ALLOWED_TAKEOVER_TOKENS", "tok_abc123")
    fake_redis = AsyncMock()
    # প্রথমবার consume সফল (True), দ্বিতীয়বার token আগেই ব্যবহৃত (None/False)
    fake_redis.set.side_effect = [True, None]

    with patch.object(session_takeover, "_redis_client", AsyncMock(return_value=fake_redis)):
        first = await session_takeover.verify_takeover_token("tok_abc123")
        second = await session_takeover.verify_takeover_token("tok_abc123")

    assert first is True
    assert second is False


def test_is_production_flag(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_ENV", "production")
    assert session_takeover._is_production() is True
    monkeypatch.setenv("SUPREMEAI_ENV", "development")
    assert session_takeover._is_production() is False
    os.environ.pop("SUPREMEAI_ENV", None)
    assert session_takeover._is_production() is False


# ── #2253 regression: page resolution via the canonical session manager ─────
# পুরনো কোড PlaywrightBrowserAgent.get_or_create_session() ডাকত — যে method
# ওই class-এ কখনোই ছিল না; প্রতিটা takeover auth-এর ঠিক পরেই AttributeError-এ
# মারা যেত। এই টেস্টগুলো নতুন canonical wiring প্রমাণ করে।


@pytest.mark.asyncio
async def test_get_for_admin_resolves_session_without_owner_check():
    """get_for_admin bypasses the owner check — HITL admin is not the owner."""
    from core.browser_session_manager import BrowserSession, BrowserSessionManager

    mgr = BrowserSessionManager(max_sessions=2, idle_timeout_seconds=60)
    fake_session = BrowserSession(
        id="bs_test",
        owner_id="agent-owner",
        context=object(),
        page=object(),
        created_at=0.0,
        last_used_at=0.0,
    )
    mgr._sessions["bs_test"] = fake_session

    resolved = await mgr.get_for_admin("bs_test")
    assert resolved is fake_session
    # last_used_at refreshed so the idle-reaper cannot kill a live takeover
    assert resolved.last_used_at > 0.0


@pytest.mark.asyncio
async def test_get_for_admin_missing_session_raises_keyerror():
    from core.browser_session_manager import BrowserSessionManager

    mgr = BrowserSessionManager(max_sessions=2, idle_timeout_seconds=60)
    with pytest.raises(KeyError):
        await mgr.get_for_admin("bs_missing")


def test_takeover_websocket_resolves_page_via_canonical_manager(monkeypatch):
    """End-to-end WS regression: auth → canonical page resolution → input ack.

    Pre-fix behavior: AttributeError at agent.get_or_create_session() right
    after auth — the socket dies and no input_ack ever arrives. This test
    fails on the old code and passes on the fixed wiring.
    """
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ALLOWED_TAKEOVER_TOKENS", "tok_ws_regression")
    monkeypatch.setattr(session_takeover, "_redis_client", AsyncMock(return_value=None))

    fake_page = MagicMock()
    fake_session = SimpleNamespace(page=fake_page)
    monkeypatch.setattr(
        "core.browser_session_manager.session_manager",
        SimpleNamespace(get_for_admin=AsyncMock(return_value=fake_session)),
    )
    # ScreencastStreamer CDP internals are out of scope: stub the stream loop.
    monkeypatch.setattr(session_takeover.ScreencastStreamer, "start_stream", AsyncMock())
    monkeypatch.setattr(session_takeover.ScreencastStreamer, "stop_stream", AsyncMock())
    monkeypatch.setattr(
        session_takeover.ScreencastStreamer,
        "handle_input",
        AsyncMock(return_value={"status": "ok"}),
    )

    app = FastAPI()
    app.include_router(session_takeover.router)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/session/bs_live/takeover") as ws:
            ws.send_json({"type": "auth", "token": "tok_ws_regression"})
            ws.send_json({"action": "click", "data": {"selector": "#btn"}})
            ack = ws.receive_json()
            assert ack["channel"] == "input_ack"
            assert ack["action"] == "click"
            assert ack["result"]["status"] == "ok"

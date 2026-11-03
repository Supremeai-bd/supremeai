"""Tests for AntiHackingContextMiddleware — sliding-window Caution tier and OTP cooldown.

বাংলা: নতুন Caution tier (partial IP/UA match) এবং OTP cooldown throttle-এর জন্য টেস্ট।
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from middleware.anti_hacking import AntiHackingContextMiddleware


def _make_request(ip: str, country: str, ua: str, fingerprint: str, admin_id: str = "admin-1"):
    req = SimpleNamespace()
    req.headers = {
        "x-forwarded-for": ip,
        "cf-ipcountry": country,
        "user-agent": ua,
        "x-device-fingerprint": fingerprint,
    }
    req.state = SimpleNamespace(user={"sub": admin_id})
    # বাংলা মন্তব্য: utils/client_ip.get_client_ip() production Request.client.host
    # আশা করে (proxy-aware IP extraction); সরাসরি এক্সপোজারে trusted_proxy_count=0
    # হওয়ায় raw_host-ই ফেরত আসে, তাই এখানে .client-কে সরাসরি ইনপুট `ip`-এ সেট করা হচ্ছে।
    req.client = SimpleNamespace(host=ip)
    return req


async def _call_next(request):
    return "OK"


@pytest.fixture
def mock_redis():
    """Async mock standing in for redis_manager with a real-ish get/set-nx behaviour."""
    store: dict[str, str] = {}
    nx_locks: set[str] = set()

    manager = AsyncMock()

    async def get_cache(key):
        return store.get(key)

    async def set_cache(key, value, ex_seconds=3600):
        store[key] = value
        return True

    manager.get_cache = AsyncMock(side_effect=get_cache)
    manager.set_cache = AsyncMock(side_effect=set_cache)

    client = AsyncMock()

    async def set_nx(key, value, nx=False, ex=None):
        if nx and key in nx_locks:
            return None
        nx_locks.add(key)
        return True

    client.set = AsyncMock(side_effect=set_nx)
    client.lpush = AsyncMock(return_value=1)
    client.ltrim = AsyncMock(return_value=True)
    client.expire = AsyncMock(return_value=True)
    manager.client = client
    manager._store = store
    manager._nx_locks = nx_locks
    return manager


@pytest.mark.asyncio
async def test_first_request_no_prior_context_passes_through(mock_redis):
    with (
        patch("middleware.anti_hacking.redis_manager", mock_redis),
        patch("middleware.anti_hacking.send_otp", new=AsyncMock()) as mock_send,
    ):
        mw = AntiHackingContextMiddleware(app=None)
        req = _make_request("1.2.3.4", "BD", "chrome", "fp-abc")
        result = await mw.dispatch(req, _call_next)
        assert result == "OK"
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_full_mismatch_triggers_otp(mock_redis):
    with (
        patch("middleware.anti_hacking.redis_manager", mock_redis),
        patch("middleware.anti_hacking.send_otp", new=AsyncMock()) as mock_send,
    ):
        mw = AntiHackingContextMiddleware(app=None)

        # Establish trusted context first
        req1 = _make_request("1.2.3.4", "BD", "chrome-v1", "fp-abc")
        await mw.dispatch(req1, _call_next)

        # Completely different IP subnet, country, UA and fingerprint -> full OTP challenge
        req2 = _make_request("9.9.9.9", "US", "safari-v9", "fp-zzz")
        await mw.dispatch(req2, _call_next)

        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_partial_match_same_subnet_is_caution_not_otp(mock_redis):
    with (
        patch("middleware.anti_hacking.redis_manager", mock_redis),
        patch("middleware.anti_hacking.send_otp", new=AsyncMock()) as mock_send,
    ):
        mw = AntiHackingContextMiddleware(app=None)

        req1 = _make_request("1.2.3.4", "BD", "chrome-v1", "fp-abc")
        await mw.dispatch(req1, _call_next)

        # Same /24 subnet (first 3 octets), different last octet + different fingerprint (CGNAT-style)
        req2 = _make_request("1.2.3.99", "US", "different-ua", "fp-zzz")
        await mw.dispatch(req2, _call_next)

        mock_send.assert_not_called()
        mock_redis.client.lpush.assert_called_once()


@pytest.mark.asyncio
async def test_partial_match_same_user_agent_is_caution_not_otp(mock_redis):
    with (
        patch("middleware.anti_hacking.redis_manager", mock_redis),
        patch("middleware.anti_hacking.send_otp", new=AsyncMock()) as mock_send,
    ):
        mw = AntiHackingContextMiddleware(app=None)

        req1 = _make_request("1.2.3.4", "BD", "chrome-v1", "fp-abc")
        await mw.dispatch(req1, _call_next)

        # Different subnet entirely, but identical UA (mobile data switch scenario)
        req2 = _make_request("77.88.99.10", "US", "chrome-v1", "fp-zzz")
        await mw.dispatch(req2, _call_next)

        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_otp_cooldown_suppresses_duplicate_sends(mock_redis):
    with (
        patch("middleware.anti_hacking.redis_manager", mock_redis),
        patch("middleware.anti_hacking.send_otp", new=AsyncMock()) as mock_send,
    ):
        mw = AntiHackingContextMiddleware(app=None)

        req1 = _make_request("1.2.3.4", "BD", "chrome-v1", "fp-abc")
        await mw.dispatch(req1, _call_next)

        # First full mismatch -> OTP sent, cooldown lock acquired
        req2 = _make_request("9.9.9.9", "US", "safari-v9", "fp-zzz")
        await mw.dispatch(req2, _call_next)
        assert mock_send.call_count == 1

        # Immediate second full mismatch from a third distinct context -> cooldown should suppress resend
        req3 = _make_request("5.5.5.5", "FR", "firefox-v1", "fp-yyy")
        await mw.dispatch(req3, _call_next)
        assert mock_send.call_count == 1  # unchanged — cooldown suppressed the second send

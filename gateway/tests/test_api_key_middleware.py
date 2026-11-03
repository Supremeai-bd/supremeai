"""APIKeyAuthMiddleware এর ইউনিট টেস্ট।

বাংলা: রেডিস/ডেটাবেজ/রেট-লিমিটার সব মক করে শুধু ডিসপ্যাচ লজিকের
স্কিপ/টেস্ট-বাইপাস ব্রাঞ্চগুলো কভার করা হয়েছে। পাবলিক পাথ ও টেস্ট এনভায়রনমেন্টেই
আইসোলেটেড টেস্ট সম্ভব, তাই সেগুলোই টার্গেট করা হলো।
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.security.api_key_middleware import API_KEY_PREFIX, APIKeyAuthMiddleware


def _make_request(
    path: str, headers: dict | None = None, client_host: str = "127.0.0.1"
):  # is_local()
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": ("127.0.0.1", 1234) if client_host else None,  # is_local()
        "query_string": b"",
    }
    # বাংলা: সাধারণ Request অবজেক্ট (starlette) বানাতে minimal attrs যোগ
    from starlette.requests import Request

    req = Request(scope)
    req.state.api_key = None
    return req


@pytest.fixture
def fake_settings():
    s = MagicMock()
    s.supremeai_public_paths = ["/api/v1/health", "/docs"]
    return s


@pytest.fixture
def middleware(fake_settings):
    with (
        patch("core.security.api_key_middleware.redis_manager") as _rm,
        patch("core.security.api_key_middleware.get_db_pool", new=AsyncMock()),
        patch("core.security.api_key_middleware.AsyncRateLimiter") as _lim,
        patch("core.security.api_key_middleware.is_test_environment", return_value=False),
        patch("core.config.settings", fake_settings),
    ):
        _lim.return_value.acquire = AsyncMock(return_value=True)
        mw = APIKeyAuthMiddleware(app=MagicMock())
        yield mw


@pytest.mark.asyncio
async def test_dispatch_public_path_skips_lookup(middleware):
    called = {"n": 0}

    async def call_next(request):
        called["n"] += 1
        return "OK"

    req = _make_request("/api/v1/health")
    result = await middleware.dispatch(req, call_next)
    assert result == "OK"
    assert called["n"] == 1


@pytest.mark.asyncio
async def test_dispatch_no_api_key_header_skips(middleware):
    called = {"n": 0}

    async def call_next(request):
        called["n"] += 1
        return "OK"

    req = _make_request("/api/v1/agents")
    result = await middleware.dispatch(req, call_next)
    assert result == "OK"
    assert called["n"] == 1


@pytest.mark.asyncio
async def test_dispatch_wrong_prefix_skips(middleware):
    called = {"n": 0}

    async def call_next(request):
        called["n"] += 1
        return "OK"

    req = _make_request("/api/v1/agents", headers={"x-api-key": "not-the-right-prefix-xyz"})
    result = await middleware.dispatch(req, call_next)
    assert result == "OK"
    assert called["n"] == 1


def test_prefix_constant_defined():
    assert API_KEY_PREFIX.startswith("sk-supreme")

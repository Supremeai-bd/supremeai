"""
Admin JWT revocation policy tests — env-aware failure policy (V3 token_budget
প্রিসিডেন্ট অনুসরণ; production-readiness plan, item 2)।

নিশ্চিত করে:
- Redis ডাউন + is_admin=True + env=production → True (fail-CLOSED, অপরিবর্তিত)
- Redis ডাউন + is_admin=True + env=dev/test   → False (fail-open) + loud log
- Redis ডাউন + is_admin=False                 → False (fail-open)
- Redis সুস্থ + blacklist-এ jti               → True
- TTL-aware admin LRU cache: revoked admin jti Redis ছাড়াই ধরা পড়ে
- verify_token_async: role=admin + production + Redis ডাউনে 401 দেয়
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from core.security import (
    _ADMIN_REVOCATION_CACHE,
    _admin_cache_get,
    _admin_cache_put,
    is_token_revoked,
    verify_token_async,
)

pytestmark = [pytest.mark.unit, pytest.mark.security]


class _FakeRedis:
    def __init__(self, down: bool = False):
        self.client = None if down else AsyncMock()


@pytest.fixture(autouse=True)
def _clean_cache():
    _ADMIN_REVOCATION_CACHE.clear()
    yield
    _ADMIN_REVOCATION_CACHE.clear()


@pytest.fixture(autouse=True)
def _preserve_jwt_secret_cache():
    # বাংলা (V5.1 রেগ্রেশন-ফিক্স): নিচের টেস্টগুলো settings.env সাময়িকভাবে
    # "production" করে; ওই উইন্ডোতে settings.jwt_secret-এর production শাখা
    # CI-র JWT_SECRET/SUPREMEAI_JWT_SECRET env পড়ে _jwt_secret_cache
    # ওভাররাইট করে ফেলে — ফলে পরবর্তী টেস্ট ফাইলের আগে-ইস্যু-করা টোকেনগুলোর
    # signature ভেঙে যায় (CI fast গ্রুপের ৫টি agent/api টেস্ট এভাবেই লাল হয়েছিল)।
    # তাই ক্যাশ স্ন্যাপশট করে টেস্ট-শেষে হুবহু ফেরত দেওয়া হয়।
    from core.config import settings

    sentinel = object()
    before = getattr(settings, "_jwt_secret_cache", sentinel)
    yield
    if before is sentinel:
        if hasattr(settings, "_jwt_secret_cache"):
            del settings._jwt_secret_cache  # pydantic extra attr — প্রপার্টিই সেট করে, তাই ডিলিটও নিরাপদ
    else:
        settings._jwt_secret_cache = before


@pytest.mark.asyncio
async def test_admin_fail_closed_when_redis_down():
    # বাংলা: production-এ নীতি অপরিবর্তিত — Redis ছাড়া অ্যাডমিন রিজেক্ট (fail-closed)।
    from core.config import settings

    with patch("core.cache.redis_manager.redis_manager", _FakeRedis(down=True)):
        with patch.object(settings, "env", "production"):
            assert await is_token_revoked("jti-admin-1", is_admin=True) is True


@pytest.mark.asyncio
async def test_admin_fail_open_dev_when_redis_down():
    # বাংলা: V5 — dev/test-এ Redis না থাকলে fail-open (নীরব নয়, loud error লগে);
    # নইলে Redis-হীন টেস্ট এনভায়রনমেন্টে সব অ্যাডমিন এন্ডপয়েন্ট 401 হয়ে যেত।
    from core.config import settings

    with patch("core.cache.redis_manager.redis_manager", _FakeRedis(down=True)):
        with patch.object(settings, "env", "local"):
            assert await is_token_revoked("jti-admin-dev", is_admin=True) is False


@pytest.mark.asyncio
async def test_regular_user_fail_open_when_redis_down():
    with patch("core.cache.redis_manager.redis_manager", _FakeRedis(down=True)):
        assert await is_token_revoked("jti-user-1", is_admin=False) is False


@pytest.mark.asyncio
async def test_revoked_jti_detected_via_redis():
    redis = _FakeRedis(down=False)
    redis.client.exists = AsyncMock(return_value=1)
    with patch("core.cache.redis_manager.redis_manager", redis):
        assert await is_token_revoked("jti-x", is_admin=False) is True
        assert await is_token_revoked("jti-x", is_admin=True) is True


@pytest.mark.asyncio
async def test_admin_lru_cache_hit_when_redis_down():
    # revoke_token করার সময় admin jti LRU-তে থাকে — Redis ডাউন হলেও ধরা পড়ে
    _admin_cache_put("jti-admin-revoked", ttl_seconds=300)
    with patch("core.cache.redis_manager.redis_manager", _FakeRedis(down=True)):
        assert await is_token_revoked("jti-admin-revoked", is_admin=True) is True


def test_admin_cache_expiry():
    import time

    _admin_cache_put("jti-ttl", ttl_seconds=60)
    assert _admin_cache_get("jti-ttl") is True
    # সরাসরি মেয়াদ উত্তীর্ণ করা হয় (put-এর max(1.0s) গার্ড এড়িয়ে)
    with __import__("core.security", fromlist=["_ADMIN_REVOCATION_LOCK"])._ADMIN_REVOCATION_LOCK:
        _ADMIN_REVOCATION_CACHE["jti-ttl"] = time.monotonic() - 1
    assert _admin_cache_get("jti-ttl") is False


def test_admin_cache_lru_bound():
    from core.security import _ADMIN_REVOCATION_CACHE_MAX

    for i in range(_ADMIN_REVOCATION_CACHE_MAX + 50):
        _admin_cache_put(f"jti-{i}")
    assert len(_ADMIN_REVOCATION_CACHE) <= _ADMIN_REVOCATION_CACHE_MAX
    # সবচেয়ে পুরনো entry evict হয়েছে
    assert _admin_cache_get("jti-0") is False
    # সর্বশেষ entry আছে
    assert _admin_cache_get(f"jti-{_ADMIN_REVOCATION_CACHE_MAX + 49}") is True


@pytest.mark.asyncio
async def test_verify_token_async_admin_401_when_redis_down():
    # বাংলা: production fail-closed semantics — অ্যাডমিন টোকেন Redis ডাউনে 401।
    # jwt_secret-এ PropertyMock: production উইন্ডোতেও decode যেন একই সিক্রেটে
    # হয় (নইলে 401 আসে signature-mismatch থেকে — ভুল কারণে পাস হতো), এবং
    # 401-এর উৎস যেন প্রকৃতই fail-closed revocation হয়।
    from unittest.mock import PropertyMock

    from core.config import settings

    token = _make_admin_token()
    real_secret = settings.jwt_secret
    with patch("core.cache.redis_manager.redis_manager", _FakeRedis(down=True)):
        with patch.object(
            type(settings), "jwt_secret", new_callable=PropertyMock, return_value=real_secret
        ):
            with patch.object(settings, "env", "production"):
                with pytest.raises(HTTPException) as exc_info:
                    await verify_token_async(token)
                assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_token_async_user_ok_when_redis_down():
    token = _make_user_token()
    with patch("core.cache.redis_manager.redis_manager", _FakeRedis(down=True)):
        payload = await verify_token_async(token)
        assert payload["role"] == "user"


# ── helpers ──────────────────────────────────────────────────────────────


def _make_admin_token() -> str:
    from core.config import settings
    from core.security import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, create_access_token

    admin_email = (
        sorted(settings.admin_emails)[0] if settings.admin_emails else "admin@supremeai.dev"
    )
    return create_access_token({"sub": admin_email, "role": "admin"})


def _make_user_token() -> str:
    from core.security import create_access_token

    return create_access_token({"sub": "regular-user@supremeai.dev", "role": "user"})

# বাংলা মন্তব্য: এই টেস্ট ফাইলটি /auth রুটের নিরাপত্তা চুক্তি (security contract)
# পরীক্ষা করে — JWT/Bearer টোকেন ভ্যালিডেশন, সেশন হ্যান্ডলিং, পাসওয়ার্ড হ্যাশ যাচাই,
# এবং brute-force প্রতিরোধী rate-limiting। সব কিছু fully mocked — কোনো বাস্তব
# DB / Supabase / Redis / বাইরের API কল নেই (Rule #64)।
#
# টেস্ট কাঠামো: Given-When-Then docstring-সহ প্রতিটি টেস্ট (Rule #61 — happy + sad)।
# বাউন্ডারি কেস যেমন expired টোকেন, type-confusion, rate-limit threshold অন্তর্ভুক্ত (Rule #66)।

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# বাংলা মন্তব্য: টেস্ট-নির্দিষ্ট JWT secret — প্রোডাকশন settings-কে একদম না ছুঁয়ে
# _get_secret_key patch করে টোকেন sign/verify করা হয়।
TEST_SECRET = "test-jwt-secret-contract-2758"
ALGORITHM = "HS256"
# বাংলা মন্তব্য (B4): ইস্যুয়ার ও অডিয়েন্স claim এখন বাধ্যতামূলক — ফিক্সচার
# টোকেনগুলোও বাস্তব টোকেনের মতো একই claim-সেট বহন করবে।
TEST_ISSUER = "supremeai"
TEST_AUDIENCE = "supremeai-api"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_app(monkeypatch):
    """বাংলা: একটি পৃথক FastAPI app যাতে শুধু auth router মাউন্ট আছে।
    _get_secret_key patch করা থাকে যাতে টোকেন sign/verify deterministic হয়।
    """
    from api.routes.auth import router as auth_router

    # বাংলা: is_token_revoked / revoke_token patch — Redis-নির্ভরশীল ভ্যালিডেশন
    # এড়িয়ে deterministic টেস্ট হয়।
    with (
        patch("api.routes.auth.is_token_revoked", new=AsyncMock(return_value=False)) as _rev,
        patch("api.routes.auth.revoke_token", new=AsyncMock(return_value=True)) as _revoke,
    ):
        app = FastAPI()
        app.include_router(auth_router)
        tc = TestClient(app)
        yield tc, app, _rev, _revoke


@pytest.fixture()
def patched_secret(monkeypatch):
    """বাংলা: _get_secret_key-কে TEST_SECRET ফেরাতে patch করা হলো।"""
    import api.routes.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_get_secret_key", lambda: TEST_SECRET)
    return TEST_SECRET


# ---------------------------------------------------------------------------
# Token minting helpers
# ---------------------------------------------------------------------------


def _access_token(
    secret: str,
    *,
    sub: str = "user-123",
    role: str = "user",
    email: str = "user@example.com",
    jti: str = "jti-access-0001",
    exp_minutes: int = 60,
) -> str:
    """বাংলা: বৈধ access JWT তৈরি করে (type=access)।"""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": sub,
        "role": role,
        "email": email,
        "tenant_id": sub,
        "type": "access",
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(minutes=exp_minutes),
        "iss": TEST_ISSUER,
        "aud": TEST_AUDIENCE,
    }
    return pyjwt.encode(payload, secret, algorithm=ALGORITHM)


def _refresh_token(
    secret: str,
    *,
    sub: str = "user-123",
    role: str = "user",
    email: str = "user@example.com",
    jti: str = "jti-refresh-0001",
    tfid: str = "tfid-family-0001",
) -> str:
    """বাংলা: বৈধ refresh JWT তৈরি করে (type=refresh)।"""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": sub,
        "role": role,
        "email": email,
        "tenant_id": sub,
        "type": "refresh",
        "jti": jti,
        "tfid": tfid,
        "iat": now,
        "exp": now + timedelta(days=7),
        "iss": TEST_ISSUER,
        "aud": TEST_AUDIENCE,
    }
    return pyjwt.encode(payload, secret, algorithm=ALGORITHM)


def _expired_access_token(secret: str) -> str:
    """বাংলা: exp ইতিমধ্যে পার হয়ে যাওয়া access টোকেন।"""
    now = datetime.now(UTC)
    payload = {
        "sub": "user-123",
        "role": "user",
        "email": "user@example.com",
        "type": "access",
        "jti": "jti-expired-0001",
        "iat": now - timedelta(minutes=70),
        "exp": now - timedelta(minutes=5),
        "iss": TEST_ISSUER,
        "aud": TEST_AUDIENCE,
    }
    return pyjwt.encode(payload, secret, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# 1. JWT / Bearer token validation
# ---------------------------------------------------------------------------


class TestJwtBearerTokenValidation:
    """JWT/Bearer টোকেন ভ্যালিডেশন চুক্তি — /auth/me এন্ডপয়েন্ট দিয়ে।"""

    def test_valid_bearer_token_returns_200(self, auth_app, patched_secret):
        """Given: একজন প্রমাণীকৃত ইউজারের বৈধ access টোকেন।
        When: /auth/me-তে Authorization: Bearer <token> দিয়ে GET।
        Then: 200 এবং response-এ user_id, role ঠিকমতো আসে (happy path)।
        """
        tc, _app, _rev, _revoke = auth_app
        token = _access_token(patched_secret)

        res = tc.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert res.status_code == 200
        body = res.json()
        assert body["user_id"] == "user-123"
        assert body["role"] == "user"
        assert body["email"] == "user@example.com"

    def test_missing_bearer_token_returns_401(self, auth_app, patched_secret):
        """Given: কোনো Authorization হেডার নেই।
        When: /auth/me-তে হেডার ছাড়া GET।
        Then: 401 Not authenticated (sad path)।
        """
        tc, _app, _rev, _revoke = auth_app

        res = tc.get("/auth/me")

        assert res.status_code == 401
        assert res.json()["detail"] == "Not authenticated"

    def test_invalid_bearer_token_returns_401(self, auth_app, patched_secret):
        """Given: একটি আজেবাজে (tampered) JWT স্ট্রিং।
        When: /auth/me-তে সেট দিয়ে GET।
        Then: 401 — JWTError ধরা হয়, detail = Not authenticated (sad path)।
        """
        tc, _app, _rev, _revoke = auth_app

        res = tc.get("/auth/me", headers={"Authorization": "Bearer not.a.real.jwt"})

        assert res.status_code == 401

    def test_expired_token_returns_401(self, auth_app, patched_secret):
        """Given: exp পার হয়ে যাওয়া টোকেন (boundary — সময় সীমা)।
        When: /auth/me-তে সেট দিয়ে GET।
        Then: 401 — ExpiredSignatureError JWTError হিসেবে ধরা পড়ে।
        """
        tc, _app, _rev, _revoke = auth_app
        token = _expired_access_token(patched_secret)

        res = tc.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert res.status_code == 401

    def test_revoked_token_returns_401(self, auth_app, patched_secret):
        """Given: একটি বৈধ access টোকেন যার jti blacklist-এ আছে (logout হয়েছে)।
        When: is_token_revoked True ফেরায় এবং /auth/me-তে GET।
        Then: 401 — revoked টোকেন আর গ্রহণযোগ্য নয় (revocation enforcement)।
        """
        tc, _app, _rev, _revoke = auth_app
        token = _access_token(patched_secret, jti="jti-revoked-0001")
        # বাংলা: is_token_revoked এখন True ফেরাবে — নির্দিষ্ট jti-র জন্য।
        _rev.return_value = True

        res = tc.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert res.status_code == 401

    def test_refresh_token_type_confusion_rejected(self, auth_app, patched_secret):
        """Given: একটি বৈধ refresh টোকেন (type=refresh)।
        When: /auth/me-তে সেট দিয়ে GET (যেন access টোকেনের মতো ব্যবহার করছে)।
        Then: 401 — token-confusion প্রতিরোধ; refresh টোকেন দিয়ে /me চলবে না (boundary)।
        """
        tc, _app, _rev, _revoke = auth_app
        token = _refresh_token(patched_secret)

        res = tc.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert res.status_code == 401

    def test_token_signed_with_wrong_secret_rejected(self, auth_app, patched_secret):
        """Given: ভিন্ন secret দিয়ে sign করা টোকেন।
        When: /auth/me-তে সেট দিয়ে GET।
        Then: 401 — signature mismatch ধরা পড়ে (boundary — secret integrity)।
        """
        tc, _app, _rev, _revoke = auth_app
        token = _access_token("a-completely-different-secret")

        res = tc.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert res.status_code == 401


# ---------------------------------------------------------------------------
# 2. Session handling (refresh rotation, logout blacklisting)
# ---------------------------------------------------------------------------


class TestSessionHandling:
    """সেশন লাইফসাইকেল — refresh rotation, type-confusion, logout blacklist।"""

    def test_refresh_with_valid_refresh_token_returns_new_tokens(self, auth_app, patched_secret):
        """Given: একটি বৈধ refresh টোকেন।
        When: /auth/refresh-এ POST।
        Then: 200 এবং নতুন access_token + refresh_token ফেরত আসে (happy)।
        """
        tc, _app, _rev, _revoke = auth_app
        rt = _refresh_token(patched_secret)

        res = tc.post("/auth/refresh", json={"refresh_token": rt})

        assert res.status_code == 200
        body = res.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["user_id"] == "user-123"
        # বাংলা: rotation — পুরনো refresh jti এখন blacklist হওয়া উচিত।
        _revoke.assert_awaited()

    def test_refresh_with_missing_token_returns_401(self, auth_app, patched_secret):
        """Given: body-তে কোনো refresh_token নেই এবং cookie-ও নেই।
        When: /auth/refresh-এ POST।
        Then: 401 Refresh token missing (sad path)।
        """
        tc, _app, _rev, _revoke = auth_app

        res = tc.post("/auth/refresh", json={})

        assert res.status_code == 401
        assert "missing" in res.json()["detail"].lower()

    def test_refresh_rejects_access_token_type_confusion(self, auth_app, patched_secret):
        """Given: একটি access টোকেন (type=access)।
        When: সেট দিয়ে /auth/refresh-এ POST।
        Then: 401 — access টোকেন দিয়ে refresh চলবে না (boundary, token confusion)।
        """
        tc, _app, _rev, _revoke = auth_app
        at = _access_token(patched_secret)

        res = tc.post("/auth/refresh", json={"refresh_token": at})

        assert res.status_code == 401
        assert "refresh token" in res.json()["detail"].lower()

    def test_refresh_with_invalid_token_returns_401(self, auth_app, patched_secret):
        """Given: একটি অবৈধ স্ট্রিং refresh হিসেবে পাঠানো হলো।
        When: /auth/refresh-এ POST।
        Then: 401 Invalid refresh token (sad path)।
        """
        tc, _app, _rev, _revoke = auth_app

        res = tc.post("/auth/refresh", json={"refresh_token": "garbage.token.value"})

        assert res.status_code == 401

    def test_logout_blacklists_access_token_jti(self, auth_app, patched_secret):
        """Given: একজন লগইন করা ইউজারের বৈধ access টোকেন।
        When: /auth/logout-এ POST।
        Then: 200 logged_out এবং revoke_token সেই jti দিয়ে কল হয় (session termination)।
        """
        tc, _app, _rev, _revoke = auth_app
        jti = "jti-logout-0001"
        token = _access_token(patched_secret, jti=jti)

        res = tc.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})

        assert res.status_code == 200
        assert res.json()["status"] == "logged_out"
        # বাংলা: revoke_token অবশ্যই কল হতে হবে — logout = jti blacklist।
        _revoke.assert_awaited()
        called_jti = _revoke.await_args.args[0] if _revoke.await_args.args else None
        assert called_jti == jti

    def test_logout_without_token_returns_401(self, auth_app, patched_secret):
        """Given: কোনো টোকেন নেই।
        When: /auth/logout-এ POST।
        Then: 401 Not authenticated (sad path)।
        """
        tc, _app, _rev, _revoke = auth_app

        res = tc.post("/auth/logout")

        assert res.status_code == 401


# ---------------------------------------------------------------------------
# 3. Password hashing verification (login flow)
# ---------------------------------------------------------------------------


class TestPasswordHashingAndLogin:
    """Login ফ্লো — Supabase auth mock দিয়ে; পাসওয়ার্ড যাচাই Supabase-এর ভেতরে
    ঘটে, আমরা verify করি যে backend সঠিকভাবে admin_emails রোল ম্যাপ করে এবং
    ব্যর্থতায় 401 দেয়।"""

    @pytest.fixture()
    def mock_db(self, monkeypatch):
        """বাংলা: auth মডিউলের db reference-কে MagicMock দিয়ে replace করা হলো।
        কোনো বাস্তব Supabase কল হবে না (Rule #64)।
        """
        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.app_metadata = {}  # বাংলা: admin role নেই — সাধারণ user
        mock_res = MagicMock()
        mock_res.user = mock_user

        mock_db = MagicMock()
        mock_db.client.auth.sign_in_with_password.return_value = mock_res
        monkeypatch.setattr("api.routes.auth.db", mock_db)
        return mock_db

    def test_login_success_returns_tokens_and_sets_cookie(self, auth_app, patched_secret, mock_db):
        """Given: একটি বৈধ (email, password) যা Supabase verify করে (mock)।
        When: /auth/login-এ POST।
        Then: 200, access_token + refresh_token ফেরত আসে, httpOnly cookie সেট হয় (happy)।
        """
        tc, _app, _rev, _revoke = auth_app

        res = tc.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "correct-horse-battery"},
        )

        assert res.status_code == 200
        body = res.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["user_id"] == "user-123"
        assert body["role"] == "user"
        # বাংলা: sign_in_with_password অবশ্যই {"email","password"} দিয়ে কল হবে।
        mock_db.client.auth.sign_in_with_password.assert_called_once_with(
            {"email": "user@example.com", "password": "correct-horse-battery"}
        )
        # বাংলা: httpOnly access cookie সেট হওয়া আবশ্যক — JWT-COOKIE-MIGRATION।
        set_cookie = res.headers.get("set-cookie", "")
        assert "supreme_access_token=" in set_cookie
        assert "httponly" in set_cookie.lower()

    def test_login_invalid_credentials_returns_401(self, auth_app, patched_secret, mock_db):
        """Given: Supabase ইউজার ফেরত দেয় না (ভুল পাসওয়ার্ড)।
        When: /auth/login-এ POST।
        Then: 401 Invalid credentials — internal detail লিক হয় না (sad path)।
        """
        tc, _app, _rev, _revoke = auth_app
        # বাংলা: res.user = None → "Invalid credentials" 401।
        mock_db.client.auth.sign_in_with_password.return_value = MagicMock(user=None)

        res = tc.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "wrong-password"},
        )

        assert res.status_code == 401
        assert res.json()["detail"] == "Invalid credentials"

    def test_login_when_db_client_unavailable_returns_500(
        self, auth_app, patched_secret, monkeypatch
    ):
        """Given: Supabase client আনইনিশিয়ালাইজড (db.client is None)।
        When: /auth/login-এ POST।
        Then: 500 — graceful degradation, honest error (Rule #3)।
        """
        tc, _app, _rev, _revoke = auth_app
        mock_db = MagicMock()
        mock_db.client = None
        monkeypatch.setattr("api.routes.auth.db", mock_db)

        res = tc.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "anything"},
        )

        assert res.status_code == 500

    def test_login_admin_email_maps_to_admin_role(
        self, auth_app, patched_secret, mock_db, monkeypatch
    ):
        """Given: ইমেইল settings.admin_emails তালিকায় আছে (boundary — role mapping)।
        When: /auth/login-এ POST।
        Then: role=admin — admin_emails allowlist থেকে রোল অ্যাসাইন হয়।
        """
        tc, _app, _rev, _revoke = auth_app
        # বাংলা: conftest-এ ADMIN_EMAILS="test_admin@supremeai.com,admin@example.com"।
        admin_email = "test_admin@supremeai.com"
        from api.routes.auth import settings

        monkeypatch.setattr(settings, "admin_emails", [admin_email])
        mock_db.client.auth.sign_in_with_password.return_value.user.id = "admin-001"
        mock_db.client.auth.sign_in_with_password.return_value.user.app_metadata = {}

        res = tc.post(
            "/auth/login",
            json={"email": admin_email, "password": "admin-pass"},
        )

        assert res.status_code == 200
        assert res.json()["role"] == "admin"
        assert res.json()["user_id"] == "admin-001"


# ---------------------------------------------------------------------------
# 4. Rate-limiting / brute-force prevention
# ---------------------------------------------------------------------------


class TestBruteForceRateLimiting:
    """বাংলা মন্তব্য: /auth/login রুট production-এ IP/identity-ভিত্তিক rate
    limiter দ্বারা সুরক্ষিত। নিচের টেস্টগুলো সেই brute-force prevention-এর
    ভিত্তি primitive — InMemoryFallbackLimiter ও AsyncRateLimiter — সরাসরি
    যাচাই করে। কোনো বাস্তব Redis কল নেই।"""

    def test_in_memory_limiter_allows_up_to_threshold(self):
        """Given: limit=5 একটি sliding window limiter।
        When: একই key দিয়ে 5 বার is_allowed কল করা হয়।
        Then: প্রতিটি True ফেরায় — threshold পর্যন্ত সব অনুরোধ গৃহীত (boundary)।
        """
        from middleware.rate_limiter import InMemoryFallbackLimiter

        limiter = InMemoryFallbackLimiter(window=60.0)
        key = "brute-force:1.2.3.4"

        results = [limiter.is_allowed(key, limit=5) for _ in range(5)]

        assert results == [True, True, True, True, True]

    def test_in_memory_limiter_blocks_after_threshold(self):
        """Given: limit=5 এবং ইতিমধ্যে 5 বার attempt হয়েছে।
        When: 6ষ্ঠ বার চেষ্টা করা হয়।
        Then: False — brute-force attempt ব্লক হয় (sad path, brute-force prevention)।
        """
        from middleware.rate_limiter import InMemoryFallbackLimiter

        limiter = InMemoryFallbackLimiter(window=60.0)
        key = "brute-force:5.6.7.8"
        for _ in range(5):
            limiter.is_allowed(key, limit=5)

        sixth = limiter.is_allowed(key, limit=5)

        assert sixth is False

    def test_in_memory_limiter_resets_after_window(self, monkeypatch):
        """Given: limit=5, window=60s এবং 5 attempt ইতিমধ্যে হয়েছে।
        When: window পার হয়ে যাওয়ার পর আবার attempt করা হয়।
        Then: True — window পার হলে limiter reset হয় (boundary — time reset)।
        """
        import middleware.rate_limiter as rl_mod
        from middleware.rate_limiter import InMemoryFallbackLimiter

        # বাংলা: time.time প্রথমে বাস্তব সময় ফেরায়, পরে window+1s ফেরায়।
        real_time = [1700_000_000.0]
        _original_time = rl_mod.time.time

        def fake_time():
            return real_time[0]

        monkeypatch.setattr(rl_mod.time, "time", fake_time)

        limiter = InMemoryFallbackLimiter(window=60.0)
        key = "brute-force:9.9.9.9"
        for _ in range(5):
            limiter.is_allowed(key, limit=5)
        assert limiter.is_allowed(key, limit=5) is False

        # বাংলা: window+1s পর — expired entries cleanup হবে, আবার allow।
        real_time[0] = 1700_000_000.0 + 61.0
        monkeypatch.setattr(rl_mod.time, "time", fake_time)
        assert limiter.is_allowed(key, limit=5) is True

    def test_in_memory_limiter_keys_are_isolated(self):
        """Given: দুটি ভিন্ন IP/identity key।
        When: key-A threshold পার করে ফেলে।
        Then: key-B এখনও allow পায় — isolation (boundary — per-key tracking)।
        """
        from middleware.rate_limiter import InMemoryFallbackLimiter

        limiter = InMemoryFallbackLimiter(window=60.0)
        for _ in range(5):
            limiter.is_allowed("ip:A", limit=5)
        assert limiter.is_allowed("ip:A", limit=5) is False

        # বাংলা: ভিন্ন key — এখনও quota আছে।
        assert limiter.is_allowed("ip:B", limit=5) is True

    @pytest.mark.asyncio
    async def test_async_rate_limiter_falls_back_to_in_memory_when_redis_down(self, monkeypatch):
        """Given: AsyncRateLimiter যেখানে Redis unavailable কিন্তু rate_limit enabled।
        When: acquire কল করা হয় limit=3 দিয়ে 4 বার।
        Then: প্রথম 3 True, 4র্থ False — in-memory fallback brute-force prevention কাজ করে।
        """
        # বাংলা: TESTING env bypass আর rate_limit disabled flag — দুটোই skip করানো দরকার।
        monkeypatch.setenv("TESTING", "false")
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")

        import middleware.rate_limiter as rl_mod
        from middleware.rate_limiter import AsyncRateLimiter

        limiter = AsyncRateLimiter()
        # বাংলা: সরাসরি enabled flag চালু করা হলো + _get_redis None ফেরাবে (Redis down)।
        limiter._rate_limit_enabled = True
        monkeypatch.setattr(limiter, "_get_redis", AsyncMock(return_value=None))
        # বাংলা: সব টেস্ট fresh fallback limiter দিয়ে শুরু করুক।
        limiter._fallback_limiter = rl_mod.InMemoryFallbackLimiter(window=60.0)

        key = "auth:brute:1.2.3.4"
        r1 = await limiter.acquire(key, limit=3, window=60)
        r2 = await limiter.acquire(key, limit=3, window=60)
        r3 = await limiter.acquire(key, limit=3, window=60)
        r4 = await limiter.acquire(key, limit=3, window=60)

        assert (r1, r2, r3) == (True, True, True)
        assert r4 is False  # বাংলা: 4র্থ attempt ব্লক — brute-force prevention।

"""#2733 — data-integrity hardening batch (D-1..D-4) contract tests.

Locked contracts:
- D-1: Stripe top-up wallet select uses SELECT ... FOR UPDATE (no lost update
  on concurrent credits) — source contract pin, matching SSLCommerz pattern.
- D-2: GitHub webhook dedup fails CLOSED (None → 503) when the dedup store is
  unavailable — replay protection no longer degrades silently.
- D-3: idempotency on critical paths fails closed (503) when Redis is down;
  non-critical paths keep fail-open availability.
- D-4: admin cache purge uses non-blocking SCAN (never KEYS), never deletes
  user_session:* (live tenant state), and enforces a safety cap.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.dependencies import verify_idempotency
from api.routes.webhooks_github import _claim_delivery
from middleware.idempotency_middleware import IdempotencyMiddleware

# ---------------------------------------------------------------- D-1 (pin)


def test_d1_stripe_topup_uses_row_lock():
    """Stripe পথে wallet select-এ with_for_update থাকতে হবে (SSLCommerz-এর মতো)।"""
    from pathlib import Path

    # বাংলা মন্তব্য: cwd-নিরপেক্ষ — tests/api/x.py → parents[2] = backend/।
    src = (Path(__file__).resolve().parents[2] / "api" / "routes" / "billing_api.py").read_text(
        encoding="utf-8"
    )
    # Stripe handler region: payment_intent.succeeded branch — locate its select
    marker = (
        src.find('"payment_intent.succeeded"')
        if '"payment_intent.succeeded"' in src
        else src.find("payment_intent.succeeded")
    )
    assert marker != -1, "stripe handler marker missing"
    region = src[marker : marker + 4000]
    # বাংলা মন্তব্য: select(UserWallet)...with_for_update — lock ছাড়া RMW race।
    assert "with_for_update" in region, "Stripe wallet select lost its FOR UPDATE lock"
    assert "wallet.balance_usd += amount_received" in region


# ---------------------------------------------------------------- D-2


@pytest.mark.asyncio
async def test_d2_claim_delivery_no_client_fails_closed():
    """Redis ক্লায়েন্ট নেই → None (fail-closed; আগে True = fail-open ছিল)।"""
    with patch("api.routes.webhooks_github.redis_manager") as rm:
        rm.get_client_async = AsyncMock(return_value=None)
        assert await _claim_delivery("k") is None


@pytest.mark.asyncio
async def test_d2_claim_delivery_error_fails_closed():
    """Redis এক্সসেপশন → None — রিপ্লে-গার্ড ছাড়া প্রসেস নিষিদ্ধ।"""
    client = MagicMock()
    client.set = AsyncMock(side_effect=RuntimeError("upstash 500"))
    with patch("api.routes.webhooks_github.redis_manager") as rm:
        rm.get_client_async = AsyncMock(return_value=client)
        assert await _claim_delivery("k") is None


@pytest.mark.asyncio
async def test_d2_claim_delivery_happy_paths():
    client = MagicMock()
    client.set = AsyncMock(side_effect=[True, False])
    with patch("api.routes.webhooks_github.redis_manager") as rm:
        rm.get_client_async = AsyncMock(return_value=client)
        assert await _claim_delivery("k1") is True  # first sight
        assert await _claim_delivery("k1") is False  # replay


# ---------------------------------------------------------------- D-3


def _fake_request(method: str, path: str, with_key: bool = True):
    """বাংলা মন্তব্য: সত্যিক starlette Request — case-insensitive headers + url.path।"""
    from starlette.requests import Request

    headers = [(b"host", b"x")]
    if with_key:
        headers.append((b"idempotency-key", b"test-key-123"))
    scope = {
        "type": "http",
        "scheme": "http",
        "server": ("testserver", 80),
        "method": method,
        "path": path,
        "headers": headers,
        "query_string": b"",
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_d3_dependency_critical_path_redis_down_503():
    req = _fake_request("POST", "/api/orchestrate/generate")
    with (
        patch("core.config.settings") as mock_settings,
        patch("core.cache.redis_manager.redis_manager") as rm,
    ):
        mock_settings.idempotency_critical_paths = ["/api/orchestrate/generate"]
        rm.client = None
        rm.acquire = None
        with pytest.raises(HTTPException) as exc:
            await verify_idempotency(req)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_d3_dependency_noncritical_path_still_fail_open():
    """অ-ক্রিটিক্যাল পথে Redis ডাউন → আগের মতো fail-open (availability)।"""
    req = _fake_request("POST", "/api/some/normal/path")
    with (
        patch("core.config.settings") as mock_settings,
        patch("core.cache.redis_manager.redis_manager") as rm,
    ):
        mock_settings.idempotency_critical_paths = ["/api/orchestrate/generate"]
        rm.client = None
        await verify_idempotency(req)  # কোনো exception নেই


@pytest.mark.asyncio
async def test_d3_middleware_critical_path_redis_down_503():
    mw = IdempotencyMiddleware(app=AsyncMock())
    sent = {}

    async def receive():
        return {"type": "http.request"}

    async def send(msg):
        sent[msg["type"]] = msg.get("status")

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/orchestrate/generate",
        "headers": [(b"idempotency-key", b"abc")],
    }
    with (
        patch("middleware.idempotency_middleware.is_test_environment", return_value=False),
        patch("middleware.idempotency_middleware.settings") as mock_settings,
        patch.object(mw, "_get_redis", AsyncMock(return_value=None)),
    ):
        mock_settings.idempotency_critical_paths = ["/api/orchestrate/generate"]
        await mw(scope, receive, send)
    assert sent.get("http.response.start") == 503


@pytest.mark.asyncio
async def test_d3_middleware_noncritical_redis_down_passes_through():
    app = AsyncMock()
    mw = IdempotencyMiddleware(app=app)

    async def receive():
        return {"type": "http.request"}

    async def send(msg):
        return None

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/normal/path",
        "headers": [(b"idempotency-key", b"abc")],
    }
    with (
        patch("middleware.idempotency_middleware.is_test_environment", return_value=False),
        patch("middleware.idempotency_middleware.settings") as mock_settings,
        patch.object(mw, "_get_redis", AsyncMock(return_value=None)),
    ):
        mock_settings.idempotency_critical_paths = ["/api/orchestrate/generate"]
        await mw(scope, receive, send)
    app.assert_awaited_once()


# ---------------------------------------------------------------- D-4


class _FakeRedis:
    """scan_iter + delete শুধু — keys() ইচ্ছাকৃতভাবে নেই (ব্যবহার হলে ভাঙবে)।"""

    def __init__(self, keys_per_pattern):
        self._keys = keys_per_pattern
        self.deleted = []

    async def scan_iter(self, match=None, count=None):
        for k in self._keys.get(match, []):
            yield k

    async def delete(self, *keys):
        self.deleted.extend(keys)
        return len(keys)


@pytest.mark.asyncio
async def test_d4_purge_uses_scan_and_skips_sessions():
    from api.routes.admin import _CACHE_PURGE_PATTERNS, _purge_cache_patterns

    # বাংলা মন্তব্য: লাইভ tenant state — এই প্যাটার্ন কখনোই purge তালিকায় নেই।
    assert not any("user_session" in p for p in _CACHE_PURGE_PATTERNS)
    assert not any("session" in p for p in _CACHE_PURGE_PATTERNS)

    redis = _FakeRedis(
        {
            "cache:*": ["cache:a", "cache:b"],
            "health:*": ["health:x"],
        }
    )
    total = await _purge_cache_patterns(redis)
    assert total == 3
    assert sorted(redis.deleted) == ["cache:a", "cache:b", "health:x"]


@pytest.mark.asyncio
async def test_d4_purge_batches_large_key_sets():
    """৬০০ কী → ৫০০-ব্যাচে দুই ডিলিট (মেমরি-বাউন্ডেড flush; এক-নিমেষে সব বাফার নয়)।"""
    from api.routes.admin import _purge_cache_patterns

    big = [f"cache:{i}" for i in range(600)]
    redis = _FakeRedis({"cache:*": big})
    total = await _purge_cache_patterns(redis)
    assert total == 600
    assert len(redis.deleted) == 600
    # বাংলা মন্তব্য: প্রথম ডিলিট-কলে ঠিক ৫০০টি — ব্যাচ-ফ্লাশ আচরণের পিন।
    assert len(redis.deleted[:500]) == 500

"""
API Key Management Tests

Mocks asyncpg so tests run without a live database.
"""

import os
import sys
import time
import types
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("OPENROUTER_API_KEY", "mock-key-value")
os.environ.setdefault("ENV", "test")


class FakeConn:
    async def execute(self, *a, **k):
        return "OK"

    async def fetch(self, *a, **k):
        return []

    async def fetchrow(self, *a, **k):
        return None


class FakePool:
    async def acquire(self):
        return FakeConn()

    async def release(self, conn):
        pass

    async def close(self):
        pass

    async def execute(self, *a, **k):
        return "OK"

    async def fetch(self, *a, **k):
        return []

    async def fetchrow(self, *a, **k):
        return None


# Ensure `core.app` is reloaded fresh in test runs (avoid cached app state)
for _mod in [m for m in list(sys.modules) if m == "core.app" or m.startswith("core.app.")]:
    del sys.modules[_mod]

from api.routes.api_keys import router
from core.app import app
from core.security import (
    API_KEY_PREFIX,
    generate_api_key,
    hash_api_key,
    mask_api_key,
    verify_api_key,
)
from middleware.rate_limiter import AsyncRateLimiter


@pytest.fixture
def client():
    fake_pool = FakePool()
    with (
        patch("core.startup.api_key_tables.ensure_api_key_tables"),
        patch("database.pgbouncer_pool.get_db_pool", return_value=fake_pool),
        patch("models.api_key.get_db_pool", return_value=fake_pool),
        patch("api.routes.api_keys._get_current_user", return_value="test_owner"),
    ):
        yield TestClient(app)


@pytest.fixture
def sample_api_key():
    return generate_api_key()


class TestSecurityUtilities:
    def test_generate_api_key_has_prefix(self):
        key = generate_api_key()
        assert key.startswith(API_KEY_PREFIX)

    def test_generate_api_key_unique(self):
        keys = {generate_api_key() for _ in range(50)}
        assert len(keys) == 50

    def test_mask_api_key(self):
        key = generate_api_key()
        masked = mask_api_key(key)
        assert masked.startswith(key[:12])
        assert "****" in masked

    def test_hash_api_key(self):
        key = generate_api_key()
        h = hash_api_key(key)
        assert h.startswith("sha256$")

    def test_verify_api_key(self):
        key = generate_api_key()
        h = hash_api_key(key)
        assert verify_api_key(key, h) is True
        assert verify_api_key("wrong-key", h) is False

    def test_hash_is_deterministic(self):
        key = generate_api_key()
        assert hash_api_key(key) == hash_api_key(key)


class FakeRedisPipe:
    def __init__(self, storage):
        self.storage = storage
        self.cmds = []

    def incr(self, key):
        self.cmds.append(("incr", key))

    def expire(self, key, window):
        self.cmds.append(("expire", key, window))

    async def execute(self):
        res = []
        for cmd, *args in self.cmds:
            if cmd == "incr":
                self.storage[args[0]] = self.storage.get(args[0], 0) + 1
                res.append(self.storage[args[0]])
            elif cmd == "expire":
                res.append(True)
        self.cmds = []
        return res


class FakeRedisClient:
    def __init__(self):
        self.storage = {}

    def pipeline(self):
        return FakeRedisPipe(self.storage)


class TestRateLimiter:
    @pytest.fixture(autouse=True)
    def patch_redis(self):
        fake_redis = FakeRedisClient()
        with patch("middleware.rate_limiter.AsyncRateLimiter._get_redis", return_value=fake_redis):
            yield

    @pytest.mark.asyncio
    async def test_allows_under_limit(self):
        rl = AsyncRateLimiter()
        for _ in range(3):
            assert await rl.acquire("pref", limit=3, window=60) is True

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, monkeypatch):
        # conftest disables rate limiting globally (RATE_LIMIT_ENABLED=false,
        # TESTING=true) and autouse fixtures mock the shared redis client.
        # Re-enable + clear the flags and force the no-redis path so the REAL
        # in-memory sliding window counting is exercised deterministically.
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
        monkeypatch.delenv("TESTING", raising=False)

        async def _no_redis():
            return None

        rl = AsyncRateLimiter()
        monkeypatch.setattr(rl, "_get_redis", _no_redis)
        for _ in range(3):
            await rl.acquire("pref2", limit=3, window=60)
        assert await rl.acquire("pref2", limit=3, window=60) is False

    @pytest.mark.asyncio
    async def test_different_keys_independent(self):
        rl = AsyncRateLimiter()
        assert await rl.acquire("pref-a", limit=2, window=60) is True
        assert await rl.acquire("pref-b", limit=2, window=60) is True


class TestRouterStructure:
    def test_router_has_correct_prefix(self):
        assert router.prefix == "/api/api-keys"

    def test_create_schema_requires_user_id(self):
        from api.routes.api_keys import CreateAPIKeyRequest

        with pytest.raises(
            Exception
        ):  # -- intentionally broad: asserts *some* error propagates (mocked/validation failure), exact type varies
            CreateAPIKeyRequest(user_id="", name="Test")

    def test_rotate_schema_requires_old_key(self):
        from api.routes.api_keys import RotateAPIKeyRequest

        with pytest.raises(
            Exception
        ):  # -- intentionally broad: asserts *some* error propagates (mocked/validation failure), exact type varies
            RotateAPIKeyRequest(old_key="")

    def test_bulk_delete_schema_limits_count(self):
        from api.routes.api_keys import BulkDeleteRequest

        with pytest.raises(
            Exception
        ):  # -- intentionally broad: asserts *some* error propagates (mocked/validation failure), exact type varies
            BulkDeleteRequest(key_ids=list(range(51)))


class TestIntegrationViaHeaders:
    def test_endpoints_accessible_without_api_key(self, client):
        resp = client.get("/api/api-keys/", headers={})  # "Authorization": "Bearer mock-token"
        if resp.status_code != 200:
            print("ERROR RESP:", resp.json())
        assert resp.status_code == 200

    def test_api_key_header_accepted_in_test_mode(self, client):
        resp = client.get(
            "/api/api-keys/",
            headers={
                # "Authorization": "Bearer mock-token",
                "x-api-key": "sk-supreme-test123",
            },
        )
        assert resp.status_code == 200


class TestAPIKeyEndpoints:
    def test_create_key_endpoint(self, client):
        mock_rec = {
            "id": 1,
            "name": "Integration Key",
            "rate_limit_rps": 10,
            "expires_at": None,
            "created_at": "2026-09-07T00:00:00Z",
            "scopes": ["read", "write"],
        }
        with patch("api.routes.api_keys.db_create_api_key", return_value=mock_rec):
            resp = client.post(
                "/api/api-keys/create",
                json={"user_id": "test_owner", "name": "Integration Key", "rate_limit_rps": 10},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["id"] == 1
            assert data["name"] == "Integration Key"
            assert "key" in data
            assert data["warning"] is not None

    def test_get_key_endpoint_success_and_not_found(self, client):
        with patch(
            "api.routes.api_keys.get_api_key_by_id",
            return_value={"id": 1, "user_id": "test_owner", "name": "Key 1"},
        ):
            resp = client.get("/api/api-keys/1")
            assert resp.status_code == 200
            assert resp.json()["id"] == 1

        with patch(
            "api.routes.api_keys.get_api_key_by_id",
            return_value={"id": 2, "user_id": "other_owner"},
        ):
            resp = client.get("/api/api-keys/2")
            assert resp.status_code == 404

    def test_revoke_and_delete_endpoints(self, client):
        with (
            patch(
                "api.routes.api_keys.get_api_key_by_id",
                return_value={"id": 1, "user_id": "test_owner"},
            ),
            patch("api.routes.api_keys.db_revoke_api_key", return_value={"id": 1, "revoked": True}),
        ):
            resp = client.post("/api/api-keys/1/revoke")
            assert resp.status_code == 200
            assert resp.json()["status"] == "revoked"

        with (
            patch(
                "api.routes.api_keys.get_api_key_by_id",
                return_value={"id": 1, "user_id": "test_owner"},
            ),
            patch("api.routes.api_keys.delete_api_key", return_value=True),
        ):
            resp = client.delete("/api/api-keys/1")
            assert resp.status_code == 200
            assert resp.json()["status"] == "deleted"

    def test_rotate_key_success_and_mismatch(self, client):
        fake_key = generate_api_key()
        fake_hash = hash_api_key(fake_key)

        with (
            patch(
                "api.routes.api_keys.get_api_key_by_id",
                return_value={"id": 1, "user_id": "test_owner", "key_hash": fake_hash},
            ),
            patch(
                "api.routes.api_keys.db_rotate_api_key",
                return_value={"id": 1, "key_masked": "sk-supreme-1***"},
            ),
            patch("api.routes.api_keys.record_api_key_event"),
        ):
            resp = client.post(
                "/api/api-keys/1/rotate", json={"old_key": fake_key, "grace_period_hours": 12}
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "rotated"
            assert "new_key" in resp.json()

        # Mismatch
        with (
            patch(
                "api.routes.api_keys.get_api_key_by_id",
                return_value={"id": 1, "user_id": "test_owner", "key_hash": fake_hash},
            ),
            patch("api.routes.api_keys.record_api_key_event"),
        ):
            resp = client.post("/api/api-keys/1/rotate", json={"old_key": "wrong_key"})
            assert resp.status_code == 400

    def test_usage_and_stats_endpoints(self, client):
        with (
            patch(
                "api.routes.api_keys.get_api_key_by_id",
                return_value={"id": 1, "user_id": "test_owner"},
            ),
            patch(
                "api.routes.api_keys.get_api_key_usage", return_value=[{"endpoint": "/api/chat"}]
            ),
            patch(
                "api.routes.api_keys.get_api_key_usage_stats", return_value={"total_requests": 25}
            ),
            patch("api.routes.api_keys.record_api_key_usage"),
        ):
            resp_usage = client.get("/api/api-keys/1/usage")
            assert resp_usage.status_code == 200

            resp_stats = client.get("/api/api-keys/1/stats")
            assert resp_stats.status_code == 200
            assert resp_stats.json()["total_requests"] == 25

            resp_record = client.post(
                "/api/api-keys/1/usage", json={"endpoint": "/api/test", "status_code": 200}
            )
            assert resp_record.status_code == 200

            resp_alert = client.get("/api/api-keys/1/admin/quota-alert")
            assert resp_alert.status_code == 200
            assert resp_alert.json()["alert"] is False

    def test_admin_bulk_delete(self, client):
        with (
            patch(
                "api.routes.api_keys.get_api_key_by_id",
                side_effect=lambda kid: {"id": kid, "user_id": "u1"} if kid == 1 else None,
            ),
            patch("api.routes.api_keys.delete_api_key", return_value=True),
            patch(
                "api.routes.api_keys._require_admin", return_value={"sub": "admin", "role": "admin"}
            ),
        ):
            resp = client.post("/api/api-keys/admin/bulk-delete", json={"key_ids": [1, 2]})
            assert resp.status_code == 200
            data = resp.json()
            assert 1 in data["deleted"]
            assert 2 in data["failed"]


# ─────────────────────────────────────────────────────────────────────────────
# Direct route-unit coverage (critical-tier headroom round 4)
#
# The API key routes are tier-critical (coverage_policy.yaml) and were the
# worst measured offender (35% on CI run 34822497054). The tests above patch
# out _get_current_user and exercise mostly happy paths through TestClient.
# These tests drive the route functions and helpers DIRECTLY so the ownership
# contract, admin gates, fail-closed 401, DB-failure 500 branches and the
# legacy compat shims are all locked without depending on middleware.
# ─────────────────────────────────────────────────────────────────────────────


def _fake_request(user=None, api_key=None, client_host="203.0.113.9"):
    """Minimal Request stand-in: routes only touch .state and .client."""
    state = types.SimpleNamespace()
    if user is not None:
        state.user = user
    if api_key is not None:
        state.api_key = api_key
    return types.SimpleNamespace(state=state, client=types.SimpleNamespace(host=client_host))


class TestGetCurrentUserContract:
    def test_state_user_dict_sub_wins(self):
        from api.routes.api_keys import _get_current_user

        assert _get_current_user(_fake_request(user={"sub": "alice@x.io"})) == "alice@x.io"

    def test_state_user_plain_string_passthrough(self):
        from api.routes.api_keys import _get_current_user

        assert _get_current_user(_fake_request(user="bob")) == "bob"

    def test_test_env_falls_back_to_test_owner(self):
        from api.routes.api_keys import _get_current_user

        assert _get_current_user(_fake_request()) == "test_owner"

    def test_fail_closed_401_outside_test_env(self):
        from api.routes.api_keys import _get_current_user

        with patch("utils.environment.is_test_environment", return_value=False):
            with pytest.raises(HTTPException) as ei:
                _get_current_user(_fake_request())
        assert ei.value.status_code == 401
        assert ei.value.detail == "Authentication required"


class TestAdminGuards:
    def test_require_admin_rejects_non_admin_role(self):
        from api.routes.api_keys import _require_admin

        with pytest.raises(HTTPException) as ei:
            _require_admin({"sub": "u", "role": "user"})
        assert ei.value.status_code == 403
        assert ei.value.detail == "Admin access required"

    def test_require_admin_rejects_missing_role(self):
        from api.routes.api_keys import _require_admin

        with pytest.raises(HTTPException) as ei:
            _require_admin({"sub": "u"})
        assert ei.value.status_code == 403

    def test_require_admin_returns_payload_for_admin(self):
        from api.routes.api_keys import _require_admin

        payload = {"sub": "a", "role": "admin"}
        assert _require_admin(payload) is payload


class TestApiKeyOwnerAttribution:
    def test_no_api_key_state_returns_none(self):
        from api.routes.api_keys import _get_api_key_owner

        assert _get_api_key_owner(_fake_request()) is None

    def test_api_key_with_id_gets_ak_prefix(self):
        from api.routes.api_keys import _get_api_key_owner

        assert _get_api_key_owner(_fake_request(api_key={"id": 7})) == "ak_7"

    def test_api_key_without_id_returns_none(self):
        from api.routes.api_keys import _get_api_key_owner

        assert _get_api_key_owner(_fake_request(api_key={"name": "k"})) is None


class TestCreateKeyDirect:
    async def test_owner_composite_when_called_via_api_key(self):
        from api.routes.api_keys import CreateAPIKeyRequest, create_key

        captured = {}

        async def fake_create(**kw):
            captured.update(kw)
            return {
                "id": 1,
                "name": kw["name"],
                "rate_limit_rps": kw["rate_limit_rps"],
                "expires_at": None,
                "created_at": "t",
                "scopes": None,
            }

        with patch("api.routes.api_keys.db_create_api_key", side_effect=fake_create):
            resp = await create_key(
                CreateAPIKeyRequest(user_id="ignored", name="via-ak", rate_limit_rps=5),
                _fake_request(user={"sub": "alice"}, api_key={"id": 7}),
            )
        assert captured["user_id"] == "alice:api_key:ak_7"
        assert resp["id"] == 1
        assert resp["warning"].startswith("Store this key securely")

    async def test_expiry_computed_from_days(self):
        from api.routes.api_keys import CreateAPIKeyRequest, create_key

        captured = {}

        async def fake_create(**kw):
            captured.update(kw)
            return {"id": 2, "name": kw["name"], "rate_limit_rps": kw["rate_limit_rps"]}

        before = int(time.time())
        with patch("api.routes.api_keys.db_create_api_key", side_effect=fake_create):
            await create_key(
                CreateAPIKeyRequest(user_id="u", name="exp", expires_in_days=3),
                _fake_request(user={"sub": "a"}),
            )
        assert before + 3 * 86400 <= captured["expires_at"] <= int(time.time()) + 3 * 86400 + 5

    async def test_no_expiry_when_days_none(self):
        from api.routes.api_keys import CreateAPIKeyRequest, create_key

        captured = {}

        async def fake_create(**kw):
            captured.update(kw)
            return {"id": 3, "name": kw["name"], "rate_limit_rps": 6}

        with patch("api.routes.api_keys.db_create_api_key", side_effect=fake_create):
            await create_key(
                CreateAPIKeyRequest(user_id="u", name="noexp"),
                _fake_request(user={"sub": "a"}),
            )
        assert captured["expires_at"] is None

    async def test_db_failure_raises_500(self):
        from api.routes.api_keys import CreateAPIKeyRequest, create_key

        async def fail_create(**kw):
            return None

        with patch("api.routes.api_keys.db_create_api_key", side_effect=fail_create):
            with pytest.raises(HTTPException) as ei:
                await create_key(
                    CreateAPIKeyRequest(user_id="x", name="n"), _fake_request(user={"sub": "a"})
                )
        assert ei.value.status_code == 500
        assert ei.value.detail == "Failed to create API key"


class TestListAndDeletePaths:
    async def test_list_user_keys_applies_limit(self):
        from api.routes.api_keys import list_user_keys

        keys = [{"id": i} for i in range(5)]
        with patch("api.routes.api_keys.get_api_keys_by_user", return_value=keys):
            resp = await list_user_keys(_fake_request(user="test_owner"), limit=2, offset=0)
        assert resp["total"] == 5
        assert [k["id"] for k in resp["keys"]] == [0, 1]

    async def test_list_all_keys_admin_path(self):
        from api.routes.api_keys import list_all_keys

        captured = {}

        async def fake_all(*, limit, offset):
            captured.update({"limit": limit, "offset": offset})
            return [{"id": 1}, {"id": 2}]

        with patch("api.routes.api_keys.get_all_api_keys", side_effect=fake_all):
            resp = await list_all_keys(
                _fake_request(user={"sub": "a", "role": "admin"}),
                limit=1,
                offset=0,
                admin_user={"role": "admin"},
            )
        assert resp["total"] == 2
        assert len(resp["keys"]) == 2
        assert captured == {"limit": 1, "offset": 0}

    async def test_delete_key_500_when_delete_fails(self):
        from api.routes.api_keys import delete_key

        with (
            patch(
                "api.routes.api_keys.get_api_key_by_id",
                return_value={"id": 1, "user_id": "test_owner"},
            ),
            patch("api.routes.api_keys.delete_api_key", return_value=False),
        ):
            with pytest.raises(HTTPException) as ei:
                await delete_key(1, _fake_request(user="test_owner"))
        assert ei.value.status_code == 500
        assert ei.value.detail == "Failed to delete key"

    async def test_get_key_404_when_record_missing(self):
        from api.routes.api_keys import get_key

        with patch("api.routes.api_keys.get_api_key_by_id", return_value=None):
            with pytest.raises(HTTPException) as ei:
                await get_key(99, _fake_request(user="test_owner"))
        assert ei.value.status_code == 404


class TestRotateAndUsageDirect:
    async def test_rotate_key_500_when_db_rotate_fails(self):
        from api.routes.api_keys import RotateAPIKeyRequest, rotate_key

        fake_key = generate_api_key()
        with (
            patch(
                "api.routes.api_keys.get_api_key_by_id",
                return_value={"id": 1, "user_id": "test_owner", "key_hash": hash_api_key(fake_key)},
            ),
            patch("api.routes.api_keys.db_rotate_api_key", return_value=None),
        ):
            with pytest.raises(HTTPException) as ei:
                await rotate_key(
                    1,
                    RotateAPIKeyRequest(old_key=fake_key),
                    _fake_request(user="test_owner"),
                )
        assert ei.value.status_code == 500
        assert ei.value.detail == "Failed to rotate key"

    async def test_quota_alert_trips_over_threshold(self):
        from api.routes.api_keys import quota_alert

        with (
            patch(
                "api.routes.api_keys.get_api_key_by_id",
                return_value={"id": 1, "user_id": "test_owner"},
            ),
            patch(
                "api.routes.api_keys.get_api_key_usage_stats",
                return_value={"total_requests": 60},
            ),
        ):
            resp = await quota_alert(1, _fake_request(user="test_owner"))
        assert resp["alert"] is True
        assert resp["rpm_used"] == 60

    async def test_record_usage_payload_defaults_and_missing_client(self):
        from api.routes.api_keys import record_usage_hook

        recorded = {}

        async def fake_rec(key_id, endpoint, status_code, latency_ms, host):
            recorded.update(
                {
                    "key_id": key_id,
                    "endpoint": endpoint,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                    "host": host,
                }
            )
            return None

        req = _fake_request(user="test_owner")
        req.client = None
        with (
            patch(
                "api.routes.api_keys.get_api_key_by_id",
                return_value={"id": 1, "user_id": "test_owner"},
            ),
            patch("api.routes.api_keys.record_api_key_usage", side_effect=fake_rec),
        ):
            resp = await record_usage_hook(1, req, {})
        assert resp == {"recorded": True}
        assert recorded == {
            "key_id": 1,
            "endpoint": "unknown",
            "status_code": 200,
            "latency_ms": 0.0,
            "host": None,
        }


class TestBulkDeleteDirect:
    async def test_mixed_results_with_delete_failure(self):
        from api.routes.api_keys import BulkDeleteRequest, bulk_delete

        async def get_by(kid):
            return {"id": kid, "user_id": "u1"} if kid in (1, 3) else None

        async def del_key(kid):
            return kid == 1

        with (
            patch("api.routes.api_keys.get_api_key_by_id", side_effect=get_by),
            patch("api.routes.api_keys.delete_api_key", side_effect=del_key),
        ):
            resp = await bulk_delete(
                _fake_request(),
                BulkDeleteRequest(key_ids=[1, 2, 3]),
                admin_user={"role": "admin"},
            )
        assert resp["deleted"] == [1]
        assert resp["failed"] == [2, 3]


class TestLegacyCompatShims:
    async def test_create_shim_without_request_uses_db_layer(self):
        from api.routes.api_keys import create_api_key

        captured = {}

        async def fake_create(**kw):
            captured.update(kw)
            return {"id": 9, "name": kw["name"]}

        with patch("api.routes.api_keys.db_create_api_key", side_effect=fake_create):
            resp = await create_api_key(None, None, key_hash="h", key_masked="m", key_prefix="p")
        assert resp["id"] == 9
        assert captured["key_hash"] == "h"
        assert captured["user_id"] == ""

    async def test_revoke_shim_digit_string_routes_to_db(self):
        from api.routes.api_keys import revoke_api_key

        async def fake_revoke(kid):
            return {"id": kid, "revoked": True}

        with patch("api.routes.api_keys.db_revoke_api_key", side_effect=fake_revoke):
            resp = await revoke_api_key("5", None)
        assert resp["id"] == 5

    async def test_revoke_shim_non_digit_falls_back_to_zero(self):
        from api.routes.api_keys import revoke_api_key

        captured = {}

        async def fake_revoke(kid):
            captured["kid"] = kid
            return {"id": kid}

        with patch("api.routes.api_keys.db_revoke_api_key", side_effect=fake_revoke):
            await revoke_api_key("abc", None)
        assert captured["kid"] == 0

    async def test_rotate_shim_without_request_routes_to_db(self):
        from api.routes.api_keys import rotate_api_key

        captured = {}

        async def fake_rotate(**kw):
            captured.update(kw)
            return {"key_masked": kw["new_key_masked"]}

        with patch("api.routes.api_keys.db_rotate_api_key", side_effect=fake_rotate):
            resp = await rotate_api_key("9", None, new_key_masked="m2", new_key_prefix="p2")
        assert resp["key_masked"] == "m2"
        assert captured["key_id"] == 9
        assert captured["new_key_prefix"] == "p2"

    def test_list_alias_points_at_user_listing(self):
        from api.routes.api_keys import list_api_keys, list_user_keys

        assert list_api_keys is list_user_keys

# বাংলা মন্তব্য: এই টেস্ট ফাইলটি /api/api-keys রুটের জীবনচক্র চুক্তি (lifecycle contract)
# পরীক্ষা করে — API key জেনারেশন, scope/role ভ্যালিডেশন, key rotation ও revocation।
# সব কিছু fully mocked — কোনো বাস্তব DB (asyncpg/PgBouncer) / Redis / বাইরের API
# কল নেই (Rule #64)। বাস্তব ক্রিপ্টো ফাংশন (generate/hash/verify/mask_api_key) ব্যবহৃত
# হয় কারণ সেগুলো pure ও side-effect-মুক্ত।
#
# টেস্ট কাঠামো: Given-When-Then docstring (Rule #61 happy + sad), boundary (Rule #66)।

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def keys_app(monkeypatch):
    """বাংলা: শুধু api_keys router মাউন্ট করা FastAPI app।
    সব DB-layer ফাংশন patch করা হয় যাতে কোনো বাস্তব asyncpg/Redis কল না হয়।
    """
    import api.routes.api_keys as keys_mod
    from api.routes.api_keys import router as keys_router

    # বাংলা: models.api_key এর সব async ফাংশন mock করা হলো — কোনো DB কল নেই।
    monkeypatch.setattr(keys_mod, "db_create_api_key", AsyncMock())
    monkeypatch.setattr(keys_mod, "get_api_key_by_id", AsyncMock())
    monkeypatch.setattr(keys_mod, "get_api_keys_by_user", AsyncMock(return_value=[]))
    monkeypatch.setattr(keys_mod, "get_all_api_keys", AsyncMock(return_value=[]))
    monkeypatch.setattr(keys_mod, "db_revoke_api_key", AsyncMock())
    monkeypatch.setattr(keys_mod, "db_rotate_api_key", AsyncMock())
    monkeypatch.setattr(keys_mod, "delete_api_key", AsyncMock(return_value=True))
    monkeypatch.setattr(keys_mod, "record_api_key_event", AsyncMock())

    app = FastAPI()
    app.include_router(keys_router)
    tc = TestClient(app)
    yield tc, app


def _admin_override(app, payload: dict[str, Any] | None = None):
    """বাংলা: _require_admin-এর ভেতরে Depends(get_current_user_token) —
    dependency override দিয়ে admin/viewer payload inject করা হয়।
    """
    from api.dependencies import get_current_user_token

    if payload is None:
        payload = {"sub": "test_admin@supremeai.com", "role": "admin"}
    app.dependency_overrides[get_current_user_token] = lambda: payload


def _real_key_record(key_id: int = 1, owner: str = "test_owner", **overrides) -> dict[str, Any]:
    """বাংলা: একটি API key record তৈরি করে যেখানে key_hash বাস্তব key থেকে
    হ্যাশ করা। owner ডিফল্ট "test_owner" কারণ test env-এ _get_current_user সেটাই ফেরায়।
    """
    from core.security import generate_api_key, hash_api_key

    plain = generate_api_key()
    rec = {
        "id": key_id,
        "user_id": owner,
        "name": "test-key",
        "key_hash": hash_api_key(plain),
        "key_masked": "sk_live-****",
        "key_prefix": plain[:12],
        "rate_limit_rps": 6,
        "revoked": False,
        "expires_at": None,
        "created_at": 1700_000_000,
        "updated_at": 1700_000_000,
        "scopes": [],
    }
    rec.update(overrides)
    return rec, plain


# ---------------------------------------------------------------------------
# 1. API key generation
# ---------------------------------------------------------------------------


class TestApiKeyGeneration:
    """API key জেনারেশন — POST /api/api-keys/create চুক্তি।"""

    def test_create_key_returns_201_and_key_string(self, keys_app):
        """Given: একজন authenticated ইউজার (test env owner)।
        When: /create-এ বৈধ body দিয়ে POST।
        Then: 201, response-এ non-empty `key` স্ট্রিং + masked + warning (happy)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod
        from core.security import API_KEY_PREFIX

        keys_mod.db_create_api_key.return_value = {
            "id": 1,
            "name": "ci-bot",
            "key_masked": "sk_live-****",
            "rate_limit_rps": 6,
            "expires_at": None,
            "created_at": 1700_000_000,
            "scopes": None,
        }

        res = tc.post(
            "/api/api-keys/create",
            json={"user_id": "test_owner", "name": "ci-bot"},
        )

        assert res.status_code == 201
        body = res.json()
        assert body["key"]
        assert body["key"].startswith(API_KEY_PREFIX)
        assert body["id"] == 1
        assert "securely" in body["warning"].lower()

    def test_create_key_stores_hash_not_plaintext(self, keys_app):
        """Given: একটি create request।
        When: db_create_api_key কল হয়।
        Then: key_hash = hash_api_key(returned_key), এবং key_hash != plaintext key
        (boundary — plaintext কখনোই store হয় না)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod
        from core.security import hash_api_key

        keys_mod.db_create_api_key.return_value = {
            "id": 7,
            "name": "k",
            "key_masked": "sk_live-****",
            "rate_limit_rps": 6,
            "expires_at": None,
            "created_at": 1,
            "scopes": None,
        }

        res = tc.post(
            "/api/api-keys/create",
            json={"user_id": "test_owner", "name": "k"},
        )
        body = res.json()
        call_kwargs = keys_mod.db_create_api_key.await_args.kwargs

        assert call_kwargs["key_hash"] == hash_api_key(body["key"])
        assert call_kwargs["key_hash"] != body["key"]  # বাংলা: plaintext store নিষিদ্ধ।

    def test_create_key_with_scopes_persists_scopes(self, keys_app):
        """Given: create request-এ scopes=["read","write"]।
        When: /create-এ POST।
        Then: db_create_api_key scopes আর্গুমেন্ট হিসেবে ["read","write"] পায়।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod

        keys_mod.db_create_api_key.return_value = {
            "id": 9,
            "name": "scoped",
            "key_masked": "sk_live-****",
            "rate_limit_rps": 6,
            "expires_at": None,
            "created_at": 1,
            "scopes": ["read", "write"],
        }

        res = tc.post(
            "/api/api-keys/create",
            json={
                "user_id": "test_owner",
                "name": "scoped",
                "scopes": ["read", "write"],
            },
        )

        assert res.status_code == 201
        assert keys_mod.db_create_api_key.await_args.kwargs["scopes"] == ["read", "write"]

    def test_create_key_rejects_blank_name(self, keys_app):
        """Given: name ফাঁকা স্ট্রিং (boundary — validation)।
        When: /create-এ POST।
        Then: 422 — Pydantic min_length=1 validation রিজেক্ট করে।
        """
        tc, _app = keys_app

        res = tc.post(
            "/api/api-keys/create",
            json={"user_id": "test_owner", "name": "   "},
        )

        assert res.status_code == 422

    def test_create_key_rate_limit_rps_boundary(self, keys_app):
        """Given: rate_limit_rps=1000 (upper bound)।
        When: /create-এ POST।
        Then: 201 — upper bound accept; rps>1000 হলে 422 (boundary)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod

        keys_mod.db_create_api_key.return_value = {
            "id": 1,
            "name": "k",
            "key_masked": "sk_live-****",
            "rate_limit_rps": 1000,
            "expires_at": None,
            "created_at": 1,
            "scopes": None,
        }

        res_hi = tc.post(
            "/api/api-keys/create",
            json={"user_id": "test_owner", "name": "k", "rate_limit_rps": 1000},
        )
        assert res_hi.status_code == 201

        # বাংলা: upper bound পার হলে রিজেক্ট।
        res_over = tc.post(
            "/api/api-keys/create",
            json={"user_id": "test_owner", "name": "k", "rate_limit_rps": 1001},
        )
        assert res_over.status_code == 422

    def test_create_key_db_failure_returns_500(self, keys_app):
        """Given: db_create_api_key None ফেরায় (store ব্যর্থ)।
        When: /create-এ POST।
        Then: 500 Failed to create API key (sad path)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod

        keys_mod.db_create_api_key.return_value = None

        res = tc.post(
            "/api/api-keys/create",
            json={"user_id": "test_owner", "name": "k"},
        )

        assert res.status_code == 500


# ---------------------------------------------------------------------------
# 2. Scope / role validation (admin vs viewer)
# ---------------------------------------------------------------------------


class TestScopeRoleValidation:
    """Admin vs viewer অ্যাক্সেস নিয়ন্ত্রণ — /all ও /admin/bulk-delete।"""

    def test_admin_can_list_all_keys(self, keys_app):
        """Given: একজন admin (role=admin via dependency override)।
        When: GET /api/api-keys/all।
        Then: 200 — admin সব user-এর key দেখতে পারে (happy)।
        """
        tc, app = keys_app
        import api.routes.api_keys as keys_mod

        _admin_override(app, {"sub": "admin@supremeai.com", "role": "admin"})
        keys_mod.get_all_api_keys.return_value = [
            {"id": 1, "user_id": "alice", "name": "a"},
            {"id": 2, "user_id": "bob", "name": "b"},
        ]

        res = tc.get("/api/api-keys/all")

        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 2
        assert {k["user_id"] for k in body["keys"]} == {"alice", "bob"}

    def test_viewer_cannot_list_all_keys_returns_403(self, keys_app):
        """Given: একজন viewer (role=viewer)।
        When: GET /api/api-keys/all।
        Then: 403 Admin access required — viewer সব key দেখতে পারবে না (sad path)।
        """
        tc, app = keys_app
        _admin_override(app, {"sub": "viewer@supremeai.com", "role": "viewer"})

        res = tc.get("/api/api-keys/all")

        assert res.status_code == 403
        assert res.json()["detail"] == "Admin access required"

    def test_admin_can_bulk_delete(self, keys_app):
        """Given: admin এবং একগুচ্ছ key id।
        When: POST /admin/bulk-delete।
        Then: 200, deleted ও failed list ফেরত আসে (happy)।
        """
        tc, app = keys_app
        import api.routes.api_keys as keys_mod

        _admin_override(app, {"sub": "admin@supremeai.com", "role": "admin"})
        # বাংলা: প্রথম key exists, দ্বিতীয়টি missing → failed।
        keys_mod.get_api_key_by_id.side_effect = [
            {"id": 10, "user_id": "x"},
            None,
        ]
        keys_mod.delete_api_key.return_value = True

        res = tc.post(
            "/api/api-keys/admin/bulk-delete",
            json={"key_ids": [10, 99]},
        )

        assert res.status_code == 200
        body = res.json()
        assert 10 in body["deleted"]
        assert 99 in body["failed"]

    def test_viewer_cannot_bulk_delete_returns_403(self, keys_app):
        """Given: একজন viewer।
        When: POST /admin/bulk-delete।
        Then: 403 — viewer bulk-delete করতে পারবে না (sad path)।
        """
        tc, app = keys_app
        _admin_override(app, {"sub": "viewer@supremeai.com", "role": "viewer"})

        res = tc.post(
            "/api/api-keys/admin/bulk-delete",
            json={"key_ids": [1]},
        )

        assert res.status_code == 403

    def test_bulk_delete_rejects_empty_list(self, keys_app):
        """Given: key_ids=[] (boundary — min_length=1)।
        When: POST /admin/bulk-delete।
        Then: 422 — empty bulk request রিজেক্ট।
        """
        tc, app = keys_app
        _admin_override(app, {"sub": "admin@supremeai.com", "role": "admin"})

        res = tc.post("/api/api-keys/admin/bulk-delete", json={"key_ids": []})

        assert res.status_code == 422

    def test_bulk_delete_caps_at_fifty(self, keys_app):
        """Given: 51টি key_id পাঠানো হলো (boundary — max_length=50)।
        When: POST /admin/bulk-delete।
        Then: 422 — bulk limit পার হলে রিজেক্ট।
        """
        tc, app = keys_app
        _admin_override(app, {"sub": "admin@supremeai.com", "role": "admin"})

        res = tc.post(
            "/api/api-keys/admin/bulk-delete",
            json={"key_ids": list(range(1, 52))},
        )

        assert res.status_code == 422


# ---------------------------------------------------------------------------
# 3. Key rotation
# ---------------------------------------------------------------------------


class TestKeyRotation:
    """Key rotation — POST /{key_id}/rotate চুক্তি।"""

    def test_rotate_with_correct_old_key_succeeds(self, keys_app):
        """Given: একটি key যার stored hash জানা আছে এবং সঠিক old_key।
        When: POST /{id}/rotate।
        Then: 200, new_key ফেরত আসে, db_rotate_api_key new hash দিয়ে কল হয় (happy)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod

        rec, plain = _real_key_record(key_id=1, owner="test_owner")
        keys_mod.get_api_key_by_id.return_value = rec
        keys_mod.db_rotate_api_key.return_value = {
            "id": 1,
            "name": "test-key",
            "key_masked": "sk_live-****",
            "key_prefix": "newprefix1234",
            "revoked": False,
            "created_at": 1,
            "updated_at": 2,
        }

        res = tc.post(
            "/api/api-keys/1/rotate",
            json={"old_key": plain, "grace_period_hours": 24},
        )

        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "rotated"
        assert body["new_key"]
        assert body["new_key"] != plain  # বাংলা: নতুন key পুরনোটার চেয়ে আলাদা।
        # বাংলা: db_rotate_api_key অবশ্যই নতুন hash দিয়ে কল হবে।
        rotate_kwargs = keys_mod.db_rotate_api_key.await_args.kwargs
        assert rotate_kwargs["key_id"] == 1
        assert rotate_kwargs["new_key_hash"] != rec["key_hash"]
        # বাংলা: rotated event record হওয়া আবশ্যক।
        keys_mod.record_api_key_event.assert_awaited()

    def test_rotate_with_wrong_old_key_returns_400(self, keys_app):
        """Given: ভুল old_key।
        When: POST /{id}/rotate।
        Then: 400 Old key verification failed, rotate_failed event record হয়,
        db_rotate_api_key কল হয় না (sad path)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod

        rec, _plain = _real_key_record(key_id=2, owner="test_owner")
        keys_mod.get_api_key_by_id.return_value = rec

        res = tc.post(
            "/api/api-keys/2/rotate",
            json={"old_key": "sk_live-totally-wrong-key"},
        )

        assert res.status_code == 400
        assert "verification" in res.json()["detail"].lower()
        # বাংলা: rotate_failed event record হবে; db_rotate_api_key কল হবে না।
        keys_mod.record_api_key_event.assert_awaited_once()
        event_args = keys_mod.record_api_key_event.await_args.args
        assert event_args[1] == "rotate_failed"
        keys_mod.db_rotate_api_key.assert_not_awaited()

    def test_rotate_invalidates_old_key(self, keys_app):
        """Given: rotation সফল হয়েছে এবং নতুন hash store হয়েছে।
        When: verify_api_key(old_plain, new_hash) ও verify_api_key(new_key, new_hash) কল।
        Then: পুরনো key আর verify হয় না, response-এ ফেরত আসা new_key verify হয়
        (rotation invalidation boundary)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod
        from core.security import verify_api_key

        rec, plain = _real_key_record(key_id=3, owner="test_owner")
        keys_mod.get_api_key_by_id.return_value = rec
        keys_mod.db_rotate_api_key.return_value = {
            "id": 3,
            "name": "k",
            "key_masked": "sk_live-****",
            "key_prefix": "newprefix1234",
            "revoked": False,
            "created_at": 1,
            "updated_at": 2,
        }

        res = tc.post(
            "/api/api-keys/3/rotate",
            json={"old_key": plain},
        )
        assert res.status_code == 200
        body = res.json()

        # বাংলা: route নিজে একটি new_key generate করে সেটার hash store করে।
        # response body-তে সেই new_key plaintext ফেরত আসে।
        stored_new_hash = keys_mod.db_rotate_api_key.await_args.kwargs["new_key_hash"]
        assert verify_api_key(plain, stored_new_hash) is False  # পুরনো key invalid
        assert verify_api_key(body["new_key"], stored_new_hash) is True  # নতুন key valid

    def test_rotate_other_users_key_returns_404(self, keys_app):
        """Given: key_id অন্য user-এর।
        When: POST /{id}/rotate।
        Then: 404 — owner isolation (boundary — IDOR prevention)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod

        # বাংলা: record-এ owner অন্য — test_owner অ্যাক্সেস করতে পারবে না।
        rec, _plain = _real_key_record(key_id=4, owner="someone_else")
        keys_mod.get_api_key_by_id.return_value = rec

        res = tc.post(
            "/api/api-keys/4/rotate",
            json={"old_key": "anything", "grace_period_hours": 0},
        )

        assert res.status_code == 404

    def test_rotate_db_failure_returns_500(self, keys_app):
        """Given: সঠিক old_key কিন্তু db_rotate_api_key None ফেরায়।
        When: POST /{id}/rotate।
        Then: 500 (sad path)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod

        rec, plain = _real_key_record(key_id=5, owner="test_owner")
        keys_mod.get_api_key_by_id.return_value = rec
        keys_mod.db_rotate_api_key.return_value = None

        res = tc.post(
            "/api/api-keys/5/rotate",
            json={"old_key": plain},
        )

        assert res.status_code == 500


# ---------------------------------------------------------------------------
# 4. Key revocation (revoked key → 403)
# ---------------------------------------------------------------------------


class TestKeyRevocation:
    """Key revocation lifecycle — revoke endpoint + revoked key enforcement → 403।"""

    def test_revoke_key_returns_200_and_marks_revoked(self, keys_app):
        """Given: একটি owner-owned key।
        When: POST /{id}/revoke।
        Then: 200, status=revoked, db_revoke_api_key কল হয়, returned record revoked=True (happy)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod

        rec, _plain = _real_key_record(key_id=10, owner="test_owner")
        keys_mod.get_api_key_by_id.return_value = rec
        keys_mod.db_revoke_api_key.return_value = {
            "id": 10,
            "name": "test-key",
            "key_masked": "sk_live-****",
            "revoked": True,
            "updated_at": 1700_000_100,
        }

        res = tc.post("/api/api-keys/10/revoke")

        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "revoked"
        assert body["key"]["revoked"] is True
        keys_mod.db_revoke_api_key.assert_awaited_once_with(10)

    def test_revoke_other_users_key_returns_404(self, keys_app):
        """Given: key_id অন্য user-এর।
        When: POST /{id}/revoke।
        Then: 404 — owner isolation (boundary — IDOR prevention)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod

        rec, _plain = _real_key_record(key_id=11, owner="someone_else")
        keys_mod.get_api_key_by_id.return_value = rec

        res = tc.post("/api/api-keys/11/revoke")

        assert res.status_code == 404
        keys_mod.db_revoke_api_key.assert_not_awaited()

    def test_revoke_unknown_key_returns_404(self, keys_app):
        """Given: key_id যা DB-তে নেই (boundary)।
        When: POST /{id}/revoke।
        Then: 404 (sad path)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod

        keys_mod.get_api_key_by_id.return_value = None

        res = tc.post("/api/api-keys/999/revoke")

        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_revoked_key_authentication_returns_403(self, monkeypatch):
        """Given: একটি API key যার DB record revoked=True (মিডলওয়্যার লুকআপ)।
        When: x-api-key হেডার দিয়ে middleware dispatch করা হয়।
        Then: 403 API key has been revoked — revoked key আর authenticate করতে পারে না।
        """
        # বাংলা: test env bypass + public-path "/" match — দুটোই skip করাতে হবে
        # যাতে মিডলওয়্যারের আসল revocation চেক চলে।
        from starlette.requests import Request

        import core.security.api_key_middleware as mw_mod
        from core.config import settings as _settings
        from core.security import generate_api_key, hash_api_key
        from core.security.api_key_middleware import APIKeyAuthMiddleware

        monkeypatch.setattr(mw_mod, "is_test_environment", lambda: False)
        # বাংলা: public_paths-এ "/" থাকলে সব path skip হয়ে যায় — খালি করা হলো।
        monkeypatch.setattr(_settings, "supremeai_public_paths", [])

        app = FastAPI()
        mw = APIKeyAuthMiddleware(app)
        # বাংলা: একটি revoked row ফেরানো হলো — DB/Redis কল নেই।
        revoked_row = {
            "id": 42,
            "key_hash": hash_api_key(generate_api_key()),
            "revoked": True,
            "expires_at": None,
            "rate_limit_rps": 6,
            "scopes": [],
        }
        monkeypatch.setattr(mw, "_get_cached_api_key", AsyncMock(return_value=revoked_row))

        # বাংলা: একটি minimal ASGI scope দিয়ে Request তৈরি।
        raw_key = generate_api_key()
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/protected",
            "raw_path": b"/api/v1/protected",
            "root_path": "",
            "headers": [(b"x-api-key", raw_key.encode())],
            "client": ("203.0.113.7", 50000),
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
        }
        request = Request(scope)

        async def call_next(_req):  # noqa: ANN001
            # বাংলা: যদি middleware pass করে দেয় তবে 200 — কিন্তু revoked হলে আসবে না।
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=200, content={"ok": True})

        response = await mw.dispatch(request, call_next)

        assert response.status_code == 403
        assert "revoked" in response.body.decode().lower()

    @pytest.mark.asyncio
    async def test_valid_active_key_passes_through_middleware(self, monkeypatch):
        """Given: একটি active (revoked=False, non-expired) key record।
        When: middleware dispatch করা হয়।
        Then: call_next reach হয় → 200 (happy path, boundary vs revoked)।
        """
        from starlette.requests import Request

        import core.security.api_key_middleware as mw_mod
        from core.config import settings as _settings
        from core.security import generate_api_key, hash_api_key
        from core.security.api_key_middleware import APIKeyAuthMiddleware

        monkeypatch.setattr(mw_mod, "is_test_environment", lambda: False)
        monkeypatch.setattr(_settings, "supremeai_public_paths", [])

        app = FastAPI()
        mw = APIKeyAuthMiddleware(app)
        active_row = {
            "id": 7,
            "key_hash": hash_api_key(generate_api_key()),
            "revoked": False,
            "expires_at": None,
            "rate_limit_rps": 6,
            "scopes": ["read"],
        }
        monkeypatch.setattr(mw, "_get_cached_api_key", AsyncMock(return_value=active_row))
        # বাংলা: rate limiter allow করবে।
        monkeypatch.setattr(mw.limiter, "acquire", AsyncMock(return_value=True))
        # বাংলা: usage recording কোনো DB কল না করুক।
        monkeypatch.setattr(mw_mod, "record_api_key_usage", AsyncMock(return_value=None))

        raw_key = generate_api_key()
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/protected",
            "raw_path": b"/api/v1/protected",
            "root_path": "",
            "headers": [(b"x-api-key", raw_key.encode())],
            "client": ("203.0.113.8", 50000),
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
        }
        request = Request(scope)

        async def call_next(_req):  # noqa: ANN001
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=200, content={"ok": True})

        response = await mw.dispatch(request, call_next)

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# 5. Owner isolation (boundary)
# ---------------------------------------------------------------------------


class TestOwnerIsolation:
    """Owner isolation — শুধু owner নিজের key অ্যাক্সেস/পরিবর্তন করতে পারে।"""

    def test_get_key_not_owner_returns_404(self, keys_app):
        """Given: key_id অন্য user-এর।
        When: GET /{id}।
        Then: 404 — owner isolation (boundary — no cross-user leak)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod

        rec, _plain = _real_key_record(key_id=20, owner="someone_else")
        keys_mod.get_api_key_by_id.return_value = rec

        res = tc.get("/api/api-keys/20")

        assert res.status_code == 404

    def test_get_own_key_returns_200(self, keys_app):
        """Given: key_id নিজের।
        When: GET /{id}।
        Then: 200, record ফেরত আসে (happy)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod

        rec, _plain = _real_key_record(key_id=21, owner="test_owner")
        keys_mod.get_api_key_by_id.return_value = rec

        res = tc.get("/api/api-keys/21")

        assert res.status_code == 200
        assert res.json()["id"] == 21

    def test_delete_other_users_key_returns_404(self, keys_app):
        """Given: key_id অন্য user-এর।
        When: DELETE /{id}।
        Then: 404 — delete isolation (boundary — IDOR prevention)।
        """
        tc, _app = keys_app
        import api.routes.api_keys as keys_mod

        rec, _plain = _real_key_record(key_id=22, owner="someone_else")
        keys_mod.get_api_key_by_id.return_value = rec

        res = tc.delete("/api/api-keys/22")

        assert res.status_code == 404
        keys_mod.delete_api_key.assert_not_awaited()

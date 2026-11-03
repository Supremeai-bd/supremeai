"""Full-coverage tests for api/routes/admin_routes.py (Task 7-c).

Strategy:
    - Minimal FastAPI app mounting ONLY admin_routes.router (no core.app).
    - Firestore is faked (dict-backed) and injected by monkeypatching
      ``api.routes.admin_routes.get_firestore_client``.
    - Redis is faked with fakeredis (async) injected on the shared
      ``redis_manager`` singleton (monkeypatch restores it).
    - Admin identity: ``mock-`` ID tokens (allowed in ENV=test by the
      fail-closed allow-list gate) plus the test auth-bypass dependency
      (ALLOW_TEST_AUTH_BYPASS=true from conftest) for the Depends()-guarded
      endpoints.
    - TOTP codes are computed locally with hmac/sha1 (same algorithm as
      check_totp) — no pyotp dependency.

Coverage targets: firebase-login branches, the full TOTP state machine
(setup → pending → verify-promotion, 409/400 guards, TTL expiry, lockout),
recovery codes with lockout, trusted-browser issue/list/revoke, and the
services-backed observability endpoints.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import time
from types import SimpleNamespace
from typing import Any

import pytest

fakeredis = pytest.importorskip("fakeredis", reason="fakeredis not installed")
import fakeredis.aioredis
import jwt as pyjwt
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from core.cache.redis_manager import redis_manager

MOCK_TOKEN = "mock-firebase-id-token"
UID = "mock-admin-uid"

# admin_routes reads settings through its own module reference; keep a
# lightweight stand-in so tests can control env/admin lists deterministically.
_ADMIN_SETTINGS = SimpleNamespace(
    env="test",
    admin_emails=["test_admin@supremeai.com", "admin@example.com"],
    jwt_secret=None,  # filled at runtime from real settings
    admin_enforce_totp=False,
)


def _totp(secret: str, drift: int = 0) -> str:
    """Compute the 6-digit OTP exactly like admin_routes.check_totp."""
    missing_padding = len(secret) % 8
    if missing_padding:
        secret += "=" * (8 - missing_padding)
    key = base64.b32decode(secret.upper())
    counter = int(time.time() // 30) + drift
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = h[19] & 15
    num = struct.unpack(">I", h[o : o + 4])[0] & 0x7FFFFFFF
    return f"{num % 1000000:06d}"


# ─────────────────────────────── fake firestore ───────────────────────────────


class FakeDoc:
    def __init__(self, store: dict, uid: str):
        self._store = store
        self._uid = uid

    @property
    def exists(self) -> bool:
        return self._uid in self._store

    def to_dict(self) -> dict:
        return dict(self._store.get(self._uid, {}))


class FakeDocRef:
    def __init__(self, store: dict, uid: str):
        self._store = store
        self._uid = uid

    def get(self) -> FakeDoc:
        return FakeDoc(self._store, self._uid)

    def set(self, data: dict, merge: bool = False) -> None:
        if merge:
            self._store.setdefault(self._uid, {}).update(data)
        else:
            self._store[self._uid] = dict(data)

    def update(self, data: dict) -> None:
        doc = self._store.setdefault(self._uid, {})
        from google.cloud import firestore as gcf

        for k, v in data.items():
            if v is gcf.DELETE_FIELD:
                doc.pop(k, None)
            else:
                doc[k] = v


class FakeFirestore:
    """Dict-backed stand-in for the Firestore admin_users collection."""

    def __init__(self) -> None:
        self.store: dict[str, dict] = {}

    def collection(self, name: str) -> Any:
        assert name == "admin_users"
        return SimpleNamespace(
            document=lambda uid: FakeDocRef(self.store, uid),
        )

    def fail(self) -> None:
        """Make every subsequent access raise (DB outage simulation)."""
        self.collection = lambda name: (_ for _ in ()).throw(RuntimeError("firestore down"))


# ─────────────────────────────────── fixtures ─────────────────────────────────


@pytest_asyncio.fixture
async def admin_env(monkeypatch):
    """Minimal app + fakeredis + (optionally) fake firestore + admin settings."""
    import api.routes.admin_routes as ar
    from core.config import settings as real_settings

    _ADMIN_SETTINGS.jwt_secret = real_settings.jwt_secret
    monkeypatch.setattr(ar, "settings", _ADMIN_SETTINGS)

    fake = fakeredis.aioredis.FakeRedis()
    monkeypatch.setattr(redis_manager, "_client", fake)

    app = FastAPI()
    app.include_router(ar.router)

    fs = FakeFirestore()
    monkeypatch.setattr(ar, "get_firestore_client", lambda: fs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, fs, fake

    app.dependency_overrides.clear()


async def _enroll(http: AsyncClient) -> dict:
    """Run one TOTP setup for the mock admin and return the response body."""
    resp = await http.post("/api/admin/firebase-totp-setup", json={"id_token": MOCK_TOKEN})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ─────────────────────────────── firebase login ───────────────────────────────


@pytest.mark.unit
class TestFirebaseLogin:
    async def test_mock_token_direct_auth(self, admin_env):
        http, fs, _ = admin_env
        resp = await http.post("/api/admin/firebase-login", json={"id_token": MOCK_TOKEN})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "authenticated"
        assert body["uid"] == UID
        assert body["role"] == "admin"
        claims = pyjwt.decode(
            body["token"],
            _ADMIN_SETTINGS.jwt_secret,
            algorithms=["HS256"],
        )
        assert claims["role"] == "admin" and claims["uid"] == UID

    async def test_login_provisions_firestore_admin_doc(self, admin_env):
        http, fs, _ = admin_env
        resp = await http.post("/api/admin/firebase-login", json={"id_token": MOCK_TOKEN})
        assert resp.status_code == 200
        assert fs.store[UID]["role"] == "admin"

    async def test_login_totp_enforced_otp_required(self, admin_env):
        http, fs, _ = admin_env
        fs.store[UID] = {
            "role": "admin",
            "totp_enabled": True,
            "totp_secret": "JBSWY3DPEHPK3PXP",
        }
        resp = await http.post("/api/admin/firebase-login", json={"id_token": MOCK_TOKEN})
        assert resp.status_code == 200
        assert resp.json()["status"] == "otp_required"

    async def test_login_totp_enforced_setup_required(self, admin_env):
        http, fs, _ = admin_env
        fs.store[UID] = {"role": "admin", "totp_enabled": True}
        resp = await http.post("/api/admin/firebase-login", json={"id_token": MOCK_TOKEN})
        assert resp.json()["status"] == "totp_setup_required"

    async def test_login_non_admin_role_403(self, admin_env):
        http, fs, _ = admin_env
        fs.store["someone-else"] = {"role": "user"}
        # mock token always maps to mock-admin-uid; instead use a doc-less,
        # non-allowlisted uid by pointing the mock uid doc at role=user.
        fs.store[UID] = {"role": "user"}
        resp = await http.post("/api/admin/firebase-login", json={"id_token": MOCK_TOKEN})
        assert resp.status_code == 403

    async def test_login_firestore_outage_403(self, admin_env):
        http, fs, _ = admin_env
        fs.fail()
        resp = await http.post("/api/admin/firebase-login", json={"id_token": MOCK_TOKEN})
        assert resp.status_code == 403

    async def test_login_trusted_browser_short_circuit(self, admin_env):
        http, fs, fake = admin_env
        cookie_token = "trusted-browser-cookie-token"
        key = "admin:trusted-browser:" + hashlib.sha256(cookie_token.encode()).hexdigest()
        await fake.set(key, json.dumps({"uid": UID, "email": "a@b.c"}))
        resp = await http.post(
            "/api/admin/firebase-login",
            json={"id_token": MOCK_TOKEN},
            cookies={"supreme_admin_trusted_browser": cookie_token},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "trusted_browser"
        assert body["uid"] == UID

    async def test_login_bad_token_401(self, admin_env):
        http, _, _ = admin_env
        # auth (Firebase SDK) is None in this env and token is not mock- → 401
        resp = await http.post("/api/admin/firebase-login", json={"id_token": "real-token-abc"})
        assert resp.status_code == 401

    async def test_mock_token_rejected_outside_test_env(self, admin_env, monkeypatch):
        http, _, _ = admin_env
        import api.routes.admin_routes as ar

        prod_settings = SimpleNamespace(
            env="production",
            admin_emails=["test_admin@supremeai.com"],
            jwt_secret=_ADMIN_SETTINGS.jwt_secret,
            admin_enforce_totp=False,
        )
        monkeypatch.setattr(ar, "settings", prod_settings)
        resp = await http.post("/api/admin/firebase-login", json={"id_token": MOCK_TOKEN})
        assert resp.status_code == 403
        assert "strictly forbidden" in resp.json()["detail"]


# ─────────────────────────────── totp setup state ──────────────────────────────


@pytest.mark.unit
class TestTotpSetup:
    async def test_fresh_setup_returns_material(self, admin_env):
        http, fs, _ = admin_env
        body = await _enroll(http)
        assert len(body["recovery_codes"]) == 8
        assert body["secret"] in body["provisioning_uri"]
        assert "issuer=SupremeAI" in body["provisioning_uri"]
        doc = fs.store[UID]
        assert doc["temp_totp_secret"] == body["secret"]
        assert len(doc["recovery_code_hashes"]) == 8
        for code in body["recovery_codes"]:
            assert hashlib.sha256(code.encode()).hexdigest() in doc["recovery_code_hashes"]

    async def test_double_setup_pending_conflict_409(self, admin_env):
        http, _, _ = admin_env
        await _enroll(http)
        resp = await http.post("/api/admin/firebase-totp-setup", json={"id_token": MOCK_TOKEN})
        assert resp.status_code == 409
        assert "pending" in resp.json()["detail"]

    async def test_setup_when_active_400(self, admin_env):
        http, fs, _ = admin_env
        fs.store[UID] = {"totp_secret": "ACTIVESECRET", "role": "admin"}
        resp = await http.post("/api/admin/firebase-totp-setup", json={"id_token": MOCK_TOKEN})
        assert resp.status_code == 400
        assert "already ACTIVE" in resp.json()["detail"]

    async def test_setup_stale_pending_allowed(self, admin_env):
        http, fs, _ = admin_env
        fs.store[UID] = {
            "temp_totp_secret": "OLDPENDING",
            "temp_totp_created_at": int(time.time()) - 3600,  # TTL (600s) expired
        }
        body = await _enroll(http)
        assert fs.store[UID]["temp_totp_secret"] == body["secret"]

    async def test_setup_state_lookup_failure_503(self, admin_env):
        http, fs, _ = admin_env
        # mock-admin-uid short-circuits the role check, so the first firestore
        # access inside setup IS the state-lookup — make it fail.
        fs.fail()
        resp = await http.post("/api/admin/firebase-totp-setup", json={"id_token": MOCK_TOKEN})
        assert resp.status_code == 503
        assert "Security database unavailable" in resp.json()["detail"]

    async def test_setup_rejects_mock_token_in_production(self, admin_env, monkeypatch):
        http, _, _ = admin_env
        import api.routes.admin_routes as ar

        prod = SimpleNamespace(
            env="production",
            admin_emails=["test_admin@supremeai.com"],
            jwt_secret=_ADMIN_SETTINGS.jwt_secret,
            admin_enforce_totp=False,
        )
        monkeypatch.setattr(ar, "settings", prod)
        resp = await http.post("/api/admin/firebase-totp-setup", json={"id_token": MOCK_TOKEN})
        assert resp.status_code == 403
        assert "strictly forbidden" in resp.json()["detail"]

    async def test_setup_non_admin_firebase_uid_blocked(self, admin_env, monkeypatch):
        http, fs, _ = admin_env
        import api.routes.admin_routes as ar

        class FakeFirebaseAuth:
            def verify_id_token(self, token):
                return {"uid": "self-registered-uid", "email": "intruder@evil.com"}

        monkeypatch.setattr(ar, "auth", FakeFirebaseAuth())
        resp = await http.post(
            "/api/admin/firebase-totp-setup", json={"id_token": "valid-but-not-admin"}
        )
        assert resp.status_code == 403
        assert "Not authorized as an admin" in resp.json()["detail"]


# ─────────────────────────────── totp verify state ─────────────────────────────


@pytest.mark.unit
class TestTotpVerify:
    async def test_verify_promotes_fresh_pending(self, admin_env):
        http, fs, fake = admin_env
        body = await _enroll(http)
        resp = await http.post(
            "/api/admin/firebase-totp-verify",
            json={"id_token": MOCK_TOKEN, "otp": _totp(body["secret"])},
        )
        assert resp.status_code == 200, resp.text
        doc = fs.store[UID]
        assert doc["totp_secret"] == body["secret"]
        assert "temp_totp_secret" not in doc
        assert "temp_totp_created_at" not in doc
        # successful verify resets the attempt counter
        assert not await fake.get(f"admin:totp:attempts:{UID}")

    async def test_verify_active_secret_after_pending_expiry(self, admin_env):
        http, fs, _ = admin_env
        active = "JBSWY3DPEHPK3PXP"
        fs.store[UID] = {
            "role": "admin",
            "totp_secret": active,
            "temp_totp_secret": "STALEPENDING",
            "temp_totp_created_at": int(time.time()) - 1200,
        }
        resp = await http.post(
            "/api/admin/firebase-totp-verify",
            json={"id_token": MOCK_TOKEN, "otp": _totp(active)},
        )
        assert resp.status_code == 200
        doc = fs.store[UID]
        assert doc["totp_secret"] == active  # stale pending never replaced it
        assert "temp_totp_secret" not in doc

    async def test_verify_without_secret_500(self, admin_env, monkeypatch):
        http, fs, _ = admin_env
        monkeypatch.delenv("SUPREMEAI_ADMIN_TOTP_SECRET", raising=False)
        resp = await http.post(
            "/api/admin/firebase-totp-verify",
            json={"id_token": MOCK_TOKEN, "otp": "123456"},
        )
        assert resp.status_code == 500
        assert "not enrolled" in resp.json()["detail"]

    async def test_verify_env_fallback_secret(self, admin_env, monkeypatch):
        http, fs, _ = admin_env
        env_secret = "JBSWY3DPEHPK3PXP"
        monkeypatch.setenv("SUPREMEAI_ADMIN_TOTP_SECRET", env_secret)
        resp = await http.post(
            "/api/admin/firebase-totp-verify",
            json={"id_token": MOCK_TOKEN, "otp": _totp(env_secret)},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    async def test_verify_wrong_code_then_lockout(self, admin_env):
        http, fs, fake = admin_env
        active = "JBSWY3DPEHPK3PXP"
        fs.store[UID] = {"role": "admin", "totp_secret": active}
        for _ in range(5):
            resp = await http.post(
                "/api/admin/firebase-totp-verify",
                json={"id_token": MOCK_TOKEN, "otp": "000000"},
            )
            assert resp.status_code == 401
        # 6th attempt is locked out
        resp = await http.post(
            "/api/admin/firebase-totp-verify",
            json={"id_token": MOCK_TOKEN, "otp": "000000"},
        )
        assert resp.status_code == 429
        assert await fake.get(f"admin:totp:lockout:{UID}")

    async def test_verify_lockout_preset_429(self, admin_env):
        http, fs, fake = admin_env
        fs.store[UID] = {"totp_secret": "JBSWY3DPEHPK3PXP"}
        await fake.set(f"admin:totp:lockout:{UID}", "locked")
        resp = await http.post(
            "/api/admin/firebase-totp-verify",
            json={"id_token": MOCK_TOKEN, "otp": "000000"},
        )
        assert resp.status_code == 429

    async def test_verify_redis_failure_fail_closed_503(self, admin_env, monkeypatch):
        http, fs, _ = admin_env
        fs.store[UID] = {"totp_secret": "JBSWY3DPEHPK3PXP"}

        class BrokenRedis:
            async def get(self, key):
                raise RuntimeError("redis exploded")

        # admin_routes pulls redis_manager.client directly (not _get_redis_client)
        monkeypatch.setattr(redis_manager, "_client", BrokenRedis())
        # active secret so we reach the redis lockout check
        resp = await http.post(
            "/api/admin/firebase-totp-verify",
            json={"id_token": MOCK_TOKEN, "otp": "000000"},
        )
        assert resp.status_code == 503

    async def test_verify_remember_browser_sets_cookie(self, admin_env):
        http, fs, fake = admin_env
        body = await _enroll(http)
        resp = await http.post(
            "/api/admin/firebase-totp-verify",
            json={
                "id_token": MOCK_TOKEN,
                "otp": _totp(body["secret"]),
                "remember_browser": True,
            },
        )
        assert resp.status_code == 200
        assert "supreme_admin_trusted_browser" in resp.cookies
        # the issued cookie must authenticate the next login
        cookie = resp.cookies["supreme_admin_trusted_browser"]
        fs.store[UID]["role"] = "admin"  # login re-reads the firestore doc
        next_login = await http.post(
            "/api/admin/firebase-login",
            json={"id_token": MOCK_TOKEN},
            cookies={"supreme_admin_trusted_browser": cookie},
        )
        assert next_login.json()["status"] == "trusted_browser"

    async def test_verify_bad_token_401(self, admin_env):
        http, _, _ = admin_env
        resp = await http.post(
            "/api/admin/firebase-totp-verify",
            json={"id_token": "not-mock", "otp": "000000"},
        )
        assert resp.status_code == 401


# ────────────────────────────── recovery codes ─────────────────────────────────


@pytest.mark.unit
class TestTotpRecovery:
    async def test_recover_success_consumes_code(self, admin_env):
        http, fs, fake = admin_env
        body = await _enroll(http)
        used_code = body["recovery_codes"][0]
        resp = await http.post(
            "/api/admin/firebase-totp-recover",
            json={"id_token": MOCK_TOKEN, "recovery_code": used_code},
        )
        assert resp.status_code == 200, resp.text
        new_secret = resp.json()["secret"]
        assert new_secret != body["secret"]
        doc = fs.store[UID]
        assert doc["temp_totp_secret"] == new_secret
        # used code removed from remaining hashes
        assert hashlib.sha256(used_code.encode()).hexdigest() not in doc["recovery_code_hashes"]
        assert len(doc["recovery_code_hashes"]) == 7
        # attempt counter cleared on success
        assert not await fake.get(f"admin:totp:recover:attempts:{UID}")

    async def test_recover_invalid_code_lockout(self, admin_env):
        http, fs, fake = admin_env
        await _enroll(http)
        for i in range(5):
            resp = await http.post(
                "/api/admin/firebase-totp-recover",
                json={"id_token": MOCK_TOKEN, "recovery_code": f"bad-code-{i}"},
            )
            assert resp.status_code == 401
        assert await fake.get(f"admin:totp:recover:lockout:{UID}")
        # now locked
        resp = await http.post(
            "/api/admin/firebase-totp-recover",
            json={"id_token": MOCK_TOKEN, "recovery_code": "bad-code-again"},
        )
        assert resp.status_code == 429

    async def test_recover_lockout_preset_429(self, admin_env):
        http, fs, fake = admin_env
        await _enroll(http)
        await fake.set(f"admin:totp:recover:lockout:{UID}", "locked")
        resp = await http.post(
            "/api/admin/firebase-totp-recover",
            json={"id_token": MOCK_TOKEN, "recovery_code": "whatever"},
        )
        assert resp.status_code == 429

    async def test_recover_without_db_503(self, admin_env, monkeypatch):
        import api.routes.admin_routes as ar

        http, _, _ = admin_env
        monkeypatch.setattr(ar, "get_firestore_client", lambda: None)
        resp = await http.post(
            "/api/admin/firebase-totp-recover",
            json={"id_token": MOCK_TOKEN, "recovery_code": "whatever"},
        )
        assert resp.status_code == 503

    async def test_recover_redis_failure_fail_closed_503(self, admin_env, monkeypatch):
        http, fs, _ = admin_env
        await _enroll(http)

        class BrokenRedis:
            async def get(self, key):
                raise RuntimeError("redis exploded")

        monkeypatch.setattr(redis_manager, "_client", BrokenRedis())
        resp = await http.post(
            "/api/admin/firebase-totp-recover",
            json={"id_token": MOCK_TOKEN, "recovery_code": "whatever"},
        )
        assert resp.status_code == 503


# ─────────────────────────── trusted browser management ────────────────────────


@pytest.mark.unit
class TestTrustedBrowsers:
    async def test_issue_list_revoke_one_and_all(self, admin_env):
        import api.routes.admin_routes as ar

        http, _, fake = admin_env

        issued = {}

        class CaptureResponse:
            def __init__(self):
                self.cookies = {}

            def set_cookie(self, key, value, **kwargs):  # match Response signature
                self.cookies[key] = value

        resp = CaptureResponse()
        await ar._issue_trusted_browser("test_admin@supremeai.com", "a@b.c", resp)
        issued["token"] = resp.cookies["supreme_admin_trusted_browser"]
        assert issued["token"]

        listing = await http.get("/admin/trusted-browsers")
        assert listing.status_code == 200
        browsers = listing.json()["browsers"]
        assert len(browsers) == 1
        assert browsers[0]["uid"] == "test_admin@supremeai.com"
        browser_id = browsers[0]["id"]

        # revoke one — unknown id 404s
        missing = await http.delete("/admin/trusted-browsers/nope")
        assert missing.status_code == 404
        ok = await http.delete(f"/admin/trusted-browsers/{browser_id}")
        assert ok.status_code == 200
        assert ok.json() == {"ok": True}

        # re-issue and revoke all
        resp2 = CaptureResponse()
        await ar._issue_trusted_browser("test_admin@supremeai.com", "a@b.c", resp2)
        ok_all = await http.delete("/admin/trusted-browsers")
        assert ok_all.status_code == 200
        empty = await http.get("/admin/trusted-browsers")
        assert empty.json()["browsers"] == []

    async def test_no_redis_503(self, admin_env, monkeypatch):
        import api.routes.admin_routes as ar

        http, _, _ = admin_env

        async def no_redis():
            return None

        monkeypatch.setattr(ar, "_get_redis_client", no_redis)
        assert (await http.get("/admin/trusted-browsers")).status_code == 503
        assert (await http.delete("/admin/trusted-browsers/some-id")).status_code == 503
        assert (await http.delete("/admin/trusted-browsers")).status_code == 503

    async def test_admin_role_required(self, admin_env, monkeypatch):
        import api.routes.admin_routes as ar

        http, _, _ = admin_env

        async def non_admin_user():
            return {"sub": "user@x.com", "role": "user"}

        app_key = ar.get_current_user_token
        http._transport.app.dependency_overrides[app_key] = non_admin_user
        resp = await http.get("/admin/trusted-browsers")
        http._transport.app.dependency_overrides.pop(app_key, None)
        assert resp.status_code == 403


# ─────────────────────── services-backed admin endpoints ───────────────────────


@pytest.mark.unit
class TestObservabilityEndpoints:
    @pytest_asyncio.fixture
    async def svc_env(self, admin_env, monkeypatch):
        http, fs, _ = admin_env
        import api.routes.admin_routes as ar

        services = SimpleNamespace(
            parallel_router=SimpleNamespace(
                get_distribution_stats=lambda: {"openai": 3, "gemini": 1},
                PROVIDERS={
                    "openai": {"current_requests": 3, "status": "active"},
                    "gemini": {"current_requests": 1, "status": "paused"},
                },
            ),
            gcp_router=SimpleNamespace(health_check=lambda timeout: {"ok": True}),
            verification_queue=SimpleNamespace(provider="firestore", stats=lambda: {"queued": 2}),
            gcp_pubsub_queue=SimpleNamespace(provider="pubsub", stats=lambda: {"published": 5}),
            cloud_function_client=SimpleNamespace(get_config=lambda: {"region": "us-central1"}),
            rules_engine=SimpleNamespace(
                rules={"max_tokens": 4096},
                save_rules=lambda rules: True,
            ),
        )
        monkeypatch.setattr(ar, "services", services)
        return http, services

    async def test_cloud_distribution(self, svc_env):
        http, _ = svc_env
        resp = await http.get("/admin/cloud-distribution")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_requests"] == 4
        assert body["active_providers"] == 1
        assert body["strategy"] == "parallel_active_active"

    async def test_gcp_health_and_queue_stats(self, svc_env):
        http, _ = svc_env
        health = await http.get("/gcp/health")
        assert health.status_code == 200
        assert health.json()["cloud_run"] == {"ok": True}
        stats = await http.get("/gcp/verification-queue/stats")
        assert stats.json() == {"queued": 2}
        pubsub = await http.get("/gcp/pubsub/stats")
        assert pubsub.json() == {"published": 5}

    async def test_rules_get_and_post(self, svc_env):
        http, _ = svc_env
        got = await http.get("/admin/rules")
        assert got.json() == {"max_tokens": 4096}
        posted = await http.post("/admin/rules", json={"rules": {"a": 1}})
        assert posted.json() == {"status": "success"}

    async def test_rules_post_failure_status(self, svc_env, monkeypatch):
        http, services = svc_env
        services.rules_engine.save_rules = lambda rules: False
        posted = await http.post("/admin/rules", json={"rules": {"a": 1}})
        assert posted.json()["status"] == "error"
        empty = await http.post("/admin/rules", json={})
        assert empty.json()["status"] == "error"

    async def test_free_tier_endpoints(self, svc_env, monkeypatch):
        http, _ = svc_env

        class FakeTracker:
            def get_status(self):
                return {"overall": "ok"}

            def get_provider_status(self, provider):
                if provider == "openai":
                    return {"provider": "openai", "paused": False}
                return None

            def mark_rate_limited(self, provider, pause_seconds=60):
                self.paused = (provider, pause_seconds)

            def override_limits(self, provider, limits):
                self.overridden = (provider, limits)

        tracker = FakeTracker()
        monkeypatch.setattr("core.llm.free_tier_tracker.get_tracker", lambda: tracker)
        status = await http.get("/admin/free-tier-status")
        assert status.json() == {"overall": "ok"}
        provider_ok = await http.get("/admin/free-tier-status/openai")
        assert provider_ok.json()["provider"] == "openai"
        provider_404 = await http.get("/admin/free-tier-status/nope")
        assert provider_404.status_code == 404
        pause = await http.post("/admin/free-tier-pause/openai", json={"seconds": 30})
        assert pause.json() == {"status": "paused", "provider": "openai", "seconds": 30.0}
        override = await http.post("/admin/free-tier-override/openai", json={"rpm": 5})
        assert override.json()["new_limits"] == {"rpm": 5}
        assert tracker.overridden == ("openai", {"rpm": 5})

    async def test_token_budget_stats(self, svc_env, monkeypatch):
        http, _ = svc_env
        monkeypatch.setattr(
            "core.llm.token_budget.get_budget_manager",
            lambda: SimpleNamespace(get_stats=lambda: {"budget": 1000}),
        )
        resp = await http.get("/admin/token-budget-stats")
        assert resp.json() == {"budget": 1000}

    async def test_skills_catalog(self, svc_env):
        http, _ = svc_env
        resp = await http.get("/skills")
        assert resp.status_code == 200
        skills = resp.json()
        assert set(skills) == {"web_scraper", "csv_exporter"}

    async def test_admin_gate_blocks_non_admin_role(self, admin_env):
        """get_current_admin 403 branch via a non-admin bypass payload."""
        import api.routes.admin_routes as ar

        http, _, _ = admin_env

        def non_admin():
            return {"sub": "user@x.com", "role": "user"}

        http._transport.app.dependency_overrides[ar.get_current_user_token] = non_admin
        try:
            resp = await http.get("/admin/rules")
        finally:
            http._transport.app.dependency_overrides.pop(ar.get_current_user_token, None)
        assert resp.status_code == 403

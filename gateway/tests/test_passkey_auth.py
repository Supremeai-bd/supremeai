"""
gateway/tests/test_passkey_auth.py — Hermetic Tests for Native WebAuthn/Passkey Engine.
"""
import base64
import json
import os
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from gateway.service.app import app
from gateway.service.keygen import generate_key
from gateway.service.storage import (
    get_user_passkey,
    list_user_passkeys,
    revoke_user_passkey,
    save_user_passkey,
)


class TestPasskeyAuth(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_passkey_register_options_require_a_session(self):
        # Anonymous registrations used to mint throwaway usr-<random> principals.
        resp = self.client.post(
            "/api/auth/passkey/register/options",
            json={
                "user_id": "usr-test-123",
                "email": "test@supremeai.com",
                "role": "user",
                "display_name": "Test User",
            },
        )
        self.assertEqual(resp.status_code, 401)

    def test_passkey_register_options(self):
        with patch.dict(os.environ, {"SUPREMEAI_MASTER_KEY": _TEST_MASTER_KEY}):
            token = generate_key(client_name="usr-usr-" + uuid.uuid4().hex[:12], quota="standard")
            resp = self.client.post(
                "/api/auth/passkey/register/options",
                json={"email": "test@supremeai.com", "display_name": "Test User"},
                headers={"Authorization": f"Bearer {token}", "Origin": _ORIGIN},
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("challenge", data)
        self.assertEqual(data["rp"]["id"], _RP_ID)
        self.assertEqual(data["user"]["name"], "test@supremeai.com")
        self.assertEqual(data["excludeCredentials"], [])

    def test_passkey_login_options(self):
        resp = self.client.post(
            "/api/auth/passkey/login/options",
            json={"role": "user"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("challenge", data)
        self.assertEqual(data["userVerification"], "required")

    def test_passkey_device_storage_lifecycle(self):
        # Hermetic credential id: the shared /tmp gateway_state.db outlives the pytest
        # process, and save_user_passkey's upsert does not reset `revoked` — a constant
        # id revoked by the previous run stayed revoked=1 and step 2's `revoked = 0`
        # lookup returned None (cross-run pollution, class F-K). Unique id per run.
        run_nonce = uuid.uuid4().hex[:12]
        cred_id = "cred-mock-test-" + base64.urlsafe_b64encode(
            f"random-key-{run_nonce}".encode()
        ).decode().rstrip("=")
        user_id = "usr-tester-99"

        # 1. Save
        saved = save_user_passkey(
            credential_id=cred_id,
            user_id=user_id,
            role="user",
            public_key_spki="mock-spki",
            device_name="MacBook Touch ID",
        )
        self.assertEqual(saved["credential_id"], cred_id)

        # 2. Get
        fetched = get_user_passkey(cred_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["device_name"], "MacBook Touch ID")

        # 3. List
        devices = list_user_passkeys(user_id)
        self.assertTrue(any(d["credential_id"] == cred_id for d in devices))

        # 4. Revoke
        revoked = revoke_user_passkey(cred_id, user_id)
        self.assertTrue(revoked)
        self.assertIsNone(get_user_passkey(cred_id))


_TEST_MASTER_KEY = "test-master-key-32-bytes-supersecret-token"
_RP_ID = "studio.example"
_ORIGIN = "https://studio.example"


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _fake_attestation(challenge_b64: str) -> tuple[dict, str]:
    """Builds a minimal 'none' attestation for rp 'studio.example' (P-256 COSE key, UP+UV+AT)."""
    import hashlib

    from cryptography.hazmat.primitives.asymmetric import ec

    pub = ec.generate_private_key(ec.SECP256R1()).public_key().public_numbers()
    cred_id = uuid.uuid4().bytes
    cose = (
        bytes([0xA5, 0x01, 0x02, 0x03, 0x26, 0x20, 0x01])
        + bytes([0x21, 0x58, 0x20]) + pub.x.to_bytes(32, "big")
        + bytes([0x22, 0x58, 0x20]) + pub.y.to_bytes(32, "big")
    )
    auth_data = (
        hashlib.sha256(_RP_ID.encode()).digest() + bytes([0x45]) + b"\x00\x00\x00\x00" + b"\x00" * 16
        + len(cred_id).to_bytes(2, "big") + cred_id + cose
    )
    attestation = (
        bytes([0xA3, 0x63]) + b"fmt" + bytes([0x64]) + b"none"
        + bytes([0x67]) + b"attStmt" + bytes([0xA0])
        + bytes([0x68]) + b"authData" + bytes([0x59]) + len(auth_data).to_bytes(2, "big") + auth_data
    )
    client_data = json.dumps(
        {"type": "webauthn.create", "challenge": challenge_b64, "origin": _ORIGIN}
    ).encode()
    payload = {
        "clientDataJSON": _b64u(client_data),
        "attestationObject": _b64u(attestation),
        "device_name": "Windows Hello",
    }
    return payload, _b64u(cred_id)


class TestPasskeyOwnerBinding(unittest.TestCase):
    """Regression (2026-11-27): passkeys saved under a random id, so Settings showed none."""

    def setUp(self):
        self.env = patch.dict(os.environ, {"SUPREMEAI_MASTER_KEY": _TEST_MASTER_KEY})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = TestClient(app)
        self.owner = "usr-" + uuid.uuid4().hex[:12]
        self.token = generate_key(client_name=f"usr-{self.owner}", quota="standard")

    def _auth(self, token=None):
        return {"Authorization": f"Bearer {token or self.token}", "Origin": _ORIGIN}

    def _register(self):
        opts = self.client.post(
            "/api/auth/passkey/register/options",
            json={"email": "owner@supremeai.com", "user_id": "usr-attacker"},
            headers=self._auth(),
        )
        self.assertEqual(opts.status_code, 200)
        user_handle = opts.json()["user"]["id"]
        self.assertEqual(base64.urlsafe_b64decode(user_handle + "==").decode(), self.owner)
        payload, cred_id = _fake_attestation(opts.json()["challenge"])
        verify = self.client.post(
            "/api/auth/passkey/register/verify", json=payload, headers=self._auth()
        )
        self.assertEqual(verify.status_code, 200, verify.text)
        self.assertEqual(verify.json()["passkey"]["user_id"], self.owner)
        return cred_id

    def test_registered_passkey_is_listed_for_the_session_owner(self):
        cred_id = self._register()
        # Legacy clients still send ?user_id=<email>; the server ignores it.
        listed = self.client.get(
            "/api/auth/passkey/devices?user_id=owner@supremeai.com", headers=self._auth()
        )
        self.assertEqual(listed.status_code, 200)
        self.assertIn(cred_id, [d["credential_id"] for d in listed.json()["devices"]])

    def test_supabase_uuid_principal_is_stable(self):
        supa_uid = str(uuid.uuid4())
        token = generate_key(client_name=f"usr-{supa_uid}", quota="standard")
        opts = self.client.post(
            "/api/auth/passkey/register/options", json={}, headers=self._auth(token)
        )
        self.assertEqual(opts.status_code, 200)
        # keygen caps client names at 20 chars -> the signed principal is "usr-" + 16 uuid chars.
        self.assertEqual(
            base64.urlsafe_b64decode(opts.json()["user"]["id"] + "==").decode(),
            "usr-" + supa_uid[:16],
        )

    def test_devices_cannot_be_read_or_revoked_across_accounts(self):
        cred_id = self._register()
        other = generate_key(client_name="usr-usr-" + uuid.uuid4().hex[:12], quota="standard")
        listed = self.client.get(
            f"/api/auth/passkey/devices?user_id={self.owner}", headers=self._auth(other)
        )
        self.assertEqual(listed.status_code, 200)
        self.assertNotIn(cred_id, [d["credential_id"] for d in listed.json()["devices"]])
        revoke = self.client.delete(
            f"/api/auth/passkey/devices/{cred_id}?user_id={self.owner}", headers=self._auth(other)
        )
        self.assertEqual(revoke.status_code, 404)
        self.assertIsNotNone(get_user_passkey(cred_id))
        mine = self.client.delete(f"/api/auth/passkey/devices/{cred_id}", headers=self._auth())
        self.assertEqual(mine.status_code, 200)

    def test_devices_require_a_session(self):
        self.assertEqual(
            self.client.get(f"/api/auth/passkey/devices?user_id={self.owner}").status_code, 401
        )

    def test_invalid_credential_is_rejected_not_orphaned(self):
        resp = self.client.post(
            "/api/auth/passkey/register/options",
            json={"email": "x@y.z"},
            headers=self._auth("sk-supreme-forged.standard.abc-deadbeef"),
        )
        self.assertEqual(resp.status_code, 401)

    def test_guest_token_cannot_own_passkeys(self):
        guest = generate_key(client_name="guest", quota="guest", ttl_seconds=300)
        resp = self.client.get("/api/auth/passkey/devices", headers=self._auth(guest))
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()

"""
gateway/tests/test_passkey_hardening.py — WebAuthn ceremony checks, keygen sessions,
RS256 support and the durable (Supabase) passkey store.
"""
import base64
import hashlib
import json
import os
import struct
import unittest
import uuid
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from fastapi.testclient import TestClient

from gateway.service import passkey_store
from gateway.service.app import app
from gateway.service.keygen import generate_key, verify_key
from gateway.service.webauthn_codec import (
    WebAuthnFormatError,
    cbor_decode,
    cose_key_to_spki,
)

MASTER = "test-master-key-32-bytes-supersecret-token"
RP_ID = "studio.example"
ORIGIN = "https://studio.example"


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


# ── tiny CBOR encoder (test-side only) ───────────────────────────────────────

def _head(major: int, n: int) -> bytes:
    if n < 24:
        return bytes([(major << 5) | n])
    for info, size in ((24, 1), (25, 2), (26, 4), (27, 8)):
        if n < 1 << (8 * size):
            return bytes([(major << 5) | info]) + n.to_bytes(size, "big")
    raise ValueError(n)


def cbor(v) -> bytes:
    if isinstance(v, bool):
        return bytes([0xF5 if v else 0xF4])
    if isinstance(v, int):
        return _head(0, v) if v >= 0 else _head(1, -1 - v)
    if isinstance(v, bytes):
        return _head(2, len(v)) + v
    if isinstance(v, str):
        raw = v.encode()
        return _head(3, len(raw)) + raw
    if isinstance(v, dict):
        return _head(5, len(v)) + b"".join(cbor(k) + cbor(x) for k, x in v.items())
    raise TypeError(type(v))


class FakeAuthenticator:
    """A platform authenticator that produces real ES256 / RS256 signatures."""

    def __init__(self, alg: str = "ES256", rp_id: str = RP_ID, origin: str = ORIGIN):
        self.alg, self.rp_id, self.origin = alg, rp_id, origin
        self.cred_id = uuid.uuid4().bytes
        self.counter = 0
        if alg == "ES256":
            self.key = ec.generate_private_key(ec.SECP256R1())
            nums = self.key.public_key().public_numbers()
            self.cose = {1: 2, 3: -7, -1: 1, -2: nums.x.to_bytes(32, "big"), -3: nums.y.to_bytes(32, "big")}
        else:
            self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            nums = self.key.public_key().public_numbers()
            self.cose = {1: 3, 3: -257, -1: nums.n.to_bytes(256, "big"), -2: nums.e.to_bytes(3, "big")}

    def _auth_data(self, flags: int, attested: bool, rp_id: str | None = None) -> bytes:
        head = hashlib.sha256((rp_id or self.rp_id).encode()).digest() + bytes([flags]) + struct.pack(">I", self.counter)
        if not attested:
            return head
        return head + b"\x00" * 16 + len(self.cred_id).to_bytes(2, "big") + self.cred_id + cbor(self.cose)

    def attest(self, challenge: str, *, flags: int = 0x45, origin: str | None = None,
               ctype: str = "webauthn.create", rp_id: str | None = None) -> dict:
        client_data = json.dumps({"type": ctype, "challenge": challenge, "origin": origin or self.origin}).encode()
        att = cbor({"fmt": "none", "attStmt": {}, "authData": self._auth_data(flags, True, rp_id)})
        return {"clientDataJSON": b64u(client_data), "attestationObject": b64u(att), "device_name": f"Test {self.alg}"}

    def assert_(self, challenge: str, user_handle: str | None, *, flags: int = 0x05, bump: int = 1) -> dict:
        self.counter += bump
        client_data = json.dumps({"type": "webauthn.get", "challenge": challenge, "origin": self.origin}).encode()
        auth_data = self._auth_data(flags, False)
        signed = auth_data + hashlib.sha256(client_data).digest()
        if self.alg == "ES256":
            sig = self.key.sign(signed, ec.ECDSA(hashes.SHA256()))
        else:
            sig = self.key.sign(signed, padding.PKCS1v15(), hashes.SHA256())
        return {
            "id": b64u(self.cred_id), "rawId": b64u(self.cred_id),
            "response": {"clientDataJSON": b64u(client_data), "authenticatorData": b64u(auth_data),
                         "signature": b64u(sig), "userHandle": user_handle},
        }


class PasskeyCeremonyTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"SUPREMEAI_MASTER_KEY": MASTER, "ENV": "test"})
        env.start()
        self.addCleanup(env.stop)
        for var in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY"):
            os.environ.pop(var, None)
        self.client = TestClient(app)
        self.owner = "usr-" + uuid.uuid4().hex[:12]
        self.token = generate_key(client_name=f"usr-{self.owner}", quota="standard")

    def h(self, token=None, origin=ORIGIN):
        return {"Authorization": f"Bearer {token or self.token}", "Origin": origin}

    def register(self, authn: FakeAuthenticator, token=None, **kw):
        opts = self.client.post("/api/auth/passkey/register/options", json={"email": "o@x.io"}, headers=self.h(token))
        self.assertEqual(opts.status_code, 200, opts.text)
        return opts, self.client.post("/api/auth/passkey/register/verify",
                                      json=authn.attest(opts.json()["challenge"], **kw), headers=self.h(token))

    def login(self, authn: FakeAuthenticator, user_handle=None, **kw):
        opts = self.client.post("/api/auth/passkey/login/options", json={}, headers={"Origin": ORIGIN})
        self.assertEqual(opts.json()["rpId"], RP_ID)
        handle = user_handle if user_handle is not None else b64u(self.owner.encode())
        return self.client.post("/api/auth/passkey/login/verify",
                                json=authn.assert_(opts.json()["challenge"], handle, **kw), headers={"Origin": ORIGIN})

    def test_es256_register_then_login_issues_a_keygen_session_for_the_same_owner(self):
        authn = FakeAuthenticator("ES256")
        _, reg = self.register(authn)
        self.assertEqual(reg.status_code, 200, reg.text)
        res = self.login(authn)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual((body["user_id"], body["role"]), (self.owner, "user"))
        claims = verify_key(body["access_token"])
        self.assertEqual(claims["client"], f"usr-{self.owner}")
        self.assertIn("exp", claims)  # passkey sessions expire (12 h)
        listed = self.client.get("/api/auth/passkey/devices", headers=self.h(body["access_token"]))
        self.assertIn(b64u(authn.cred_id), [d["credential_id"] for d in listed.json()["devices"]])

    def test_rs256_windows_hello_keys_are_supported(self):
        authn = FakeAuthenticator("RS256")
        _, reg = self.register(authn)
        self.assertEqual(reg.status_code, 200, reg.text)
        self.assertEqual(self.login(authn).status_code, 200)

    def test_admin_passkey_logs_in_as_admin(self):
        admin = generate_key(client_name="studio-admin", quota="unlimited")
        authn = FakeAuthenticator()
        _, reg = self.register(authn, token=admin)
        self.assertEqual(reg.status_code, 200, reg.text)
        res = self.login(authn, user_handle=b64u(b"usr-admin-primary"))
        self.assertEqual(res.json()["role"], "admin")
        self.assertEqual(verify_key(res.json()["access_token"])["client"], "studio-admin")

    def test_registration_rejects_wrong_origin_rp_type_and_missing_uv(self):
        for kwargs, detail in (
            ({"origin": "https://evil.example"}, "origin"),
            ({"rp_id": "evil.example"}, "relying party"),
            ({"ctype": "webauthn.get"}, "ceremony type"),
            ({"flags": 0x41}, "verification"),  # UP + AT, no UV
        ):
            _, res = self.register(FakeAuthenticator(), **kwargs)
            self.assertEqual(res.status_code, 400, kwargs)
            self.assertIn(detail, res.json()["detail"].lower())

    def test_challenges_are_single_use(self):
        authn = FakeAuthenticator()
        opts = self.client.post("/api/auth/passkey/register/options", json={}, headers=self.h())
        payload = authn.attest(opts.json()["challenge"])
        self.assertEqual(self.client.post("/api/auth/passkey/register/verify", json=payload, headers=self.h()).status_code, 200)
        again = self.client.post("/api/auth/passkey/register/verify", json=payload, headers=self.h())
        self.assertEqual(again.status_code, 400)

    def test_exclude_credentials_lists_existing_passkeys(self):
        authn = FakeAuthenticator()
        self.register(authn)
        opts = self.client.post("/api/auth/passkey/register/options", json={}, headers=self.h())
        self.assertIn({"type": "public-key", "id": b64u(authn.cred_id)}, opts.json()["excludeCredentials"])

    def test_credential_id_cannot_be_rebound_to_another_account(self):
        authn = FakeAuthenticator()
        self.register(authn)
        thief = generate_key(client_name="usr-usr-" + uuid.uuid4().hex[:12], quota="standard")
        _, res = self.register(authn, token=thief)
        self.assertEqual(res.status_code, 409)

    def test_cloned_authenticator_counter_regression_is_blocked(self):
        authn = FakeAuthenticator()
        self.register(authn)
        self.assertEqual(self.login(authn, bump=5).status_code, 200)
        self.assertEqual(self.login(authn, bump=-2).status_code, 403)

    def test_user_handle_must_match_the_credential_owner(self):
        authn = FakeAuthenticator()
        self.register(authn)
        self.assertEqual(self.login(authn, user_handle=b64u(b"usr-someoneelse")).status_code, 401)

    def test_login_requires_user_verification_and_valid_signature(self):
        authn = FakeAuthenticator()
        self.register(authn)
        self.assertEqual(self.login(authn, flags=0x01).status_code, 400)
        opts = self.client.post("/api/auth/passkey/login/options", json={}, headers={"Origin": ORIGIN})
        payload = authn.assert_(opts.json()["challenge"], None)
        payload["response"]["signature"] = b64u(b"\x30\x06\x02\x01\x01\x02\x01\x01")
        res = self.client.post("/api/auth/passkey/login/verify", json=payload, headers={"Origin": ORIGIN})
        self.assertEqual(res.status_code, 401)


class FakePostgrest:
    """In-memory stand-in for PostgREST /rest/v1/user_passkeys (eq./is. filters)."""

    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.fail = False

    @staticmethod
    def _match(row, filters):
        for col, cond in filters.items():
            op, _, val = cond.partition(".")
            if op == "eq" and str(row.get(col)) != val:
                return False
            if op == "is" and row.get(col) is not {"true": True, "false": False}[val]:
                return False
        return True

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            return httpx.Response(500)
        assert request.headers["apikey"] == "service-key"
        assert urlsplit(str(request.url)).path == "/rest/v1/user_passkeys"
        q = {k: v[0] for k, v in parse_qs(urlsplit(str(request.url)).query).items()}
        select = q.pop("select", None)
        for key in ("order", "limit"):
            q.pop(key, None)
        hits = [r for r in self.rows.values() if self._match(r, q)]
        if request.method == "POST":
            row = json.loads(request.content)
            if row["credential_id"] in self.rows:
                return httpx.Response(409)
            self.rows[row["credential_id"]] = row
            return httpx.Response(201)
        if request.method == "PATCH":
            for r in hits:
                r.update(json.loads(request.content))
            if "return=minimal" in request.headers.get("prefer", ""):
                return httpx.Response(204)
        cols = select.split(",") if select else None
        out = [{c: r.get(c) for c in cols} if cols else r for r in hits]
        return httpx.Response(200, json=out)


class DurableStoreTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakePostgrest()
        env = patch.dict(os.environ, {"SUPABASE_URL": "https://proj.supabase.co",
                                      "SUPABASE_SERVICE_ROLE_KEY": "service-key",
                                      "SUPREMEAI_MASTER_KEY": MASTER, "ENV": "test"})
        env.start()
        self.addCleanup(env.stop)
        real_client = httpx.Client
        transport = httpx.MockTransport(self.fake.handler)
        client_patch = patch.object(passkey_store.httpx, "Client",
                                    lambda **kw: real_client(transport=transport, **kw))
        client_patch.start()
        self.addCleanup(client_patch.stop)

    def test_lifecycle_goes_to_supabase_not_the_temp_sqlite(self):
        self.assertTrue(passkey_store.is_durable())
        passkey_store.save_user_passkey("cred-1", "usr-aaaaaaaaaaaa", "user", "spki", "Hello", 0)
        self.assertIn("cred-1", self.fake.rows)
        self.assertEqual(passkey_store.get_user_passkey("cred-1")["device_name"], "Hello")
        self.assertEqual([d["credential_id"] for d in passkey_store.list_user_passkeys("usr-aaaaaaaaaaaa")], ["cred-1"])
        passkey_store.update_passkey_usage("cred-1", 7)
        self.assertEqual(self.fake.rows["cred-1"]["counter"], 7)
        self.assertFalse(passkey_store.revoke_user_passkey("cred-1", "usr-bbbbbbbbbbbb"))
        self.assertTrue(passkey_store.revoke_user_passkey("cred-1", "usr-aaaaaaaaaaaa"))
        self.assertIsNone(passkey_store.get_user_passkey("cred-1"))

    def test_existing_credential_of_another_account_is_a_conflict(self):
        passkey_store.save_user_passkey("cred-2", "usr-aaaaaaaaaaaa", "user", "spki", "A", 0)
        with self.assertRaises(passkey_store.PasskeyConflict):
            passkey_store.save_user_passkey("cred-2", "usr-bbbbbbbbbbbb", "user", "spki2", "B", 0)
        self.assertEqual(self.fake.rows["cred-2"]["public_key_spki"], "spki")

    def test_store_outage_is_a_503_not_an_empty_list(self):
        self.fake.fail = True
        token = generate_key(client_name="usr-usr-" + uuid.uuid4().hex[:12], quota="standard")
        res = TestClient(app).get("/api/auth/passkey/devices", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 503)


class CodecTests(unittest.TestCase):
    def test_rejects_indefinite_lengths_tags_and_truncation(self):
        for bad in (b"\x5f", b"\xc0\x01", b"\x58\x05ab", b""):
            with self.assertRaises(WebAuthnFormatError):
                cbor_decode(bad)

    def test_unsupported_cose_keys_are_rejected(self):
        with self.assertRaises(WebAuthnFormatError):
            cose_key_to_spki({1: 1, 3: -8})  # OKP / EdDSA
        with self.assertRaises(WebAuthnFormatError):
            cose_key_to_spki({1: 2, 3: -7, -1: 1, -2: b"\x01" * 32, -3: b"\x02" * 32})  # not on curve


if __name__ == "__main__":
    unittest.main()

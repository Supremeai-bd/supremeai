"""
gateway/service/passkey_auth.py — Native WebAuthn (Passkey / Fingerprint / Face ID) Engine.

Passwordless biometric login and multi-device passkeys for registered accounts.
- No WebAuthn library: strict CBOR/COSE parsing lives in ``webauthn_codec`` and
  signatures are verified with ``cryptography`` (ES256 and RS256).
- Credentials persist in Supabase via ``passkey_store`` (survives redeploys);
  the local SQLite store is only used when Supabase is not configured.
- Every ceremony checks: challenge (single use, 5 min), clientData type, origin,
  rpIdHash, user-present + user-verified flags, and (login) the signature and the
  monotonic sign counter.
- Passkey login returns the same keygen ``sk-supreme-…`` session the password
  login issues (with a 12 h / 24 h expiry), so every gateway route accepts it.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

try:
    from gateway.service import passkey_store
    from gateway.service.auth_identity import extract_token
    from gateway.service.keygen import generate_key, verify_key
    from gateway.service.webauthn_codec import (
        AuthenticatorData,
        WebAuthnFormatError,
        cose_key_to_spki,
        parse_attestation_object,
        parse_authenticator_data,
    )
except ImportError:  # pragma: no cover - flat deploy layout
    from service import passkey_store  # type: ignore[no-redef]
    from service.auth_identity import extract_token  # type: ignore[no-redef]
    from service.keygen import generate_key, verify_key  # type: ignore[no-redef]
    from service.webauthn_codec import (  # type: ignore[no-redef]
        AuthenticatorData,
        WebAuthnFormatError,
        cose_key_to_spki,
        parse_attestation_object,
        parse_authenticator_data,
    )

logger = logging.getLogger("supremeai.passkey_auth")

# Registered-account principals minted by the gateway login routes:
#   studio-admin                 -> usr-admin-primary
#   usr-usr-<12 hex>             -> usr-<12 hex>          (gateway users table)
#   usr-<uuid prefix>            -> usr-<uuid prefix>     (Supabase GoTrue fallback;
#                                   keygen caps client names at 20 chars, so the
#                                   signed principal is the first 16 uuid chars)
_GATEWAY_USER_RE = re.compile(r"usr-(usr-[a-f0-9]{12})")
_SUPABASE_USER_RE = re.compile(r"(usr-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{2})")
_GATEWAY_OWNER_RE = re.compile(r"usr-[a-f0-9]{12}")
ADMIN_OWNER = "usr-admin-primary"

router = APIRouter(prefix="/api/auth/passkey", tags=["passkey-auth"])

CHALLENGE_TTL_SECONDS = 300.0
USER_SESSION_TTL_SECONDS = 12 * 3600
ADMIN_SESSION_TTL_SECONDS = 24 * 3600


@dataclass(frozen=True)
class _Challenge:
    user_id: str
    expires_at: float
    ceremony: str  # "register" | "login"
    rp_id: str
    origin: str  # Origin header of the options request ("" when absent)


# Single-use challenges (5-minute TTL). In-memory is fine: a ceremony takes seconds,
# and a redeploy only cancels ceremonies that are in flight at that moment.
_challenges: Dict[str, _Challenge] = {}


def _clean_expired_challenges() -> None:
    now = time.time()
    for key in [k for k, c in _challenges.items() if c.expires_at < now]:
        _challenges.pop(key, None)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding and padding < 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("utf-8"))


# ── Identity ─────────────────────────────────────────────────────────────────

def _owner_from_keygen_token(token: str) -> Optional[str]:
    """Map a keygen-signed session token to its stable registered user id."""
    try:
        claims = verify_key(token) or {}
    except Exception:  # noqa: BLE001 - malformed credential == no principal
        return None
    client = str(claims.get("client") or "").strip()
    if client == "studio-admin":
        return ADMIN_OWNER
    for pattern in (_GATEWAY_USER_RE, _SUPABASE_USER_RE):
        match = pattern.fullmatch(client)
        if match:
            return match[1]
    return None


def _resolve_passkey_owner(request: Request) -> Optional[str]:
    """Server-verified owner of passkeys for this request (None = no credential).

    A presented-but-invalid (or guest) credential is a 401, never an orphan account.
    """
    token = extract_token(request)
    if not token:
        return None
    owner = _owner_from_keygen_token(token)
    if not owner:
        raise HTTPException(status_code=401, detail="Sign in with a registered account to manage passkeys.")
    return owner


def _require_passkey_owner(request: Request) -> str:
    owner = _resolve_passkey_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Sign in with a registered account to manage passkeys.")
    return owner


def _mint_passkey_session(owner: str) -> Tuple[str, str]:
    """Issue the same keygen session the password login issues (inverse of the owner map)."""
    if owner == ADMIN_OWNER:
        client, quota, role, ttl = "studio-admin", "unlimited", "admin", ADMIN_SESSION_TTL_SECONDS
    elif _SUPABASE_USER_RE.fullmatch(owner):
        client, quota, role, ttl = owner, "standard", "user", USER_SESSION_TTL_SECONDS
    elif _GATEWAY_OWNER_RE.fullmatch(owner):
        client, quota, role, ttl = f"usr-{owner}", "standard", "user", USER_SESSION_TTL_SECONDS
    else:
        raise HTTPException(status_code=401, detail="This passkey is not linked to a registered account.")
    try:
        return generate_key(client_name=client, quota=quota, ttl_seconds=ttl), role
    except RuntimeError:
        # keygen fails closed without a signing secret: an error, never a session.
        raise HTTPException(status_code=503, detail="Sign-in is temporarily unavailable.") from None


# ── Ceremony checks ──────────────────────────────────────────────────────────

def _relying_party(request: Request) -> Tuple[str, str]:
    """(rp_id, origin) for this request. The browser's Origin header is authoritative."""
    origin = (request.headers.get("origin") or "").strip()
    host = urlparse(origin).hostname if origin else None
    rp_id = (host or request.headers.get("host", "localhost").split(":")[0] or "localhost").lower()
    if rp_id in ("localhost", "127.0.0.1"):
        rp_id = "localhost"
    return rp_id, origin


def _issue_challenge(user_id: str, ceremony: str, request: Request) -> Tuple[str, str]:
    _clean_expired_challenges()
    rp_id, origin = _relying_party(request)
    challenge_b64 = _b64url_encode(secrets.token_bytes(32))
    _challenges[challenge_b64] = _Challenge(user_id, time.time() + CHALLENGE_TTL_SECONDS, ceremony, rp_id, origin)
    return challenge_b64, rp_id


def _consume_challenge(client_data_b64: str, ceremony: str) -> Tuple[_Challenge, bytes]:
    """Validates clientDataJSON and pops its (single-use) challenge."""
    _clean_expired_challenges()
    try:
        raw = _b64url_decode(client_data_b64)
        client_data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Malformed clientDataJSON") from None
    if not isinstance(client_data, dict):
        raise HTTPException(status_code=400, detail="Malformed clientDataJSON")
    challenge_b64 = client_data.get("challenge")
    challenge = _challenges.pop(challenge_b64, None) if isinstance(challenge_b64, str) else None
    if challenge is None:
        raise HTTPException(status_code=400, detail="Invalid or expired passkey challenge")
    if challenge.ceremony != ceremony:
        raise HTTPException(status_code=400, detail="Challenge ceremony mismatch")
    expected_type = "webauthn.create" if ceremony == "register" else "webauthn.get"
    if client_data.get("type") != expected_type:
        raise HTTPException(status_code=400, detail="Unexpected WebAuthn ceremony type")
    origin = str(client_data.get("origin") or "")
    if challenge.origin:
        origin_ok = origin == challenge.origin
    else:  # non-browser caller: the origin must at least live under the RP id
        host = (urlparse(origin).hostname or "").lower()
        origin_ok = bool(host) and (host == challenge.rp_id or host.endswith("." + challenge.rp_id))
    if not origin_ok:
        raise HTTPException(status_code=400, detail="Passkey origin mismatch")
    return challenge, raw


def _check_authenticator_data(auth: AuthenticatorData, rp_id: str) -> None:
    if not secrets.compare_digest(auth.rp_id_hash, hashlib.sha256(rp_id.encode("utf-8")).digest()):
        raise HTTPException(status_code=400, detail="Passkey relying party mismatch")
    if not (auth.user_present and auth.user_verified):
        raise HTTPException(status_code=400, detail="Biometric / PIN verification is required")


def _verify_webauthn_signature(
    public_key_spki_b64: str,
    authenticator_data_bytes: bytes,
    client_data_hash: bytes,
    signature_bytes: bytes,
) -> bool:
    """Verifies an ES256 / RS256 WebAuthn assertion signature."""
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
        from cryptography.hazmat.primitives.serialization import load_der_public_key

        pub_key = load_der_public_key(_b64url_decode(public_key_spki_b64))
        signed_data = authenticator_data_bytes + client_data_hash
        if isinstance(pub_key, ec.EllipticCurvePublicKey):
            pub_key.verify(signature_bytes, signed_data, ec.ECDSA(hashes.SHA256()))
            return True
        if isinstance(pub_key, rsa.RSAPublicKey):
            pub_key.verify(signature_bytes, signed_data, padding.PKCS1v15(), hashes.SHA256())
            return True
        return False
    except Exception as exc:  # noqa: BLE001 - any failure == invalid signature
        logger.warning("Passkey signature verification failed: %s", type(exc).__name__)
        return False


def _store(fn, *args, **kwargs):
    """Runs a passkey_store call, mapping storage failures to HTTP errors."""
    try:
        return fn(*args, **kwargs)
    except passkey_store.PasskeyConflict:
        raise HTTPException(status_code=409, detail="This passkey is already registered to another account.") from None
    except passkey_store.PasskeyStoreUnavailable:
        raise HTTPException(status_code=503, detail="Passkey storage is temporarily unavailable. Please retry.") from None


# ── Pydantic Request Models ──────────────────────────────────────────────────

class RegisterOptionsRequest(BaseModel):
    user_id: Optional[str] = None  # ignored (untrusted); kept for older clients
    email: Optional[str] = None
    role: Optional[str] = "user"  # ignored (untrusted); kept for older clients
    display_name: Optional[str] = None


class RegisterVerifyRequest(BaseModel):
    clientDataJSON: str
    attestationObject: str
    device_name: Optional[str] = "Personal Biometric Device"


class LoginOptionsRequest(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None


class LoginVerifyRequest(BaseModel):
    id: str  # credential_id base64url
    rawId: str
    response: Dict[str, Any]  # clientDataJSON, authenticatorData, signature, userHandle


# ── Registration Endpoints ───────────────────────────────────────────────────

@router.post("/register/options")
async def get_register_options(req: RegisterOptionsRequest, request: Request):
    """WebAuthn registration options for the signed-in account.

    Client-supplied ``user_id`` / ``role`` are never trusted (passkey squatting /
    privilege escalation). A session is required: anonymous registrations used to
    mint throwaway ``usr-<random>`` principals that no account owned.
    """
    if req.user_id:
        logger.warning("Ignoring client-supplied user_id in passkey registration (untrusted)")
    if req.role and req.role != "user":
        logger.warning("Ignoring client-supplied role in passkey registration (untrusted)")
    owner = _resolve_passkey_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Sign in first to add a passkey.")

    display_email = (req.email or "").strip()
    email = display_email if "@" in display_email and len(display_email) <= 160 else f"{owner}@supremeai.local"
    existing: List[Dict[str, Any]] = _store(passkey_store.list_user_passkeys, owner)
    challenge_b64, rp_id = _issue_challenge(owner, "register", request)

    return {
        "challenge": challenge_b64,
        "rp": {"name": "SupremeAI Security Platform", "id": rp_id},
        "user": {
            "id": _b64url_encode(owner.encode("utf-8")),
            "name": email,
            "displayName": (req.display_name or email.split("@")[0])[:64],
        },
        "pubKeyCredParams": [
            {"type": "public-key", "alg": -7},  # ES256
            {"type": "public-key", "alg": -257},  # RS256 (Windows Hello TPM keys)
        ],
        # Stops the same authenticator being registered twice for this account.
        "excludeCredentials": [
            {"type": "public-key", "id": d["credential_id"]} for d in existing if d.get("credential_id")
        ],
        "authenticatorSelection": {
            "authenticatorAttachment": "platform",  # Built-in Fingerprint / Touch ID / Face ID
            "userVerification": "required",
            "residentKey": "preferred",
        },
        "timeout": 60000,
        "attestation": "none",
    }


@router.post("/register/verify")
async def verify_registration(req: RegisterVerifyRequest, request: Request):
    """Validates the attestation response and persists the new passkey."""
    challenge, _ = _consume_challenge(req.clientDataJSON, "register")
    # The finishing request must come from the same account that started it.
    caller = _resolve_passkey_owner(request)
    if caller and caller != challenge.user_id:
        raise HTTPException(status_code=403, detail="Passkey ceremony belongs to another account")

    try:
        auth = parse_authenticator_data(parse_attestation_object(_b64url_decode(req.attestationObject)))
        if auth.credential_id is None or auth.cose_key is None:
            raise WebAuthnFormatError("attestation has no credential")
        spki = cose_key_to_spki(auth.cose_key)
    except (WebAuthnFormatError, ValueError) as exc:
        logger.info("Rejected passkey attestation: %s", exc)
        raise HTTPException(status_code=400, detail="Could not parse authenticator attestation") from None
    _check_authenticator_data(auth, challenge.rp_id)

    device_name = (req.device_name or "Biometric Device").strip()[:160] or "Biometric Device"
    passkey = _store(
        passkey_store.save_user_passkey,
        credential_id=_b64url_encode(auth.credential_id),
        user_id=challenge.user_id,
        role="admin" if challenge.user_id == ADMIN_OWNER else "user",
        public_key_spki=_b64url_encode(spki),
        device_name=device_name,
        counter=auth.sign_count,
    )
    logger.info("Registered passkey '%s' for %s", device_name, challenge.user_id)
    return {
        "status": "success",
        "message": f"Passkey registered successfully for {device_name}",
        "passkey": passkey,
    }


# ── Authentication Endpoints ─────────────────────────────────────────────────

@router.post("/login/options")
async def get_login_options(req: LoginOptionsRequest, request: Request):
    """WebAuthn authentication options (discoverable credentials, biometric required)."""
    challenge_b64, rp_id = _issue_challenge("", "login", request)
    return {
        "challenge": challenge_b64,
        "timeout": 60000,
        "rpId": rp_id,
        "userVerification": "required",
    }


@router.post("/login/verify")
async def verify_login(req: LoginVerifyRequest, request: Request, response: Response):
    """Verifies the biometric assertion and returns a gateway session."""
    challenge, client_data_raw = _consume_challenge(str(req.response.get("clientDataJSON", "")), "login")

    passkey = _store(passkey_store.get_user_passkey, req.id)
    if not passkey:
        raise HTTPException(status_code=401, detail="Passkey not recognized or has been revoked")

    user_handle = req.response.get("userHandle")
    if user_handle:
        try:
            handle_owner = _b64url_decode(str(user_handle)).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            handle_owner = ""
        if handle_owner != passkey["user_id"]:
            raise HTTPException(status_code=401, detail="Passkey does not match this account")

    try:
        auth_data = _b64url_decode(str(req.response.get("authenticatorData", "")))
        signature = _b64url_decode(str(req.response.get("signature", "")))
        auth = parse_authenticator_data(auth_data)
    except (WebAuthnFormatError, ValueError):
        raise HTTPException(status_code=400, detail="Malformed authenticator assertion") from None
    _check_authenticator_data(auth, challenge.rp_id)

    if not _verify_webauthn_signature(
        public_key_spki_b64=passkey["public_key_spki"],
        authenticator_data_bytes=auth_data,
        client_data_hash=hashlib.sha256(client_data_raw).digest(),
        signature_bytes=signature,
    ):
        raise HTTPException(status_code=401, detail="Biometric signature verification failed")

    # Monotonic sign counter (0 = authenticator does not count, e.g. synced passkeys).
    stored_counter = int(passkey.get("counter") or 0)
    if auth.sign_count > 0 and auth.sign_count <= stored_counter:
        logger.warning("Passkey sign counter regressed for credential %s…", req.id[:12])
        raise HTTPException(status_code=403, detail="Potential cloned authenticator detected")
    _store(passkey_store.update_passkey_usage, req.id, auth.sign_count)

    owner = passkey["user_id"]
    token, role = _mint_passkey_session(owner)
    response.set_cookie(
        key="supreme_access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("ENV", "production") != "test",
        max_age=ADMIN_SESSION_TTL_SECONDS if role == "admin" else USER_SESSION_TTL_SECONDS,
    )
    logger.info("Passkey login: %s (%s) via %s", owner, role, passkey.get("device_name"))
    return {
        "status": "success",
        "access_token": token,
        "token": token,
        "token_type": "bearer",
        "user_id": owner,
        "role": role,
        "device_name": passkey.get("device_name"),
    }


# ── Device Management Endpoints ──────────────────────────────────────────────

@router.get("/devices")
async def list_devices(request: Request, user_id: Optional[str] = None):
    """Lists the caller's passkeys. The legacy ``user_id`` query parameter is ignored."""
    owner = _require_passkey_owner(request)
    return {"devices": _store(passkey_store.list_user_passkeys, owner)}


@router.delete("/devices/{credential_id}")
async def revoke_device(credential_id: str, request: Request, user_id: Optional[str] = None):
    """Revokes one of the caller's passkeys (404 for anyone else's)."""
    owner = _require_passkey_owner(request)
    if not _store(passkey_store.revoke_user_passkey, credential_id, owner):
        raise HTTPException(status_code=404, detail="Device not found or unauthorized")
    return {"status": "success", "message": "Passkey revoked successfully"}

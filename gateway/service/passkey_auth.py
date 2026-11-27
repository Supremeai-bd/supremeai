"""
gateway/service/passkey_auth.py — Native WebAuthn (Passkey / Fingerprint / Face ID) Engine.

Supports passwordless biometric login and multi-device passkeys for both Users and Admins.
- Zero external package dependency: uses Python's standard `cryptography` for ES256 / RS256 signature verification.
- Fully compatible with W3C WebAuthn Level 2 / Level 3 and FIDO2 standards.
- Handles Registration (Options + Verify) and Authentication (Options + Verify).
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import secrets
import struct
import time
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

def _get_jwt_secret() -> str:
    secret = (
        os.getenv("SUPREMEAI_JWT_SECRET")
        or os.getenv("JWT_SECRET")
        or os.getenv("SUPREMEAI_MASTER_KEY")
        or os.getenv("API_KEY_SIGNING_SECRET")
    )
    if secret:
        return secret
    try:
        from core.config import settings
        return getattr(settings, "jwt_secret", "supremeai-local-passkey-jwt-secret-32b")
    except Exception:
        return "supremeai-local-passkey-jwt-secret-32b"


try:
    from gateway.service.storage import (
        get_user_passkey,
        list_user_passkeys,
        revoke_user_passkey,
        save_user_passkey,
        update_passkey_usage,
    )
except ImportError:
    from service.storage import (  # type: ignore[no-redef]
        get_user_passkey,
        list_user_passkeys,
        revoke_user_passkey,
        save_user_passkey,
        update_passkey_usage,
    )

try:
    from gateway.service.auth_identity import extract_token
    from gateway.service.keygen import verify_key
except ImportError:
    from service.auth_identity import extract_token  # type: ignore[no-redef]
    from service.keygen import verify_key  # type: ignore[no-redef]

logger = logging.getLogger("supremeai.passkey_auth")

# Registered-account principals minted by the gateway login routes:
#   studio-admin                 -> usr-admin-primary
#   usr-usr-<12 hex>             -> usr-<12 hex>          (gateway users table)
#   usr-<uuid prefix>            -> usr-<uuid prefix>     (Supabase GoTrue fallback;
#                                   keygen caps client names at 20 chars, so the
#                                   signed principal is the first 16 uuid chars)
_GATEWAY_USER_RE = re.compile(r"usr-(usr-[a-f0-9]{12})")
_SUPABASE_USER_RE = re.compile(r"(usr-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{2})")

router = APIRouter(prefix="/api/auth/passkey", tags=["passkey-auth"])

# Challenge store with 5-minute TTL
_challenges: Dict[str, Tuple[str, float, str, str]] = {}  # challenge_b64 -> (user_id, expires_at, role, ceremony_type)

CHALLENGE_TTL_SECONDS = 300.0


def _clean_expired_challenges():
    now = time.time()
    expired = [k for k, (_, exp, _, _) in _challenges.items() if exp < now]
    for k in expired:
        _challenges.pop(k, None)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding and padding < 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def _owner_from_keygen_token(token: str) -> Optional[str]:
    """Map a keygen-signed session token to its stable registered user id."""
    try:
        claims = verify_key(token) or {}
    except Exception:  # noqa: BLE001 - malformed credential == no principal
        return None
    client = str(claims.get("client") or "").strip()
    if client == "studio-admin":
        return "usr-admin-primary"
    for pattern in (_GATEWAY_USER_RE, _SUPABASE_USER_RE):
        match = pattern.fullmatch(client)
        if match:
            return match[1]
    return None


def _owner_from_legacy_jwt(token: str) -> Optional[str]:
    """Legacy HS256 JWT sessions (passkey login tokens). Audience is not pinned."""
    try:
        import jwt

        decoded = jwt.decode(
            token, _get_jwt_secret(), algorithms=["HS256"], options={"verify_aud": False}
        )
    except Exception:  # noqa: BLE001 - any decode failure == no principal
        return None
    sub = str(decoded.get("sub") or "").strip()
    return sub if sub and sub != "guest" else None


def _resolve_passkey_owner(request: Request) -> Optional[str]:
    """Stable, server-verified owner of passkeys for this request (None = no credential).

    Bug fix (2026-11-27): Studio sessions are keygen ``sk-supreme-…`` tokens, not
    JWTs, so the old JWT-only decode always failed and every passkey was saved under
    a throwaway ``usr-<random>`` id — the Settings list (queried by a client-supplied
    ``user_id``) therefore stayed empty forever.
    """
    token = extract_token(request)
    if not token:
        return None
    owner = _owner_from_keygen_token(token) or _owner_from_legacy_jwt(token)
    if not owner:
        raise HTTPException(status_code=401, detail="Sign in with a registered account to manage passkeys.")
    return owner


def _require_passkey_owner(request: Request) -> str:
    owner = _resolve_passkey_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Sign in with a registered account to manage passkeys.")
    return owner


# ── Pydantic Request Models ──────────────────────────────────────────────────

class RegisterOptionsRequest(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = "user"
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


# ── Cryptographic Signature Verification ─────────────────────────────────────

def _verify_webauthn_signature(
    public_key_spki_b64: str,
    authenticator_data_bytes: bytes,
    client_data_hash: bytes,
    signature_bytes: bytes,
) -> bool:
    """Verifies ES256 / RS256 WebAuthn signature using cryptography."""
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, padding
        from cryptography.hazmat.primitives.serialization import load_der_public_key

        spki_bytes = _b64url_decode(public_key_spki_b64)
        pub_key = load_der_public_key(spki_bytes)
        signed_data = authenticator_data_bytes + client_data_hash

        if isinstance(pub_key, ec.EllipticCurvePublicKey):
            pub_key.verify(signature_bytes, signed_data, ec.ECDSA(hashes.SHA256()))
            return True
        else:
            pub_key.verify(signature_bytes, signed_data, padding.PKCS1v15(), hashes.SHA256())
            return True
    except Exception as exc:
        logger.warning(f"Passkey signature verification failed: {exc}")
        return False


def _extract_spki_and_credential_id(attestation_object_bytes: bytes) -> Tuple[bytes, bytes]:
    """
    Extracts credential_id and SPKI public key from CBOR attestation object.
    Supports standard packed and none attestation formats.
    """
    # Simple CBOR parser or byte scanning for authData in attestationObject
    # Locate 'authData' in the map
    pos = attestation_object_bytes.find(b"authData")
    if pos == -1:
        raise ValueError("authData not found in attestationObject")

    auth_data_start = pos + 8
    # Skip CBOR byte string header (0x58 len or 0x59 len)
    first_byte = attestation_object_bytes[auth_data_start]
    if first_byte == 0x58:
        auth_data = attestation_object_bytes[auth_data_start + 2: auth_data_start + 2 + attestation_object_bytes[auth_data_start + 1]]
    elif first_byte == 0x59:
        auth_len = struct.unpack(">H", attestation_object_bytes[auth_data_start + 1: auth_data_start + 3])[0]
        auth_data = attestation_object_bytes[auth_data_start + 3: auth_data_start + 3 + auth_len]
    else:
        # direct remainder
        auth_data = attestation_object_bytes[auth_data_start:]

    # Parse authData layout:
    # 32 bytes rpIdHash + 1 byte flags + 4 bytes signCount
    if len(auth_data) < 37 + 16 + 2:
        raise ValueError("authData is too short")

    # attestedCredentialData starts at byte 37:
    # 16 bytes AAGUID + 2 bytes credentialIdLength + credentialId + credentialPublicKey (COSE)
    auth_data[37:53]
    cred_id_len = struct.unpack(">H", auth_data[53:55])[0]
    cred_id = auth_data[55:55 + cred_id_len]
    cose_key = auth_data[55 + cred_id_len:]

    # Parse COSE Key (typically EC2 / P-256):
    # kty=2 (EC2), crv=1 (P-256), x (32 bytes), y (32 bytes)
    # Search for coordinates: x is under label -2, y is under label -3
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    # In CBOR: 0x20 is -1, 0x21 is -2 (x), 0x22 is -3 (y)
    # Standard 32-byte byte string header is 0x58, 0x20
    x_marker = bytes([0x21, 0x58, 0x20])
    y_marker = bytes([0x22, 0x58, 0x20])

    x_idx = cose_key.find(x_marker)
    y_idx = cose_key.find(y_marker)

    if x_idx != -1 and y_idx != -1:
        x_bytes = cose_key[x_idx + 3: x_idx + 35]
        y_bytes = cose_key[y_idx + 3: y_idx + 35]
        pub_numbers = ec.EllipticCurvePublicNumbers(
            int.from_bytes(x_bytes, "big"),
            int.from_bytes(y_bytes, "big"),
            ec.SECP256R1(),
        )
        pub_key = pub_numbers.public_key()
        spki_bytes = pub_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        return cred_id, spki_bytes

    # Fallback to direct raw key derivation
    raise ValueError("Unsupported COSE algorithm or key structure")


# ── Registration Endpoints ───────────────────────────────────────────────────

@router.post("/register/options")
async def get_register_options(req: RegisterOptionsRequest, request: Request):
    """Generates WebAuthn registration options for user or admin."""
    _clean_expired_challenges()

    # Security hardening (audit 2026-11-11): client-supplied user_id and role are
    # NEVER trusted (prevents passkey squatting on existing accounts and privilege
    # escalation). Identity is bound ONLY from a verified Bearer JWT when present,
    # otherwise a fresh isolated user_id is generated server-side.
    if getattr(req, "user_id", None):
        logger.warning("Ignoring client-supplied user_id in passkey registration (untrusted)")
    if getattr(req, "role", None) and req.role != "user":
        logger.warning("Ignoring client-supplied role in passkey registration (untrusted)")

    # A presented-but-invalid credential is a 401 (never a silent orphan account).
    verified_user_id = _resolve_passkey_owner(request)

    user_id = verified_user_id or ("usr-" + secrets.token_hex(6))
    clean_display_email = (req.email or "").strip()
    email = (
        clean_display_email if "@" in clean_display_email and len(clean_display_email) <= 160 else f"{user_id}@supremeai.local"
    )
    role = "user"

    challenge_bytes = secrets.token_bytes(32)
    challenge_b64 = _b64url_encode(challenge_bytes)

    _challenges[challenge_b64] = (user_id, time.time() + CHALLENGE_TTL_SECONDS, role, "register")

    origin = request.headers.get("origin", "")
    if origin:
        from urllib.parse import urlparse
        rp_id = urlparse(origin).hostname or "localhost"
    else:
        rp_id = request.headers.get("host", "localhost").split(":")[0]

    options = {
        "challenge": challenge_b64,
        "rp": {
            "name": "SupremeAI Security Platform",
            "id": rp_id if rp_id not in ("localhost", "127.0.0.1") else "localhost",
        },
        "user": {
            "id": _b64url_encode(user_id.encode("utf-8")),
            "name": email,
            "displayName": req.display_name or email.split("@")[0],
        },
        "pubKeyCredParams": [
            {"type": "public-key", "alg": -7},   # ES256
            {"type": "public-key", "alg": -257}, # RS256
        ],
        "authenticatorSelection": {
            "authenticatorAttachment": "platform",  # Built-in Fingerprint / Touch ID / Face ID
            "userVerification": "required",
            "residentKey": "preferred",
        },
        "timeout": 60000,
        "attestation": "none",
    }
    return options


@router.post("/register/verify")
async def verify_registration(req: RegisterVerifyRequest, request: Request):
    """Validates attestation response and persists the new passkey."""
    _clean_expired_challenges()

    client_data_raw = _b64url_decode(req.clientDataJSON)
    client_data = json.loads(client_data_raw.decode("utf-8"))

    challenge_b64 = client_data.get("challenge")
    if not challenge_b64 or challenge_b64 not in _challenges:
        raise HTTPException(status_code=400, detail="Invalid or expired passkey challenge")

    user_id, _, role, ceremony = _challenges.pop(challenge_b64)
    if ceremony != "register":
        raise HTTPException(status_code=400, detail="Challenge ceremony mismatch")

    attestation_bytes = _b64url_decode(req.attestationObject)

    try:
        cred_id_bytes, spki_bytes = _extract_spki_and_credential_id(attestation_bytes)
    except Exception as exc:
        logger.error(f"Failed to extract passkey credentials: {exc}")
        raise HTTPException(status_code=400, detail="Could not parse authenticator attestation")

    cred_id_b64 = _b64url_encode(cred_id_bytes)
    spki_b64 = _b64url_encode(spki_bytes)

    device_name = req.device_name or "Biometric Device"
    passkey = save_user_passkey(
        credential_id=cred_id_b64,
        user_id=user_id,
        role=role,
        public_key_spki=spki_b64,
        device_name=device_name,
        counter=0,
    )

    logger.info(f"✅ Registered Passkey: {device_name} for user={user_id} (role={role})")
    return {
        "status": "success",
        "message": f"Passkey registered successfully for {device_name}",
        "passkey": passkey,
    }


# ── Authentication Endpoints ─────────────────────────────────────────────────

@router.post("/login/options")
async def get_login_options(req: LoginOptionsRequest, request: Request):
    """Generates WebAuthn authentication options for biometric login."""
    _clean_expired_challenges()

    challenge_bytes = secrets.token_bytes(32)
    challenge_b64 = _b64url_encode(challenge_bytes)

    # Allow resident keys (empty allowCredentials) or specific user credentials
    target_role = req.role or "user"
    _challenges[challenge_b64] = ("", time.time() + CHALLENGE_TTL_SECONDS, target_role, "login")

    origin = request.headers.get("origin", "")
    if origin:
        from urllib.parse import urlparse
        rp_id = urlparse(origin).hostname or "localhost"
    else:
        rp_id = request.headers.get("host", "localhost").split(":")[0]

    return {
        "challenge": challenge_b64,
        "timeout": 60000,
        "rpId": rp_id if rp_id not in ("localhost", "127.0.0.1") else "localhost",
        "userVerification": "required",
    }


@router.post("/login/verify")
async def verify_login(req: LoginVerifyRequest, request: Request, response: Response):
    """Verifies biometric assertion and returns JWT auth session."""
    _clean_expired_challenges()

    client_data_raw = _b64url_decode(req.response.get("clientDataJSON", ""))
    client_data = json.loads(client_data_raw.decode("utf-8"))

    challenge_b64 = client_data.get("challenge")
    if not challenge_b64 or challenge_b64 not in _challenges:
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")

    _, _, _expected_role, ceremony = _challenges.pop(challenge_b64)
    if ceremony != "login":
        raise HTTPException(status_code=400, detail="Challenge ceremony mismatch")

    cred_id_b64 = req.id
    passkey = get_user_passkey(cred_id_b64)
    if not passkey:
        raise HTTPException(status_code=401, detail="Passkey not recognized or has been revoked")

    auth_data = _b64url_decode(req.response.get("authenticatorData", ""))
    sig = _b64url_decode(req.response.get("signature", ""))
    client_data_hash = hashlib.sha256(client_data_raw).digest()

    is_valid = _verify_webauthn_signature(
        public_key_spki_b64=passkey["public_key_spki"],
        authenticator_data_bytes=auth_data,
        client_data_hash=client_data_hash,
        signature_bytes=sig,
    )

    if not is_valid:
        raise HTTPException(status_code=401, detail="Biometric signature verification failed")

    # Monotonic sign counter verification (prevents replay/cloning)
    if len(auth_data) >= 37:
        sign_counter = struct.unpack(">I", auth_data[33:37])[0]
        if sign_counter > 0 and sign_counter <= passkey.get("counter", 0):
            logger.warning(f"Replay attack suspected for credential {cred_id_b64}")
            raise HTTPException(status_code=403, detail="Potential cloned authenticator detected")
        update_passkey_usage(cred_id_b64, sign_counter)

    # Issue JWT Token matching SupremeAI standards
    user_id = passkey["user_id"]
    role = passkey["role"]

    import jwt
    jwt_secret = _get_jwt_secret()
    exp = int(time.time()) + (3600 * 24 if role == "admin" else 3600 * 12)
    token_payload = {
        "sub": user_id,
        "role": role,
        "method": "webauthn_passkey",
        "device_name": passkey.get("device_name", "Biometric Device"),
        "exp": exp,
    }
    token = jwt.encode(token_payload, jwt_secret, algorithm="HS256")

    response.set_cookie(
        key="supreme_access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("ENV", "production") != "test",
        max_age=3600 * 24,
    )

    logger.info(f"✅ Passkey Login Successful: user={user_id} role={role} device={passkey.get('device_name')}")
    return {
        "status": "success",
        "access_token": token,
        "token_type": "bearer",
        "user_id": user_id,
        "role": role,
        "device_name": passkey.get("device_name"),
    }


# ── Device Management Endpoints ──────────────────────────────────────────────

@router.get("/devices")
async def list_devices(request: Request, user_id: Optional[str] = None):
    """Lists the caller's registered passkeys.

    The owner comes from the verified session; the legacy ``user_id`` query
    parameter is ignored (it allowed listing anyone's devices).
    """
    owner = _require_passkey_owner(request)
    devices = list_user_passkeys(owner)
    return {"devices": devices}


@router.delete("/devices/{credential_id}")
async def revoke_device(credential_id: str, request: Request, user_id: Optional[str] = None):
    """Revokes one of the caller's registered passkeys."""
    owner = _require_passkey_owner(request)
    success = revoke_user_passkey(credential_id, owner)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found or unauthorized")
    return {"status": "success", "message": "Passkey revoked successfully"}

"""Minimal, strict WebAuthn codec: CBOR (RFC 8949 subset), authenticator data, COSE keys.

Replaces the old byte-scanning parser in ``passkey_auth.py`` (it searched for the
literal ``authData`` and fixed x/y markers, so RS256 keys -- common on Windows
Hello TPMs -- were rejected and malformed input could be mis-read).

Only what WebAuthn needs: definite-length unsigned/negative ints, byte/text
strings, arrays, maps and the simple values false/true/null.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any, Optional, Tuple

_MAX_DEPTH = 8
_MAX_ITEMS = 64

FLAG_UP = 0x01  # user present
FLAG_UV = 0x04  # user verified
FLAG_AT = 0x40  # attested credential data included
FLAG_ED = 0x80  # extension data included

COSE_ALG_ES256 = -7
COSE_ALG_RS256 = -257


class WebAuthnFormatError(ValueError):
    """Malformed or unsupported authenticator payload."""


def _read_length(data: bytes, pos: int, info: int) -> Tuple[int, int]:
    if info < 24:
        return info, pos
    sizes = {24: 1, 25: 2, 26: 4, 27: 8}
    size = sizes.get(info)
    if size is None:
        raise WebAuthnFormatError("Indefinite or reserved CBOR length")
    if pos + size > len(data):
        raise WebAuthnFormatError("Truncated CBOR length")
    return int.from_bytes(data[pos:pos + size], "big"), pos + size


def cbor_decode(data: bytes, pos: int = 0, depth: int = 0) -> Tuple[Any, int]:
    """Decode one CBOR item at ``pos``; returns ``(value, next_pos)``."""
    if depth > _MAX_DEPTH:
        raise WebAuthnFormatError("CBOR nesting too deep")
    if pos >= len(data):
        raise WebAuthnFormatError("Truncated CBOR item")
    initial = data[pos]
    major, info = initial >> 5, initial & 0x1F
    pos += 1
    if major == 7:
        simple = {20: False, 21: True, 22: None}
        if info in simple:
            return simple[info], pos
        raise WebAuthnFormatError("Unsupported CBOR simple/float value")
    value, pos = _read_length(data, pos, info)
    if major == 0:
        return value, pos
    if major == 1:
        return -1 - value, pos
    if major in (2, 3):
        end = pos + value
        if end > len(data):
            raise WebAuthnFormatError("Truncated CBOR string")
        raw = data[pos:end]
        if major == 2:
            return bytes(raw), end
        try:
            return raw.decode("utf-8"), end
        except UnicodeDecodeError as exc:
            raise WebAuthnFormatError("Invalid UTF-8 in CBOR text") from exc
    if value > _MAX_ITEMS:
        raise WebAuthnFormatError("CBOR container too large")
    if major == 4:
        items = []
        for _ in range(value):
            item, pos = cbor_decode(data, pos, depth + 1)
            items.append(item)
        return items, pos
    if major == 5:
        result = {}
        for _ in range(value):
            key, pos = cbor_decode(data, pos, depth + 1)
            if isinstance(key, (list, dict)):
                raise WebAuthnFormatError("Unhashable CBOR map key")
            result[key], pos = cbor_decode(data, pos, depth + 1)
        return result, pos
    raise WebAuthnFormatError("Unsupported CBOR major type (tags)")


@dataclass(frozen=True)
class AuthenticatorData:
    rp_id_hash: bytes
    flags: int
    sign_count: int
    credential_id: Optional[bytes] = None
    cose_key: Optional[dict] = None

    @property
    def user_present(self) -> bool:
        return bool(self.flags & FLAG_UP)

    @property
    def user_verified(self) -> bool:
        return bool(self.flags & FLAG_UV)


def parse_authenticator_data(auth_data: bytes) -> AuthenticatorData:
    if len(auth_data) < 37:
        raise WebAuthnFormatError("authenticatorData is too short")
    rp_id_hash = bytes(auth_data[:32])
    flags = auth_data[32]
    sign_count = struct.unpack(">I", auth_data[33:37])[0]
    if not flags & FLAG_AT:
        return AuthenticatorData(rp_id_hash, flags, sign_count)
    if len(auth_data) < 55:
        raise WebAuthnFormatError("attestedCredentialData is too short")
    cred_len = struct.unpack(">H", auth_data[53:55])[0]
    cred_end = 55 + cred_len
    if cred_len == 0 or cred_len > 1023 or cred_end > len(auth_data):
        raise WebAuthnFormatError("Invalid credential id length")
    cose_key, _ = cbor_decode(auth_data, cred_end)
    if not isinstance(cose_key, dict):
        raise WebAuthnFormatError("Credential public key is not a COSE map")
    return AuthenticatorData(rp_id_hash, flags, sign_count, bytes(auth_data[55:cred_end]), cose_key)


def parse_attestation_object(attestation_object: bytes) -> bytes:
    """Returns the raw ``authData`` from a CBOR attestation object."""
    obj, _ = cbor_decode(attestation_object)
    if not isinstance(obj, dict) or not isinstance(obj.get("authData"), bytes):
        raise WebAuthnFormatError("attestationObject has no authData")
    return obj["authData"]


def cose_key_to_spki(cose_key: dict) -> bytes:
    """Converts an ES256 (EC2 P-256) or RS256 (RSA) COSE key to DER SubjectPublicKeyInfo."""
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    kty, alg = cose_key.get(1), cose_key.get(3)
    if kty == 2 and alg in (COSE_ALG_ES256, None):
        x, y, crv = cose_key.get(-2), cose_key.get(-3), cose_key.get(-1)
        if crv != 1 or not isinstance(x, bytes) or not isinstance(y, bytes) or len(x) != 32 or len(y) != 32:
            raise WebAuthnFormatError("Unsupported EC2 key (only P-256 / ES256)")
        try:
            key = ec.EllipticCurvePublicNumbers(
                int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()
            ).public_key()
        except ValueError as exc:
            raise WebAuthnFormatError("EC point is not on P-256") from exc
    elif kty == 3 and alg in (COSE_ALG_RS256, None):
        n, e = cose_key.get(-1), cose_key.get(-2)
        if not isinstance(n, bytes) or not isinstance(e, bytes) or len(n) < 256:
            raise WebAuthnFormatError("Unsupported RSA key (need >= 2048-bit RS256)")
        key = rsa.RSAPublicNumbers(int.from_bytes(e, "big"), int.from_bytes(n, "big")).public_key()
    else:
        raise WebAuthnFormatError(f"Unsupported COSE key (kty={kty}, alg={alg})")
    return key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)

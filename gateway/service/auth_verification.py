"""Client/guest/operator credential verification for the SupremeAI gateway.

Extracted from ``gateway/service/app.py`` (God-file split, 2026-11-24). This
module owns every reusable client-credential decision:

- guest-class cost guard (:func:`_guest_rate_limit`, :func:`_is_guest_cost_guard_signal`)
- server-issued guest verification (:func:`_is_verified_guest`)
- signed token issuance (:func:`_issue_signed_token` and TTL variants)
- request auth surface (:func:`_verify_client_auth`, :func:`_is_admin_principal`,
  :func:`_require_operator_key`, :func:`_extract_token`, ``OPERATOR_KEYS``)

``gateway.service.app`` re-imports every public name from here so existing
importers (``from service.app import _verify_client_auth`` etc.) keep working.
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from typing import Optional, Tuple

from fastapi import HTTPException, Request

try:
    from service.keygen import generate_key, get_signing_secret, verify_key
except ImportError:
    try:
        from gateway.service.keygen import generate_key, get_signing_secret, verify_key
    except ImportError:

        def generate_key(*args, **kwargs):  # type: ignore[misc]
            """Fail-closed stub: without keygen nothing can sign a token."""
            raise RuntimeError(
                "keygen unavailable (neither service.keygen nor "
                "gateway.service.keygen is importable): refusing to issue an "
                "unsigned credential"
            )

        def get_signing_secret() -> str:  # type: ignore[misc]
            """Fail-closed stub: no signing secret is resolvable without keygen."""
            raise RuntimeError(
                "keygen unavailable (neither service.keygen nor "
                "gateway.service.keygen is importable): no signing secret"
            )

        def verify_key(token: str):  # type: ignore[misc]
            return None

try:
    from service.registry_lookup import _registry_origin
except ImportError:
    from gateway.service.registry_lookup import _registry_origin  # type: ignore[no-redef]

try:
    from .auth_identity import verified_guest_claims
except ImportError:
    from gateway.service.auth_identity import verified_guest_claims

logger = logging.getLogger("supremeai.gateway")

# ── Guest Rate Limit (cost guard for the keyless bypass) ─────────────────────
# The x-guest-mode / studio-origin / "guest"-token bypass is intentional
# (Studio free tier), but it is the ONLY auth class with no throttle while the
# stealth relay is the single paid reply path. Unbounded guest traffic can
# drain relay quota and mask real outages (silent 502 storms). Sliding-window
# per client IP, in-memory (single-process asyncio — no new deps).
# বাংলা মন্তব্য: গেস্ট ক্লায়েন্টদের জন্য ডিফল্ট রেট লিমিট ১০ থেকে বাড়িয়ে ৬০ করা হলো যাতে লাইভ ফ্যাব্রিক সিঙ্ক ও স্বাভাবিক চ্যাট থ্রটলিং এড়ানো যায়।
GUEST_RATE_LIMIT_PER_MIN = max(0, int(os.getenv("GUEST_RATE_LIMIT_PER_MIN", "60")))
_GUEST_WINDOW_SECONDS = 60.0
_GUEST_BUCKET_CAP = 10000  # bounded memory: never track more IPs than this
_guest_hits: dict = {}


def _client_ip(request: Request) -> str:
    """Trusted-proxy-aware client IP.

    বাংলা মন্তব্য: Cloudflare Pages বা Edge প্রক্সি থেকে আসলে 'cf-connecting-ip' হেডারে মূল ক্লায়েন্ট
    আইপি থাকে। না থাকলে X-Forwarded-For-এ Render/CF প্রক্সি সর্বডানে প্রকৃত ক্লায়েন্ট আইপি
    যোগ করে; সবচেয়ে বাঁয়ের (client-supplied) হপ spoofable — bucketing কী হিসেবে গ্রহণযোগ্য নয়।

    Doctrine matches gateway/main.py::_client_ip: trust the LAST XFF hop.
    (The previous implementation trusted the leftmost hop, which let an
    unauthenticated caller rotate a fake X-Forwarded-For to mint a fresh
    rate-limit budget per request.)
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip and cf_ip.strip():
        return cf_ip.strip()
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "unknown"


# ── Guest identity split (auth vs. cost-guard) ───────────────────────────────
# HTTP clients fully control Origin/Referer/X-Guest-Mode and the well-known
# demo tokens, so NONE of them may gate an AUTH decision. They remain legitimate
# ONLY as a cost-guard signal for throttling. Real guest access is granted by a
# server-issued, signed, short-lived guest token or session cookie (see
# _is_verified_guest). This closes the spoof vector where an attacker sets
# X-Guest-Mode: true / Origin: <studio host> and rides the paid relay path.
_GUEST_TOKENS = {"guest", "demo", "public-guest"}
_GUEST_COOKIE = "supremeai_guest_session"


def _client_origin(request: Request) -> str:
    """Lowercased Origin header (client-supplied, never trusted for auth)."""
    return (request.headers.get("origin") or "").lower()


def _client_referer(request: Request) -> str:
    """Lowercased Referer header (client-supplied, never trusted for auth)."""
    return (request.headers.get("referer") or "").lower()


def _studio_hosts() -> list[str]:
    """Known Studio front-end hosts (for cost-guard classification only)."""
    hosts = [
        # Live Studio origin, from the registry (never a literal — a host
        # migration must not need a second edit here).
        *filter(None, [_registry_origin("frontend")]),
        "https://supremeai-studio.paykaribazaronline.workers.dev",
    ]
    preview = os.getenv("STUDIO_FRONTEND_URL", "").lower().strip()
    if preview:
        hosts.append(preview)
    return hosts


def _is_guest_cost_guard_signal(request: Request, token: Optional[str]) -> bool:
    """Cost-guard ONLY: classify a request as guest-class for throttling.

    Deliberately trusts spoofable client headers and well-known demo tokens.
    This is safe here because the worst case is over-throttling a keyed-auth
    caller — it never grants access. It must NEVER be used as an auth decision.
    """
    origin = _client_origin(request)
    referer = _client_referer(request)
    guest_token = token or request.cookies.get(_GUEST_COOKIE, "")
    return (
        request.headers.get("x-guest-mode", "").lower() == "true"
        or any(host in origin or host in referer for host in _studio_hosts())
        or token in _GUEST_TOKENS
        or bool(verified_guest_claims(guest_token))
    )


def _is_verified_guest(request: Request, token: Optional[str]) -> bool:
    """AUTH-CLASS guest check: only server-issued, signed short-lived tokens.

    A client-supplied header is NEVER sufficient. A request is a verified guest
    only when it carries a signed guest token (issued by _issue_guest_token)
    or a valid HttpOnly guest session cookie. Everything else — including
    X-Guest-Mode: true and any Origin/Referer — is rejected.

    An explicit test-only bypass exists ONLY when ENV=test AND
    SUPREMEAI_TEST_GUEST_BYPASS=1 is set, so the offline test suite can
    exercise the guest path without shipping a production bypass.
    """
    if os.environ.get("ENV", "").lower() == "test" and os.environ.get(
        "SUPREMEAI_TEST_GUEST_BYPASS", ""
    ) in ("1", "true", "yes"):
        return True
    # Explicit credentials take precedence: a bad bearer cannot fall back to a
    # different cookie principal. keygen uses dot-separated payload segments.
    candidate = token or request.cookies.get(_GUEST_COOKIE, "")
    return bool(verified_guest_claims(candidate))


def _issue_signed_token(client_name: str, quota: str) -> str:
    """Issue a keygen-signed token, failing closed when keygen is unusable.

    Token issuance is never degraded: an unsigned/placeholder value (e.g. a
    ``sess_<hex>`` string or an empty string) cannot be verified by
    ``verify_key`` and would silently hand the caller a useless credential.
    A keygen failure is surfaced as a 503 so the misconfiguration is visible.
    """
    try:
        return generate_key(client_name=client_name, quota=quota)
    except Exception as exc:  # keygen failure is surfaced as 503, never swallowed
        # বাংলা মন্তব্য: CodeQL py/clear-text-logging-sensitive-data কমপ্লায়েন্স — লগ ফাইলে সংবেদনশীল ডেটা না রেখে শুধু এক্সসেপশন টাইপ লগ করা হচ্ছে
        logger.error(
            "[auth] token issuance failed: %s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503, detail="Token issuance is temporarily unavailable"
        ) from exc


def _issue_guest_token(ttl_seconds: int = 300) -> str:
    """Issue a signed, short-lived guest token (HMAC via service.keygen).

    The TTL is embedded in the token payload as an ``.exp`` claim so the
    credential is statelessly rejected once expired (see keygen.verify_key).
    """
    return _issue_signed_token_with_ttl(client_name="guest", quota="guest", ttl_seconds=ttl_seconds)


def _issue_signed_token_with_ttl(client_name: str, quota: str, ttl_seconds: int) -> str:
    """Issue a keygen-signed token with an embedded expiry, failing closed."""
    try:
        return generate_key(client_name=client_name, quota=quota, ttl_seconds=ttl_seconds)
    except Exception as exc:  # keygen failure is surfaced as 503, never swallowed
        # বাংলা মন্তব্য: CodeQL py/clear-text-logging-sensitive-data কমপ্লায়েন্স — লগ ফাইলে সংবেদনশীল ডেটা না রেখে শুধু এক্সসেপশন টাইপ লগ করা হচ্ছে
        logger.error(
            "[auth] token issuance failed: %s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503, detail="Token issuance is temporarily unavailable"
        ) from exc


def _guest_rate_limit(request: Request) -> Tuple[bool, float]:
    """Sliding-window per-IP limiter for guest-class requests.
    Returns (allowed, retry_after_seconds). GUEST_RATE_LIMIT_PER_MIN<=0 disables."""
    if GUEST_RATE_LIMIT_PER_MIN <= 0:
        return True, 0.0
    ip = _client_ip(request)
    now = time.time()
    dq = _guest_hits.get(ip)
    if dq is None:
        if len(_guest_hits) >= _GUEST_BUCKET_CAP:
            # Evict expired buckets first; then force-evict oldest if still full.
            for k in [k for k, v in _guest_hits.items() if not v or v[-1] < now - _GUEST_WINDOW_SECONDS]:
                _guest_hits.pop(k, None)
            while len(_guest_hits) >= _GUEST_BUCKET_CAP:
                _guest_hits.pop(next(iter(_guest_hits)))
        dq = _guest_hits[ip] = deque()
    while dq and dq[0] < now - _GUEST_WINDOW_SECONDS:
        dq.popleft()
    if len(dq) >= GUEST_RATE_LIMIT_PER_MIN:
        return False, max(1.0, _GUEST_WINDOW_SECONDS - (now - dq[0]))
    dq.append(now)
    return True, 0.0

# Operator telemetry requires a dedicated credential. Generic client API keys
# (including signed ``sk-supreme-*`` keys) must never grant fleet visibility.
# SUPREMEAI_SUPERADMIN_KEY and MCP_SUPERADMIN_KEY remain supported as explicit
# rotation aliases for existing deployments.
OPERATOR_KEYS = {
    value.strip()
    for value in (
        os.getenv("SUPREMEAI_OPERATOR_KEY", ""),
        os.getenv("SUPREMEAI_SUPERADMIN_KEY", ""),
        os.getenv("MCP_SUPERADMIN_KEY", ""),
    )
    if value and value.strip()
}
SUPERADMIN_KEY = os.getenv("SUPREMEAI_SUPERADMIN_KEY", os.getenv("MCP_SUPERADMIN_KEY", "")).strip()


def _extract_token(request: Request, x_supremeai_key: Optional[str]) -> Optional[str]:
    """Resolve the caller token: explicit X-SupremeAI-Key header wins, else Bearer."""
    if x_supremeai_key:
        return x_supremeai_key
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return None


def _verify_client_auth(request: Request, x_supremeai_key: Optional[str] = None) -> bool:
    """
    Validates client gateway access token:
    1. First checks if it is a cryptographically signed sk-supreme-... key via keygen.
    2. Then checks if it matches SUPREMEAI_API_KEY, SUPREMEAI_API_KEYS, or SUPERADMIN_KEY.
    3. Fails closed in production if environment has no keys.
    """
    token = _extract_token(request, x_supremeai_key)

    # Guest pass-through ONLY for server-issued, signed short-lived guest tokens
    # or a valid HttpOnly guest session cookie. Client-supplied headers are NOT
    # trusted here — see _is_verified_guest / _is_guest_cost_guard_signal.
    if _is_verified_guest(request, token):
        return True

    if not token:
        # Check if environment is secured (fail-closed in non-dev)
        return not (os.getenv("SUPREMEAI_API_KEY") or SUPERADMIN_KEY or os.getenv("ENVIRONMENT") != "development")

    # 1. Check stateless cryptographic HMAC signature (sk-supreme-...)
    if token.startswith("sk-supreme-"):
        meta = verify_key(token)
        if meta:
            # Guest credentials must also carry the signed guest quota and expiry.
            if meta.get("client") == "guest":
                return bool(verified_guest_claims(token))
            return True

    # 2. Check static master/pool env keys
    valid_keys = set()
    master = os.getenv("SUPREMEAI_API_KEY", "").strip()
    if master:
        valid_keys.add(master)
    pool_str = os.getenv("SUPREMEAI_API_KEYS", "").strip()
    if pool_str:
        for k in pool_str.split(","):
            if k.strip():
                valid_keys.add(k.strip())
    if SUPERADMIN_KEY:
        valid_keys.add(SUPERADMIN_KEY)

    if not valid_keys:
        return os.getenv("ENVIRONMENT") == "development"

    # FIX (full audit 2026-11-13 F-006): `token in valid_keys` short-circuits on
    # first-byte differences — a remote timing oracle on the static pool.
    # Constant-time scan keeps the signed-key path (keygen.verify_key already
    # uses hmac.compare_digest) consistent for static env keys.
    import hmac as _hmac

    return any(_hmac.compare_digest(token, k) for k in valid_keys)


def _is_admin_principal(
    request: Request,
    x_supremeai_key: Optional[str] = None,
    x_superadmin_key: Optional[str] = None,
) -> bool:
    """Authorize administrative (superuser) access only.

    Unlike ``_verify_client_auth``, an ordinary client API key, a guest token,
    or a standard-quota ``sk-supreme-`` key is REJECTED. Access requires EITHER
    the dedicated superadmin key OR an admin-scoped signed token
    (``client == 'studio-admin'`` / ``quota == 'unlimited'``) OR a valid admin
    JWT whose role is ``admin``.
    """
    import hmac as _hmac

    if (
        SUPERADMIN_KEY
        and x_superadmin_key
        and _hmac.compare_digest(x_superadmin_key, SUPERADMIN_KEY)
    ):
        return True

    token = _extract_token(request, x_supremeai_key)
    if not token:
        return False

    try:
        from gateway.service.admin_auth import is_admin_token
    except ImportError:
        try:
            from service.admin_auth import is_admin_token  # type: ignore[no-redef]
        except ImportError:
            is_admin_token = None  # type: ignore[assignment]
    return bool(is_admin_token is not None and is_admin_token(token, verify_key_fn=verify_key))


def _require_operator_key(request: Request, x_supremeai_key: Optional[str] = None) -> bool:
    """Authorize operator-only telemetry with a dedicated exact-match key.

    This is intentionally not backed by ``verify_key``: that verifier validates
    ordinary client API keys and has no operator scope. Keeping the credential
    separate makes the authorization boundary explicit and allows independent
    rotation/revocation.
    """
    token = _extract_token(request, x_supremeai_key)
    if not token or not OPERATOR_KEYS:
        return False
    authorized = token in OPERATOR_KEYS
    if authorized:
        logger.info("operator telemetry authorized principal=operator scope=telemetry")
    else:
        logger.warning("operator telemetry denied principal=unknown scope=telemetry")
    return authorized


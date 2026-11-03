"""SEC-HARDEN-2026-09 — Gap-closing security control tests.

Closes the coverage gaps identified by the 30-category security audit
(`docs/security/SECURITY_AUDIT_MATRIX.md`, 2026-09-12). Each class maps to a
matrix category:

- ``TestJWTAlgorithmConfusion``      → row 4  (JWT Security)
- ``TestClientIPSpoofResistance``    → row 14 (Rate-limit bypass)
- ``TestSSRFProtectionUnit``         → row 7  (SSRF)
- ``TestWAFAttackPatterns``          → rows 8, 10 (Path traversal / XSS)
- ``TestMassAssignmentProtection``   → row 16 (Mass Assignment)

Convention (same as ``test_cross_tenant_isolation.py``): unit/source-level only —
no heavy application fixtures, so these run in the fast Critical/security tier.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Import-light helpers that do NOT pull the whole app fixture graph
# ---------------------------------------------------------------------------
from core.middleware.security import RequestValidationMiddleware
from core.security.protection.ssrf_protection import SSRFProtection
from utils.client_ip import get_client_ip

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def _source_of(rel_path: str) -> str:
    """Read a backend file from disk (dependency-free source assertions)."""
    return (BACKEND_DIR / rel_path).read_text(encoding="utf-8")


def _make_unsigned_jwt(payload: dict) -> str:
    """Build an ``alg=none`` token manually (header.payload.) for bypass probes."""
    header = {"alg": "none", "typ": "JWT"}

    def _b64(obj) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    return f"{_b64(header)}.{_b64(payload)}."


@pytest.fixture(scope="module")
def app_secret() -> str:
    """The exact secret the real verify path uses (single source)."""
    from core.security import _get_jwt_secret

    return _get_jwt_secret()


# ===========================================================================
# Row 4 — JWT: alg:none / tampered / expired against the real verify path
# ===========================================================================
class TestJWTAlgorithmConfusion:
    """Attack tokens must be rejected by the production verification path."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_none_algorithm_token_rejected(self):
        from core.security import verify_token_async

        token = _make_unsigned_jwt(
            {"sub": "user-1", "role": "admin", "exp": 4102444800}  # year 2100
        )
        with pytest.raises(HTTPException) as excinfo:
            await verify_token_async(token)
        assert excinfo.value.status_code == 401

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_tampered_signature_rejected(self, app_secret):
        import jwt

        from core.security import verify_token_async

        valid = jwt.encode({"sub": "user-1", "exp": 4102444800}, app_secret, algorithm="HS256")
        parts = valid.split(".")
        # Flip payload bits while keeping structure to force signature mismatch.
        tampered = f"{parts[0]}.{parts[1][:-1]}{'A' if parts[1][-1] != 'A' else 'B'}.{parts[2]}"
        with pytest.raises(HTTPException) as excinfo:
            await verify_token_async(tampered)
        assert excinfo.value.status_code == 401

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, app_secret):
        import jwt

        from core.security import verify_token_async

        expired = jwt.encode(
            {"sub": "user-1", "exp": 1_600_000_000},  # 2020
            app_secret,
            algorithm="HS256",
        )
        with pytest.raises(HTTPException) as excinfo:
            await verify_token_async(expired)
        assert excinfo.value.status_code == 401

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_valid_token_accepted(self):
        from core.security import create_access_token, verify_token_async

        payload = await verify_token_async(create_access_token({"sub": "u-hardening-test"}))
        assert payload["sub"] == "u-hardening-test"
        assert "jti" in payload
        assert "exp" in payload

    @pytest.mark.unit
    def test_production_weak_secret_is_fatal(self):
        """config_secrets must refuse boot when the JWT secret is missing/short."""
        src = _source_of("core/config_secrets.py")
        # Issue #542/#567: the floor is centralized in core/secret_policy.py
        # (JWT_SECRET_MIN_LENGTH = 64) and config_secrets enforces it via the
        # constant instead of a hardcoded literal.
        assert re.search(r"len\s*\(\s*secret\s*\)\s*<\s*JWT_SECRET_MIN_LENGTH", src), (
            "production JWT secret length guard missing"
        )
        assert "RuntimeError" in src, "production must fail closed on weak secret"
        assert "resolve_jwt_secret_env" in src, "canonical env resolver must be consulted"
        policy_src = _source_of("core/secret_policy.py")
        assert re.search(r"JWT_SECRET_MIN_LENGTH\s*(:\s*int)?\s*=\s*64", policy_src), (
            "JWT secret floor must stay at 64 bytes"
        )


# ===========================================================================
# Row 14 — Rate-limit bypass: client-IP extraction is proxy-aware & spoof-proof
# ===========================================================================
class TestClientIPSpoofResistance:
    """Attacker-supplied X-Forwarded-For prefixes must never become the bucket key."""

    @staticmethod
    def _request(client_host: str, xff: str | None) -> SimpleNamespace:
        headers = {"x-forwarded-for": xff} if xff else {}
        return SimpleNamespace(client=SimpleNamespace(host=client_host), headers=headers)

    @pytest.mark.unit
    def test_direct_exposure_ignores_xff(self):
        with patch("utils.client_ip._trusted_proxy_count", return_value=0):
            ip = get_client_ip(self._request("1.1.1.1", "6.6.6.6"))
        assert ip == "1.1.1.1"  # no proxy → XFF fully ignored

    @pytest.mark.unit
    def test_trusted_proxy_uses_last_hops_not_first(self):
        # Render/N=1: attacker sends "6.6.6.6", proxy appends real "5.5.5.5".
        with patch("utils.client_ip._trusted_proxy_count", return_value=1):
            ip = get_client_ip(self._request("2.2.2.2", "6.6.6.6, 5.5.5.5"))
        assert ip == "5.5.5.5"  # spoofed prefix dropped

    @pytest.mark.unit
    def test_single_trailing_client_ip_used(self):
        with patch("utils.client_ip._trusted_proxy_count", return_value=1):
            ip = get_client_ip(self._request("2.2.2.2", "203.0.113.7"))
        assert ip == "203.0.113.7"

    @pytest.mark.unit
    def test_short_chain_returns_raw_host(self):
        with patch("utils.client_ip._trusted_proxy_count", return_value=2):
            ip = get_client_ip(self._request("2.2.2.2", "6.6.6.6"))
        assert ip == "2.2.2.2"  # malformed chain → fail safe

    @pytest.mark.unit
    def test_missing_xff_returns_raw_host(self):
        with patch("utils.client_ip._trusted_proxy_count", return_value=1):
            ip = get_client_ip(self._request("2.2.2.2", None))
        assert ip == "2.2.2.2"


# ===========================================================================
# Row 7 — SSRF: private / loopback / link-local / metadata / internal blocking
# ===========================================================================
class TestSSRFProtectionUnit:
    """Unit probes against SSRFProtection.validate_url with mocked DNS."""

    @pytest.fixture(autouse=True)
    def _mock_dns(self):
        """Route DNS through a controllable map so no real lookups occur.

        Hostnames not listed resolve to a public IP so metadata/hostname checks
        are what is under test, not DNS flakiness.
        """
        resolver = {"roundrobin.example": ["1.2.3.4", "10.0.0.44"]}  # rebinding pair

        def _resolve(hostname: str, use_cache: bool = True) -> str:
            if hostname in resolver:
                return resolver[hostname].pop(0)
            # Literal IP hostnames resolve to themselves (mirrors socket.gethostbyname),
            # so private/loopback/metadata IP checks see the caller-supplied target.
            try:
                ipaddress.ip_address(hostname)
                return hostname
            except ValueError:
                return "93.184.216.34"  # unknown domain → public IP

        with patch.object(SSRFProtection, "_resolve_hostname", side_effect=_resolve):
            yield

    @pytest.mark.unit
    def test_private_ip_literal_blocked(self):
        from core.security.protection.ssrf_protection import SSRFProtection

        for url in ("http://10.0.0.1/", "http://192.168.1.10/", "http://172.16.5.5/"):
            result = SSRFProtection().validate_url(url)
            assert result.is_safe is False, f"{url} must be blocked as private"

    @pytest.mark.unit
    def test_loopback_and_linklocal_blocked(self):
        from core.security.protection.ssrf_protection import SSRFProtection

        for url in ("http://127.0.0.1/admin", "http://[::1]/", "http://169.254.169.254/"):
            result = SSRFProtection().validate_url(url)
            assert result.is_safe is False, f"{url} must be blocked (loopback/link-local)"

    @pytest.mark.unit
    def test_cloud_metadata_blocked(self):
        from core.security.protection.ssrf_protection import SSRFProtection

        result = SSRFProtection().validate_url("http://169.254.169.254/latest/meta-data/")
        assert result.is_safe is False
        assert "metadata" in result.reason.lower()

    @pytest.mark.unit
    def test_internal_hostname_suffix_blocked(self):
        from core.security.protection.ssrf_protection import SSRFProtection

        for url in ("http://db.internal/", "http://api.corp/", "http://files.local/"):
            result = SSRFProtection().validate_url(url)
            assert result.is_safe is False, f"{url} must be blocked (internal TLD)"

    @pytest.mark.unit
    def test_localhost_blocked(self):
        from core.security.protection.ssrf_protection import SSRFProtection

        assert SSRFProtection().validate_url("http://localhost/").is_safe is False

    @pytest.mark.unit
    def test_non_http_scheme_blocked(self):
        from core.security.protection.ssrf_protection import SSRFProtection

        for url in ("file:///etc/passwd", "gopher://internal", "ftp://10.0.0.1/x"):
            assert SSRFProtection().validate_url(url).is_safe is False

    @pytest.mark.unit
    def test_domain_resolving_to_private_ip_blocked(self):
        from core.security.protection.ssrf_protection import SSRFProtection

        # Public-looking host whose DNS resolves to loopback must be rejected.
        with patch.object(SSRFProtection, "_resolve_hostname", return_value="127.0.0.1"):
            blocked = SSRFProtection().validate_url("http://evil.example/")
        assert blocked.is_safe is False

    @pytest.mark.unit
    def test_dns_rebinding_flagged(self):
        from core.security.protection.ssrf_protection import SSRFProtection

        # First resolve = public, second resolve = private → rebinding attack.
        result = SSRFProtection().validate_url("http://roundrobin.example/")
        assert result.is_safe is False
        assert "rebinding" in result.reason.lower()

    @pytest.mark.unit
    def test_public_url_allowed(self):
        from core.security.protection.ssrf_protection import SSRFProtection

        result = SSRFProtection().validate_url("http://93.184.216.34/")
        assert result.is_safe is True


# ===========================================================================
# Rows 8 & 10 — Path traversal (incl. encoded variants) + XSS WAF detection
# ===========================================================================
class TestWAFAttackPatterns:
    """RequestValidationMiddleware detection primitives (no real request needed)."""

    @pytest.fixture(scope="class")
    def waf(self):
        return RequestValidationMiddleware(lambda request: None)

    @pytest.mark.unit
    def test_sql_injection_detected(self, waf):
        for payload in ("' OR '1'='1", "1; DROP TABLE users; --", "' UNION SELECT * FROM users--"):
            assert waf._detect_sql_injection(payload) is True

    @pytest.mark.unit
    def test_clean_query_not_sql(self, waf):
        assert waf._detect_sql_injection("dashboard?page=2&sort=name") is False

    @pytest.mark.unit
    def test_xss_detected(self, waf):
        for payload in ("<script>alert(1)</script>", "javascript:alert(1)", "<iframe src=x>"):
            assert waf._detect_xss(payload) is True

    @pytest.mark.unit
    def test_clean_query_not_xss(self, waf):
        assert waf._detect_xss("name=John+O'Neil&age=30") is False

    @pytest.mark.unit
    def test_path_traversal_detected(self, waf):
        for payload in ("../../etc/passwd", "..\\windows\\win.ini", "${7*7}"):
            assert waf._detect_dangerous(payload) is True

    @pytest.mark.unit
    def test_encoded_path_traversal_detected(self, waf):
        """SEC-HARDEN-2026-09: hex/double-encoded ../ must not bypass the WAF."""
        for payload in (
            "%2e%2e%2fetc/passwd",  # URL-encoded ../
            "%2E%2E%2Fetc/passwd",  # uppercase hex
            "%252e%252e%252fetc/passwd",  # double-encoded
            "%252e%252e%255cwindows",  # double-encoded ..\
            "..%2fetc/passwd",  # mixed ..%2f
            "..%5cwindows",  # mixed ..%5c
        ):
            assert waf._detect_dangerous(payload) is True, f"bypass payload: {payload}"

    @pytest.mark.unit
    def test_clean_path_not_blocked(self, waf):
        assert waf._detect_dangerous("search?q=hello+world") is False


# ===========================================================================
# Row 16 — Mass assignment: privileged fields are not client-settable
# ===========================================================================
class TestMassAssignmentProtection:
    """Public request models must not expose role / admin / verification flags."""

    PRIVILEGED_FIELDS = ("role", "is_admin", "is_superadmin", "is_verified", "is_active")

    @staticmethod
    def _model_block(src: str, class_name: str) -> str:
        start = src.index(f"class {class_name}")
        # Slice until the next top-level class / decorator / def boundary.
        rest = src[start:]
        for marker in ("\nclass ", "\n@", "\ndef "):
            idx = rest.find(marker, len(class_name) + 8)
            if idx != -1:
                return rest[:idx]
        return rest

    @pytest.mark.unit
    def test_register_request_has_minimal_fields(self):
        src = _source_of("api/routes/auth.py")
        block = self._model_block(src, "RegisterRequest")
        assert "username" in block and "password" in block
        for field in self.PRIVILEGED_FIELDS:
            assert field not in block, f"RegisterRequest must not expose {field!r}"

    @pytest.mark.unit
    def test_login_request_has_no_privileged_fields(self):
        src = _source_of("api/routes/auth.py")
        block = self._model_block(src, "LoginRequest")
        assert "username" in block or "email" in block
        for field in self.PRIVILEGED_FIELDS:
            assert field not in block, f"LoginRequest must not expose {field!r}"

    @pytest.mark.unit
    def test_governance_contracts_forbid_extra_fields(self):
        """Canonical governance/capability models fail closed on unknown fields."""
        for rel in (
            "core/automation/models.py",
            "core/circles/contracts.py",
            "api/routes/capabilities.py",
        ):
            src = _source_of(rel)
            assert 'extra="forbid"' in src or "extra='forbid'" in src, (
                f"{rel} should use strict Pydantic models (extra='forbid')"
            )


# ===========================================================================
# SEC-HARDEN P5 / P6 / P9 — regression guards for the 2026-09-12 hardening batch
# ===========================================================================
class TestHardeningRegressions:
    """Forbid the exact insecure patterns this hardening removed."""

    @pytest.mark.unit
    def test_sso_never_disables_signature_verification(self):
        """P5: OIDC id_token must be JWKS-verified; verify_signature=False is banned."""
        src = _source_of("tools/sso_integrator.py")
        # Banned executable pattern (docs/comments may mention the keyword).
        assert 'jwt.decode(id_token, options={"verify_signature": False})' not in src
        assert "options={'verify_signature': False}" not in src
        assert "_verify_oidc_id_token" in src
        assert "PyJWKClient" in src
        assert "fail closed" in src.lower() or "fail_closed" in src

    @pytest.mark.unit
    def test_sso_jwks_uri_is_https_only(self):
        """P5: refusing to fetch signing keys over plain http (SSRF-adjacent)."""
        src = _source_of("tools/sso_integrator.py")
        assert 'startswith("https://")' in src

    @pytest.mark.unit
    def test_render_proxy_never_allows_arbitrary_framing(self):
        """P6: browser render proxy must not send ALLOWALL / frame-ancestors *."""
        # FIX (final-test ci-fixes): browser.py monolith এখন api/routes/browser/ প্যাকেজ —
        # render proxy লজিক _render_proxy.py-তে। সেই মডিউলই এই security contract-এর source।
        src = _source_of("api/routes/browser/_render_proxy.py")
        # Banned executable header values (comments may mention the keyword).
        assert '"X-Frame-Options": "ALLOWALL"' not in src
        assert '"Content-Security-Policy": "frame-ancestors *"' not in src
        assert "_frame_ancestors_sources" in src
        assert 'X-Frame-Options": "SAMEORIGIN"' in src or 'X-Frame-Options": "DENY"' in src

    @pytest.mark.unit
    def test_global_csp_has_no_inline_script_execution(self):
        """P9: global CSP must not allow script-src 'unsafe-inline'."""
        src = _source_of("core/middleware/security.py")
        block = src[src.index("SECURITY_HEADERS = {") :]
        assert "script-src 'self' 'unsafe-inline'" not in block, (
            "script-src 'unsafe-inline' must stay removed from the global CSP"
        )
        assert "script-src 'self';" in block
        assert "object-src 'none'" in block
        assert "base-uri 'self'" in block
        assert "form-action 'self'" in block


# ===========================================================================
# SEC-HARDEN P5 — OIDC id_token verification must fail closed (no network needed)
# ===========================================================================
class TestOidcSignatureVerification:
    """Behavioral tests for the fail-closed JWKS verification path."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_unsupported_provider_fails_closed(self):
        from tools.sso_integrator import SSOIntegrator

        payload, err = await SSOIntegrator()._verify_oidc_id_token("nope", "x.y.z", "client-1")
        assert payload is None
        assert err and "Unsupported" in err

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_plain_http_jwks_refused(self, monkeypatch):
        from tools.sso_integrator import SSOIntegrator

        # Force a provider whose jwks_uri would be fetched over plain http.
        monkeypatch.setitem(
            SSOIntegrator.OIDC_PROVIDERS,
            "fakeidp",
            {"jwks_uri": "http://insecure.example.com/keys"},
        )
        payload, err = await SSOIntegrator()._verify_oidc_id_token("fakeidp", "x.y.z", "client-1")
        assert payload is None
        assert "https" in err.lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_jwks_fetch_or_verify_failure_returns_no_claims(self):
        from tools.sso_integrator import SSOIntegrator

        with patch("tools.sso_integrator.jwt.PyJWKClient", side_effect=RuntimeError("boom")):
            payload, err = await SSOIntegrator()._verify_oidc_id_token(
                "google", "h.p.s", "client-1"
            )
        assert payload is None
        assert err

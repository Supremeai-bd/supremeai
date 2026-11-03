"""Full-coverage tests for core.security.origin_validator (TrustedOriginMiddleware).

Extends tests/core/test_origin_validator.py with dispatch-level tests:
OPTIONS preflight, CSRF origin blocking, Host-header tampering detection,
public-path bypass, security response headers, and _load_origins parsing.
All settings are mocked; no network, no real app.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import Response

import core.security.origin_validator as ov_module
from core.security.origin_validator import (
    ADMIN_DEFAULT_TRUSTED_ORIGINS,
    USER_DEFAULT_TRUSTED_ORIGINS,
    TrustedOriginMiddleware,
    _load_origins,
)

pytestmark = pytest.mark.security


def make_fake_settings(**overrides):
    s = MagicMock()
    s.service_role = "user"
    s.admin_cors_origins = []
    s.user_cors_origins = []
    s.cors_origins = []
    s.env = "local"
    s.is_origin_bypass_allowed = False
    s.supremeai_public_paths = ["/api/v1/health", "/docs"]
    s.allowed_hosts = []
    for key, value in overrides.items():
        setattr(s, key, value)
    return s


def make_request(
    path="/api/v1/agents",
    method="GET",
    headers=None,
    scheme="http",
    client_host="203.0.113.5",
):
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "query_string": b"",
        "client": (client_host, 52341) if client_host else None,
        "scheme": scheme,
        "server": ("testserver", 80),
    }
    return Request(scope)


async def call_next_handler(request):
    return Response("ok", status_code=200)


def response_body(response) -> str:
    return response.body.decode() if hasattr(response, "body") else ""


class TestLoadOrigins:
    def test_env_unset_returns_default(self, monkeypatch):
        monkeypatch.delenv("OV_TEST_VAR", raising=False)
        default = frozenset({"https://default.example"})
        assert _load_origins("OV_TEST_VAR", default) == default

    def test_env_json_list_parsed(self, monkeypatch):
        monkeypatch.setenv("OV_TEST_VAR", json.dumps(["https://a.com", "https://b.com"]))
        assert _load_origins("OV_TEST_VAR", frozenset()) == frozenset(
            {"https://a.com", "https://b.com"}
        )

    def test_env_invalid_json_comma_split(self, monkeypatch):
        monkeypatch.setenv("OV_TEST_VAR", "https://a.com, https://b.com ,")
        assert _load_origins("OV_TEST_VAR", frozenset()) == frozenset(
            {"https://a.com", "https://b.com"}
        )

    def test_env_json_non_list_falls_back_to_default(self, monkeypatch):
        # parsed JSON that is not a list (e.g. dict) -> silently returns default
        monkeypatch.setenv("OV_TEST_VAR", '{"not": "a list"}')
        default = frozenset({"https://fallback.example"})
        assert _load_origins("OV_TEST_VAR", default) == default

    def test_env_empty_string_returns_default(self, monkeypatch):
        monkeypatch.setenv("OV_TEST_VAR", "")
        default = frozenset({"x"})
        assert _load_origins("OV_TEST_VAR", default) == default


class TestPortalRole:
    def test_override_normalised(self, monkeypatch):
        monkeypatch.setattr(ov_module, "settings", make_fake_settings())
        mw = TrustedOriginMiddleware(app=MagicMock(), portal_role="ADMIN")
        assert mw.portal_role == "admin"

    def test_settings_role_admin(self, monkeypatch):
        monkeypatch.setattr(ov_module, "settings", make_fake_settings(service_role="admin"))
        mw = TrustedOriginMiddleware(app=MagicMock())
        assert mw.portal_role == "admin"

    def test_settings_role_exception_falls_back_to_user(self, monkeypatch):
        bad_settings = MagicMock()
        # str(service_role) raises -> exception branch -> "user"
        type(bad_settings).service_role = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        monkeypatch.setattr(ov_module, "settings", bad_settings)
        mw = TrustedOriginMiddleware(app=MagicMock())
        assert mw.portal_role == "user"

    def test_settings_role_none_falls_back_to_user(self, monkeypatch):
        monkeypatch.setattr(ov_module, "settings", make_fake_settings(service_role=None))
        mw = TrustedOriginMiddleware(app=MagicMock())
        assert mw.portal_role == "user"

    def test_default_origins_property_admin_vs_user(self, monkeypatch):
        monkeypatch.setattr(ov_module, "settings", make_fake_settings())
        admin_mw = TrustedOriginMiddleware(app=MagicMock(), portal_role="admin")
        user_mw = TrustedOriginMiddleware(app=MagicMock(), portal_role="user")
        assert admin_mw._default_origins == set(ADMIN_DEFAULT_TRUSTED_ORIGINS)
        assert user_mw._default_origins == set(USER_DEFAULT_TRUSTED_ORIGINS)


class TestAllowedOrigins:
    def test_union_of_user_and_admin_sets(self, monkeypatch):
        monkeypatch.setattr(ov_module, "settings", make_fake_settings())
        mw = TrustedOriginMiddleware(app=MagicMock(), portal_role="user")
        origins = mw.allowed_origins
        assert USER_DEFAULT_TRUSTED_ORIGINS.issubset(origins)
        assert ADMIN_DEFAULT_TRUSTED_ORIGINS.issubset(origins)

    def test_empty_origin_filtered_out(self, monkeypatch):
        monkeypatch.setattr(ov_module, "settings", make_fake_settings(user_cors_origins=["", "*"]))
        mw = TrustedOriginMiddleware(app=MagicMock())
        assert "" not in mw.allowed_origins
        assert "*" not in mw.allowed_origins

    def test_env_read_failure_uses_defaults(self, monkeypatch):
        bad_settings = make_fake_settings()
        # settings.env access raises inside the try-block -> warning branch
        type(bad_settings).env = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("config broken"))
        )
        monkeypatch.setattr(ov_module, "settings", bad_settings)
        mw = TrustedOriginMiddleware(app=MagicMock())
        assert USER_DEFAULT_TRUSTED_ORIGINS.issubset(mw.allowed_origins)


class TestDispatchOptions:
    def _mw(self, monkeypatch, **settings_overrides):
        settings = make_fake_settings(**settings_overrides)
        monkeypatch.setattr(ov_module, "settings", settings)
        return TrustedOriginMiddleware(app=MagicMock())

    async def test_options_with_allowed_origin(self, monkeypatch):
        mw = self._mw(monkeypatch, user_cors_origins=["https://good.example"])
        request = make_request(
            method="OPTIONS",
            headers={
                "Origin": "https://good.example",
                "Access-Control-Request-Headers": "X-Custom-Header",
            },
        )
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://good.example"
        assert response.headers["access-control-allow-credentials"] == "true"
        assert response.headers["access-control-allow-headers"] == "X-Custom-Header"
        assert response.headers["access-control-allow-methods"].startswith("GET")

    async def test_options_with_disallowed_origin_no_allow_header(self, monkeypatch):
        mw = self._mw(monkeypatch, user_cors_origins=["https://good.example"])
        request = make_request(method="OPTIONS", headers={"Origin": "https://evil.example"})
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers

    async def test_options_without_origin_wildcard(self, monkeypatch):
        mw = self._mw(monkeypatch)
        request = make_request(method="OPTIONS")
        response = await mw.dispatch(request, call_next_handler)
        assert response.headers["access-control-allow-origin"] == "*"
        # default requested headers used when preflight header absent
        assert "X-API-Key" in response.headers["access-control-allow-headers"]


class TestDispatchOriginEnforcement:
    def _mw(self, monkeypatch, **settings_overrides):
        settings = make_fake_settings(**settings_overrides)
        monkeypatch.setattr(ov_module, "settings", settings)
        return TrustedOriginMiddleware(app=MagicMock())

    async def test_public_path_bypasses_all_checks(self, monkeypatch):
        mw = self._mw(monkeypatch, allowed_hosts=["real.example"])
        request = make_request(path="/api/v1/health", headers={"Origin": "https://evil.example"})
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 200
        # call_next ran (the "ok" body), not the middleware's 403
        assert response_body(response) == "ok"

    async def test_origin_bypass_allowed_flag_skips_check(self, monkeypatch):
        mw = self._mw(monkeypatch, is_origin_bypass_allowed=True)
        request = make_request(headers={"Origin": "https://evil.example"})
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 200

    async def test_test_env_env_var_skips_origin_check(self, monkeypatch):
        monkeypatch.setenv("ENV", "test")
        mw = self._mw(monkeypatch, env="production")
        request = make_request(headers={"Origin": "https://evil.example"})
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 200

    async def test_bad_origin_blocked_403(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        mw = self._mw(
            monkeypatch,
            env="production",
            user_cors_origins=["https://good.example"],
        )
        request = make_request(headers={"Origin": "https://evil.example"})
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 403
        assert "Cross-Origin Request Blocked" in response_body(response)

    async def test_no_origin_header_passes_origin_check(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        mw = self._mw(monkeypatch, env="production")
        request = make_request()  # same-origin request: no Origin header
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 200

    async def test_good_origin_allowed(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        mw = self._mw(
            monkeypatch,
            env="production",
            user_cors_origins=["https://good.example"],
        )
        request = make_request(headers={"Origin": "https://good.example"})
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 200

    async def test_client_without_addr_still_blocks_bad_origin(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        mw = self._mw(
            monkeypatch,
            env="production",
            user_cors_origins=["https://good.example"],
        )
        request = make_request(headers={"Origin": "https://evil.example"}, client_host=None)
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 403


class TestDispatchHostHeader:
    def _mw(self, monkeypatch, **settings_overrides):
        settings = make_fake_settings(**settings_overrides)
        monkeypatch.setattr(ov_module, "settings", settings)
        return TrustedOriginMiddleware(app=MagicMock())

    async def test_allowed_host_with_port_passes(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        mw = self._mw(monkeypatch, env="production", allowed_hosts=["real.example"])
        request = make_request(headers={"Host": "real.example:8443"})
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 200

    async def test_subdomain_of_allowed_host_passes(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        mw = self._mw(monkeypatch, env="production", allowed_hosts=["real.example"])
        request = make_request(headers={"Host": "api.real.example"})
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 200

    async def test_testserver_host_always_allowed(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        mw = self._mw(monkeypatch, env="production", allowed_hosts=[])
        request = make_request(headers={"Host": "testserver:9999"})
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 200

    async def test_local_env_allows_localhost_and_127(self, monkeypatch):
        monkeypatch.setenv("ENV", "local")
        mw = self._mw(monkeypatch, env="local", allowed_hosts=[])
        for host in ("localhost:3000", "127.0.0.1:5173"):
            request = make_request(headers={"Host": host})
            response = await mw.dispatch(request, call_next_handler)
            assert response.status_code == 200, host

    async def test_tampered_host_blocked_403(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        mw = self._mw(monkeypatch, env="production", allowed_hosts=["real.example"])
        request = make_request(headers={"Host": "evil.example"})
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 403
        assert "Host verification failure" in response_body(response)

    async def test_missing_host_header_skips_host_check(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        mw = self._mw(monkeypatch, env="production", allowed_hosts=["real.example"])
        request = make_request()  # no Host header in scope
        response = await mw.dispatch(request, call_next_handler)
        assert response.status_code == 200


class TestDispatchSecurityHeaders:
    def _mw(self, monkeypatch, **settings_overrides):
        settings = make_fake_settings(**settings_overrides)
        monkeypatch.setattr(ov_module, "settings", settings)
        return TrustedOriginMiddleware(app=MagicMock())

    async def test_security_headers_http(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        mw = self._mw(monkeypatch, env="production", allowed_hosts=[])
        request = make_request(headers={"Host": "testserver"})
        response = await mw.dispatch(request, call_next_handler)
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "SAMEORIGIN"
        assert response.headers["x-xss-protection"] == "1; mode=block"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "strict-transport-security" not in response.headers

    async def test_security_headers_https_adds_hsts(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        mw = self._mw(monkeypatch, env="production", allowed_hosts=[])
        request = make_request(scheme="https", headers={"Host": "testserver"})
        response = await mw.dispatch(request, call_next_handler)
        assert response.headers["strict-transport-security"] == (
            "max-age=31536000; includeSubDomains"
        )

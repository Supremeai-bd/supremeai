"""Zero-hardcode policy tests for ALLOWED_HOSTS (final-test/zero-hardcode-reconciliation).

REGRESSION BACKGROUND: ``validate_allowed_hosts`` used to append the bare
``"onrender.com"`` apex as a last-resort fallback when running on Render without
a discoverable per-service hostname. ``TrustedOriginMiddleware`` matches Host
headers by exact value OR suffix (``endswith("." + h)``), so the bare apex entry
trusted EVERY ``*.onrender.com`` subdomain — including attacker-registered ones.
The fallback is now removed (fail-closed) and explicitly-configured bare platform
apex domains are rejected outright.

Contract locked in here:

1. Explicit production hosts parse and keep real per-service names.
2. Loopback/dev entries are stripped in production/staging.
3. Platform discovery derives REAL per-service hostnames
   (RENDER_EXTERNAL_URL, RENDER_SERVICE_NAME).
4. The bare-apex fallback is gone: Render without metadata can no longer
   produce "onrender.com" in ALLOWED_HOSTS.
5. Explicit bare platform apex domains are rejected (fail fast).
6. Real-boot subprocess probes prove the fail-fast behaviour outside pytest
   (the in-process pytest placeholder escape returns "testserver" and must
   never leak the apex either).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.config import Settings

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROD_JWT = "p" * 64

PLATFORM_VARS = (
    "ALLOWED_HOSTS",
    "RENDER",
    "RENDER_SERVICE_ID",
    "RENDER_SERVICE_NAME",
    "RENDER_EXTERNAL_URL",
    "RENDER_EXTERNAL_HOSTNAME",
    "VERCEL_URL",
    "VERCEL_BRANCH_URL",
)


@pytest.fixture(autouse=True)
def _clean_platform_env(monkeypatch):
    """Isolate tests from sandbox/CI platform-metadata leakage."""
    for var in PLATFORM_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SUPREMEAI_JWT_SECRET", PROD_JWT)


def _prod_settings(monkeypatch, **kwargs) -> Settings:
    """Trigger production semantics the way real boot does: the ENV env var.

    NOTE: the ``env`` field is declared in the Settings class body, which
    pydantic validates AFTER the mixin fields (incl. allowed_hosts), so a
    ``Settings(env=...)`` kwarg never reaches ``info.data`` inside
    ``validate_allowed_hosts``. Real boots drive this via ENV, and so do these
    tests.
    """
    monkeypatch.setenv("ENV", "production")
    return Settings(**kwargs)


# ---------------------------------------------------------------------------
# 1. Explicit hosts parse + loopback stripping
# ---------------------------------------------------------------------------


def test_prod_explicit_hosts_preserved(monkeypatch):
    settings = _prod_settings(monkeypatch, ALLOWED_HOSTS=["api.example.com", "www.example.com"])
    assert settings.allowed_hosts == ["api.example.com", "www.example.com"]


def test_prod_loopback_entries_stripped(monkeypatch):
    settings = _prod_settings(
        monkeypatch,
        ALLOWED_HOSTS=["localhost", "127.0.0.1", "0.0.0.0", "api.example.com"],
    )
    assert settings.allowed_hosts == ["api.example.com"]


# ---------------------------------------------------------------------------
# 2. Platform discovery derives REAL per-service hostnames
# ---------------------------------------------------------------------------


def test_prod_render_external_url_derived(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://supremeai-api.onrender.com/")
    settings = _prod_settings(monkeypatch, ALLOWED_HOSTS=[])
    assert settings.allowed_hosts == ["supremeai-api.onrender.com"]


def test_prod_render_service_name_derived(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_SERVICE_NAME", "supremeai-api")
    settings = _prod_settings(monkeypatch, ALLOWED_HOSTS=[])
    assert settings.allowed_hosts == ["supremeai-api.onrender.com"]


# ---------------------------------------------------------------------------
# 3. Bare-apex fallback REMOVED (core regression)
# ---------------------------------------------------------------------------


def test_bare_apex_fallback_removed(monkeypatch):
    """Render w/o metadata must NOT produce "onrender.com" in allowed_hosts.

    Under pytest the dedicated test-only placeholder ("testserver") is returned
    instead of failing fast — the important assertion is that the bare apex can
    never reappear in the trusted-host set.
    """
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
    settings = _prod_settings(monkeypatch, ALLOWED_HOSTS=[])
    assert "onrender.com" not in settings.allowed_hosts
    assert settings.allowed_hosts == ["testserver"]


def test_pytest_placeholder_does_not_leak_apex(monkeypatch):
    monkeypatch.setenv("RENDER_SERVICE_ID", "rs-123")
    settings = _prod_settings(monkeypatch, ALLOWED_HOSTS=[])
    assert settings.allowed_hosts == ["testserver"]


# ---------------------------------------------------------------------------
# 4. Explicit bare platform apex domains are rejected (fail fast)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("apex", "other"),
    [
        ("onrender.com", []),
        ("ONRENDER.COM", []),
        ("vercel.app", []),
        ("netlify.app", ["api.example.com"]),
    ],
)
def test_explicit_bare_apex_rejected(monkeypatch, apex, other):
    with pytest.raises(ValueError, match="platform apex"):
        _prod_settings(monkeypatch, ALLOWED_HOSTS=[*other, apex])


def test_subdomain_entries_still_allowed(monkeypatch):
    """Only the bare apex is forbidden — real per-service subdomains stay valid."""
    settings = _prod_settings(
        monkeypatch, ALLOWED_HOSTS=["supremeai-a.web.app", "my-app.vercel.app"]
    )
    assert settings.allowed_hosts == ["supremeai-a.web.app", "my-app.vercel.app"]


# ---------------------------------------------------------------------------
# 5. Real-boot subprocess probes (bypass the pytest "testserver" escape)
# ---------------------------------------------------------------------------


def _boot_env(**extra) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in PLATFORM_VARS}
    # Strip the pytest escape hatches so Settings sees a real boot.
    for k in ("ENV", "TESTING", "CI", "PYTEST_CURRENT_TEST", "DATABASE_URL", "TEST_DATABASE_URL"):
        env.pop(k, None)
    env["ENV"] = "production"
    env["SUPREMEAI_JWT_SECRET"] = PROD_JWT
    # Minimal complete production env (verified by the boot probes below).
    env["ENCRYPTION_KEY"] = "k" * 32
    # P0 fail-closed admin secret (>=12 chars, not the dev fallback, and never
    # equal to SUPREMEAI_DOCS_PASSWORD which this minimal env does not set):
    # without it the #297 boot validator rejects every probe before the
    # ALLOWED_HOSTS policy under test can even run.
    env["SUPREMEAI_ADMIN_SECRET"] = "boot-probe-admin-secret-0123456789"
    env["SUPABASE_URL"] = "https://proj.supabase.co"
    env["SUPABASE_KEY"] = "sb-key-123"
    env["SUPABASE_SERVICE_ROLE_KEY"] = "sb-role-456"
    env["FIREBASE_SERVICE_ACCOUNT_JSON"] = '{"type":"service_account"}'
    env["SUPREMEAI_API_KEY"] = "sk-boot-probe-supremeai-api-key-12345"
    env["SUPREMEAI_ADMIN_PASSWORD_HASH"] = "boot-probe-admin-password-hash"
    env["CI_WEBHOOK_SECRET"] = "boot-probe-ci-webhook-secret-0123456789"
    env["SUPABASE_DATABASE_URL_POOLER"] = "postgresql://u:p@db.example.com:5432/supremeai"
    env.setdefault("DATABASE_URL", "postgresql://u:p@db.example.com:5432/supremeai")
    env.setdefault("REDIS_URL", "redis://u:p@cache.example.com:6379")
    env["PYTHONPATH"] = str(BACKEND_DIR)
    env.update(extra)
    return env


def _boot(
    settings_expr: str = "from core.config import settings", **env_extra
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", settings_expr],
        cwd=str(BACKEND_DIR),
        env=_boot_env(**env_extra),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_real_boot_without_hosts_fails_fast():
    """Production boot with no ALLOWED_HOSTS and no platform metadata exits nonzero."""
    proc = _boot(ALLOWED_HOSTS="")
    assert proc.returncode != 0, f"expected fail-fast boot, got: {proc.stdout!r}"
    assert "ALLOWED_HOSTS" in (proc.stderr or "")


def test_real_boot_with_explicit_hosts_succeeds():
    proc = _boot(
        'from core.config import settings; print("HOSTS=" + ",".join(settings.allowed_hosts))',
        ALLOWED_HOSTS="api.example.com",
    )
    # The boot must reach the marker; ALLOWED_HOSTS was provided explicitly.
    marker_lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("HOSTS=")]
    if proc.returncode != 0:
        pytest.fail(f"real boot failed unexpectedly:\n{proc.stderr[-2000:]}")
    assert marker_lines, proc.stdout
    assert "api.example.com" in marker_lines[-1]


def test_real_boot_explicit_apex_rejected():
    env = _boot_env(ALLOWED_HOSTS="onrender.com")
    proc = subprocess.run(
        [sys.executable, "-c", "from core.config import settings"],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode != 0
    assert "platform apex" in (proc.stderr or "")

"""Vault-cache regressions for `gateway/service/admin_auth.py`.

The pre-fix behaviour was three bugs in one function:

1. **No TTL.** `_vault_cache` was a plain dict that only ever grew, so a rotated
   secret was served from memory until the process restarted.
2. **No negative cache.** Every request for an *unset* secret re-ran the full
   Infisical universal-auth login + fetch (two blocking HTTP calls, up to 20 s)
   inside an `async def` handler — one slow vault stalled every chat request.
3. **No single-flight.** Concurrent admin requests each opened their own
   login+fetch round trip.

These tests pin the fixed behaviour without any network.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _admin_auth_module():
    path = REPO_ROOT / "gateway" / "service" / "admin_auth.py"
    spec = importlib.util.spec_from_file_location("supremeai_admin_auth_vault_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeVault:
    """Stands in for urllib.request.urlopen, counting round trips."""

    def __init__(self, secrets: dict[str, str]):
        self.secrets = secrets
        self.calls = 0

    def __call__(self, request, timeout=None):
        self.calls += 1
        url = request.full_url
        if "universal-auth/login" in url:
            return _Resp({"accessToken": "token-abc"})
        return _Resp(
            {"secrets": [{"secretKey": k, "secretValue": v} for k, v in self.secrets.items()]}
        )


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self, *_args):
        return json.dumps(self._payload).encode()

    def close(self):
        pass


@pytest.fixture
def auth(monkeypatch):
    # The module promotes fetched secrets into os.environ (a real production
    # behaviour). Snapshot and restore it so one test's "vault" cannot leak a
    # TOTP secret into the next module's login test.
    import os

    before = dict(os.environ)
    module = _admin_auth_module()
    monkeypatch.setenv("INFISICAL_CLIENT_ID", "cid")
    monkeypatch.setenv("INFISICAL_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("INFISICAL_PROJECT_ID", "pid")
    monkeypatch.setenv("INFISICAL_CACHE_TTL", "300")
    monkeypatch.setenv("INFISICAL_MISS_TTL", "30")
    module._vault_cache.clear()
    module._vault_misses.clear()
    module._vault_promoted.clear()
    yield module
    os.environ.clear()
    os.environ.update(before)
    module._vault_cache.clear()
    module._vault_misses.clear()
    module._vault_promoted.clear()


def test_env_var_wins_and_never_hits_the_vault(auth, monkeypatch):
    fake = _FakeVault({"SUPREMEAI_JWT_SECRET": "from-vault"})
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setenv("SUPREMEAI_JWT_SECRET", " from-env ")
    assert auth.get_vault_secret("SUPREMEAI_JWT_SECRET") == "from-env"
    assert fake.calls == 0


def test_miss_is_negative_cached_so_the_vault_is_asked_once(auth, monkeypatch):
    fake = _FakeVault({})  # vault has nothing
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert auth.get_vault_secret("NOT_THERE") is None
    assert auth.get_vault_secret("NOT_THERE") is None
    assert auth.get_vault_secret("NOT_THERE") is None
    assert fake.calls == 2, "one login + one fetch, then the negative cache answers"


def test_hit_is_cached_until_ttl_expires(auth, monkeypatch):
    fake = _FakeVault({"SUPREMEAI_ADMIN_TOTP_SECRET": "totp-secret"})
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert auth.get_vault_secret("SUPREMEAI_ADMIN_TOTP_SECRET") == "totp-secret"
    calls_after_first = fake.calls
    assert auth.get_vault_secret("SUPREMEAI_ADMIN_TOTP_SECRET") == "totp-secret"
    assert fake.calls == calls_after_first

    # Expire the entry: the next read must re-fetch (secret rotation).
    key = "SUPREMEAI_ADMIN_TOTP_SECRET"
    value, _ = auth._vault_cache[key]
    auth._vault_cache[key] = (value, value and 0.0)  # fetched at epoch 0 => stale
    fake.secrets[key] = "rotated"
    assert auth.get_vault_secret(key) == "rotated"


def test_transport_failure_is_not_negative_cached(auth, monkeypatch):
    def boom(request, timeout=None):
        raise OSError("vault unreachable")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert auth.get_vault_secret("WHATEVER") is None
    assert "WHATEVER" not in auth._vault_misses, "a transport error must be retried, not cached"


@pytest.mark.asyncio
async def test_async_wrapper_offloads_the_blocking_fetch(auth, monkeypatch):
    fake = _FakeVault({"SUPABASE_URL": "https://project.supabase.co"})
    monkeypatch.setattr(urllib.request, "urlopen", fake)

    # Runs the blocking urlopen in a worker thread, so the event loop stays free.
    assert await auth.get_vault_secret_async("SUPABASE_URL") == "https://project.supabase.co"
    assert fake.calls == 2


@pytest.mark.asyncio
async def test_supabase_base_url_is_awaitable(auth, monkeypatch):
    fake = _FakeVault({"SUPABASE_URL": "https://project.supabase.co/"})
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert await auth._supabase_base_url() == "https://project.supabase.co"

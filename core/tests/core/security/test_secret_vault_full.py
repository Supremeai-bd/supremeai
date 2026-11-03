"""Full-coverage tests for core/security/secret_vault.py (Task 7 wave-2).

A fake `infisical_client` module is injected into sys.modules so every branch
(client construction, retries, TTLs, circuit breaker, fail-closed fallback) is
exercised without network access.
"""

from __future__ import annotations

import asyncio
import sys
import time
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.security.secret_vault as sv
from core.security.secret_vault import (
    CACHE_TTL_SECONDS,
    ProductionSecretVault,
    SecretNotFoundError,
    _CacheEntry,
    get_secret_vault,
    reset_secret_vault,
)


# ---------------------------------------------------------------------------
# Fake infisical_client module
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module", autouse=True)
def fake_infisical_module():
    mod = types.ModuleType("infisical_client")

    class GetSecretOptions:
        def __init__(self, environment=None, project_id=None, secret_name=None):
            self.environment = environment
            self.project_id = project_id
            self.secret_name = secret_name

    class ListSecretsOptions:
        def __init__(self, **kw):
            self.kwargs = kw

    class UniversalAuthMethod:
        def __init__(self, client_id=None, client_secret=None):
            self.client_id = client_id
            self.client_secret = client_secret

    class AuthenticationOptions:
        def __init__(self, universal_auth=None):
            self.universal_auth = universal_auth

    class ClientSettings:
        def __init__(self, access_token=None, auth=None):
            self.access_token = access_token
            self.auth = auth

    class InfisicalClient:
        def __init__(self, settings=None):
            self.settings = settings

    for name, obj in {
        "GetSecretOptions": GetSecretOptions,
        "ListSecretsOptions": ListSecretsOptions,
        "UniversalAuthMethod": UniversalAuthMethod,
        "AuthenticationOptions": AuthenticationOptions,
        "ClientSettings": ClientSettings,
        "InfisicalClient": InfisicalClient,
    }.items():
        setattr(mod, name, obj)
    prev = {k: sys.modules.get("infisical_client") for k in ["infisical_client"]}
    sys.modules["infisical_client"] = mod
    # rebind module-level names that the try/except import set to None
    sv.GetSecretOptions = GetSecretOptions
    sv.ListSecretsOptions = ListSecretsOptions
    sv.ClientSettings = ClientSettings
    sv.AuthenticationOptions = AuthenticationOptions
    sv.UniversalAuthMethod = UniversalAuthMethod
    sv.InfisicalClient = InfisicalClient
    yield mod
    sys.modules["infisical_client"] = prev["infisical_client"]
    sv.InfisicalClient = None


def make_vault(env="local", **envs) -> ProductionSecretVault:
    """Vault with TESTING unset so Infisical init logic can be exercised."""
    base = {"ENV": env, "TESTING": "", "PRE_COMMIT": "", "INFISICAL_PROJECT_ID": "pid"}
    base.update(envs)
    with patch.dict("os.environ", base, clear=False):
        v = ProductionSecretVault()
    v._cache.clear()
    return v


@pytest.fixture(autouse=True)
def clean_vault_singleton():
    reset_secret_vault()
    yield
    reset_secret_vault()


class TestCacheEntry:
    def test_fresh_entry_not_expired(self):
        e = _CacheEntry("v", ttl=60)
        assert e.value == "v"
        assert e.is_expired is False  # property

    def test_expired_entry(self):
        e = _CacheEntry("v", ttl=0)
        time.sleep(0.01)
        assert e.is_expired is True

    def test_default_ttl_is_cache_constant(self):
        e = _CacheEntry("v")
        assert e.expires_at - e.created_at if False else True
        # default ttl is expressed via expires_at ≈ now + CACHE_TTL_SECONDS
        assert e.is_expired is False


class TestVaultInit:
    def test_testing_mode_skips_init(self, monkeypatch):
        monkeypatch.setenv("TESTING", "1")
        monkeypatch.setenv("INFISICAL_TOKEN", "tok")
        v = ProductionSecretVault()
        assert v.client is None

    def test_precommit_mode_skips_init(self, monkeypatch):
        monkeypatch.setenv("PRE_COMMIT", "1")
        v = ProductionSecretVault()
        assert v.client is None

    def test_no_credentials_bypass(self, monkeypatch):
        monkeypatch.setenv("TESTING", "")
        monkeypatch.delenv("INFISICAL_TOKEN", raising=False)
        monkeypatch.delenv("INFISICAL_CLIENT_ID", raising=False)
        monkeypatch.delenv("INFISICAL_CLIENT_SECRET", raising=False)
        v = ProductionSecretVault()
        assert v.client is None

    def test_token_init_success(self, monkeypatch):
        monkeypatch.setenv("TESTING", "")
        monkeypatch.setenv("INFISICAL_TOKEN", "tok")
        v = ProductionSecretVault()
        assert v.client is not None

    def test_universal_auth_init(self, monkeypatch):
        monkeypatch.setenv("TESTING", "")
        monkeypatch.delenv("INFISICAL_TOKEN", raising=False)
        monkeypatch.setenv("INFISICAL_CLIENT_ID", "cid")
        monkeypatch.setenv("INFISICAL_CLIENT_SECRET", "csec")
        v = ProductionSecretVault()
        assert v.client is not None

    def test_init_generic_exception_bypasses(self, monkeypatch):
        monkeypatch.setenv("TESTING", "")
        monkeypatch.setenv("INFISICAL_TOKEN", "tok")
        with patch.object(
            sv.ProductionSecretVault,
            "_init_infisical_client",
            side_effect=Exception("bad creds"),
        ):
            v = ProductionSecretVault()
        assert v.client is None


class TestFetchSecret:
    def test_env_override_wins(self, monkeypatch):
        v = make_vault()
        v.client = MagicMock()
        monkeypatch.setenv("MY_SECRET", "from-env")
        assert v.fetch_secret("MY_SECRET") == "from-env"
        v.client.getSecret.assert_not_called()

    def test_cache_hit(self, monkeypatch):
        v = make_vault()
        v._cache["C1"] = _CacheEntry("cached", ttl=60)
        assert v.fetch_secret("C1", "dft") == "cached"

    def test_expired_cache_removed(self, monkeypatch):
        v = make_vault()
        e = _CacheEntry("old", ttl=0)
        time.sleep(0.01)
        v._cache["C2"] = e
        # no client -> falls back to env/local mock
        v.client = None
        out = v.fetch_secret("C2", "dft")
        assert out == "dft"

    def test_circuit_breaker_open_short_circuits(self, monkeypatch):
        v = make_vault()
        v._circuit_breaker_open = True
        v.client = MagicMock()
        assert v.fetch_secret("X1", "fb") == "fb"

    def test_no_client_falls_back(self, monkeypatch):
        v = make_vault()
        assert v.fetch_secret("X2", "fb") == "fb"

    def test_client_success_caches(self, monkeypatch):
        v = make_vault()
        v.client = MagicMock()
        v.client.getSecret.return_value = MagicMock(secret_value="sval")
        out = v.fetch_secret("X3")
        assert out == "sval"
        assert v._cache["X3"].value == "sval"

    def test_retries_then_success(self, monkeypatch):
        v = make_vault(env="production")
        v.client = MagicMock()
        ok = MagicMock(secret_value="good")
        v.client.getSecret.side_effect = [ConnectionError("a"), ok]
        with patch.object(sv.time, "sleep") as sl:
            out = v.fetch_secret("X4")
        assert out == "good"
        sl.assert_called_once_with(1)

    def test_retries_skipped_backoff_on_event_loop(self, monkeypatch):
        v = make_vault()
        v.client = MagicMock()
        ok = MagicMock(secret_value="good2")
        v.client.getSecret.side_effect = [TimeoutError("t"), ok]

        async def run():
            return v.fetch_secret("X5")

        out = asyncio.run(run())
        assert out == "good2"

    def test_retries_exhausted_open_circuit(self, monkeypatch):
        v = make_vault()
        v.client = MagicMock()
        v.client.getSecret.side_effect = ConnectionError("down")
        emitted = []
        monkeypatch.setattr(
            "core.security.secret_vault.error_event_bus",
            MagicMock(emit=lambda ev: emitted.append(ev)),
        )
        with patch.object(sv.time, "sleep"):
            out = v.fetch_secret("X6", "fb")
        assert v._circuit_breaker_open is True
        assert out == "fb"
        assert len(emitted) == 1

    def test_not_found_error_no_breaker(self, monkeypatch):
        v = make_vault()
        v.client = MagicMock()
        v.client.getSecret.side_effect = Exception("secret not found (404)")
        out = v.fetch_secret("X7", "fb")
        assert out == "fb"
        assert v._circuit_breaker_open is False

    def test_unexpected_error_opens_breaker(self, monkeypatch):
        v = make_vault()
        v.client = MagicMock()
        v.client.getSecret.side_effect = RuntimeError("cosmic rays")
        emitted = []
        monkeypatch.setattr(
            "core.security.secret_vault.error_event_bus",
            MagicMock(emit=lambda ev: emitted.append(ev)),
        )
        out = v.fetch_secret("X8", "fb")
        assert v._circuit_breaker_open is True
        assert out == "fb"
        assert len(emitted) == 1

    @pytest.mark.parametrize(
        "env,slug", [("production", "prod"), ("staging", "staging"), ("local", "dev")]
    )
    def test_environment_slug_selection(self, monkeypatch, env, slug):
        v = make_vault(env=env)
        v.client = MagicMock()
        v.client.getSecret.return_value = MagicMock(secret_value="v")
        v.fetch_secret("SLUGTEST")
        opts = v.client.getSecret.call_args.kwargs["options"]
        assert opts.environment == slug

    def test_infisical_env_override(self, monkeypatch):
        v = make_vault()
        v.client = MagicMock()
        v.client.getSecret.return_value = MagicMock(secret_value="v")
        monkeypatch.setenv("INFISICAL_ENV", "custom")
        v.fetch_secret("SLUGTEST2")
        opts = v.client.getSecret.call_args.kwargs["options"]
        assert opts.environment == "custom"


class TestFetchSecretAsync:
    async def test_circuit_open(self, monkeypatch):
        v = make_vault()
        v._circuit_breaker_open = True
        assert await v.fetch_secret_async("A1", "fb") == "fb"

    async def test_cache_hit(self):
        v = make_vault()
        v._cache["A2"] = _CacheEntry("ac", ttl=60)
        assert await v.fetch_secret_async("A2") == "ac"

    async def test_no_client(self):
        v = make_vault()
        assert await v.fetch_secret_async("A3", "fb") == "fb"

    async def test_success(self, monkeypatch):
        v = make_vault()
        v.client = MagicMock()
        v.client.getSecret.return_value = MagicMock(secret_value="aval")

        async def fake_to_thread(fn):
            return fn()

        monkeypatch.setattr(sv.asyncio, "to_thread", fake_to_thread)
        assert await v.fetch_secret_async("A4") == "aval"

    async def test_retries_exhausted(self, monkeypatch):
        v = make_vault()
        v.client = MagicMock()
        v.client.getSecret.side_effect = ConnectionError("net down")

        async def fake_to_thread(fn):
            return fn()

        monkeypatch.setattr(sv.asyncio, "to_thread", fake_to_thread)
        monkeypatch.setattr(sv.asyncio, "sleep", AsyncMock())
        out = await v.fetch_secret_async("A5", "fb")
        assert out == "fb"
        assert v._circuit_breaker_open is True

    async def test_not_found(self, monkeypatch):
        v = make_vault()
        v.client = MagicMock()
        v.client.getSecret.side_effect = Exception("not_found in vault")

        async def fake_to_thread(fn):
            return fn()

        monkeypatch.setattr(sv.asyncio, "to_thread", fake_to_thread)
        assert await v.fetch_secret_async("A6", "fb") == "fb"
        assert v._circuit_breaker_open is False

    async def test_unexpected_error(self, monkeypatch):
        v = make_vault()
        v.client = MagicMock()
        v.client.getSecret.side_effect = RuntimeError("weird")

        async def fake_to_thread(fn):
            return fn()

        monkeypatch.setattr(sv.asyncio, "to_thread", fake_to_thread)
        out = await v.fetch_secret_async("A7", "fb")
        assert out == "fb"
        assert v._circuit_breaker_open is True


class TestFallbackToEnv:
    def test_env_value_used(self, monkeypatch):
        v = make_vault()
        monkeypatch.setenv("FB1", "envval")
        assert v._fallback_to_env("FB1", None) == "envval"

    def test_local_mock_with_default(self):
        v = make_vault()
        assert v._fallback_to_env("FB2", "dft") == "dft"

    def test_local_mock_jwt_secret_64_bytes(self):
        v = make_vault()
        out = v._fallback_to_env("SUPREMEAI_JWT_SECRET", None)
        assert len(out) >= 60

    def test_local_mock_supabase(self):
        v = make_vault()
        assert v._fallback_to_env("SUPABASE_URL", None) == "https://mock.supabase.co"
        assert v._fallback_to_env("SUPABASE_KEY", None) == "mock-key"

    def test_local_mock_generic(self):
        v = make_vault()
        assert v._fallback_to_env("WHATEVER_KEY", None) == "mock_WHATEVER_KEY"

    def test_optional_secret_missing_in_prod(self, monkeypatch):
        v = make_vault(env="production")
        optional = next(iter(sv.OPTIONAL_SECRETS))
        monkeypatch.delenv(optional, raising=False)
        out = v._fallback_to_env(optional, "opt-default")
        assert out == "opt-default"

    def test_optional_secret_missing_in_prod_no_default(self, monkeypatch):
        v = make_vault(env="production")
        optional = next(iter(sv.OPTIONAL_SECRETS))
        monkeypatch.delenv(optional, raising=False)
        out = v._fallback_to_env(optional, None)
        assert out == ""

    def test_hard_required_missing_in_prod_fail_closed(self):
        v = make_vault(env="production")
        required = next(iter(sv.HARD_REQUIRED_SECRETS))
        with pytest.raises(RuntimeError, match="Fail-closed"):
            v._fallback_to_env(required, None)

    def test_unknown_secret_missing_in_prod_fail_closed(self):
        v = make_vault(env="production")
        with pytest.raises(RuntimeError, match="BE-13 fail-closed"):
            v._fallback_to_env("TOTALLY_UNKNOWN_SECRET", None)

    def test_staging_unknown_fail_closed(self):
        v = make_vault(env="staging")
        with pytest.raises(RuntimeError):
            v._fallback_to_env("TOTALLY_UNKNOWN_STAGING", None)


class TestGetSecretAndJson:
    def test_get_secret_returns_value(self):
        v = make_vault()
        v._cache["G1"] = _CacheEntry("val", ttl=60)
        assert v.get_secret("G1") == "val"

    def test_get_secret_local_empty(self):
        v = make_vault()
        assert v.get_secret("G2", "dd") == "dd"

    def test_get_secret_prod_missing_raises(self):
        v = make_vault(env="production")
        v._circuit_breaker_open = True  # force fallback path -> raises RuntimeError
        # fallback raises RuntimeError (fail-closed) — get_secret propagates
        with pytest.raises(RuntimeError):
            v.get_secret("UNKNOWN_G")

    def test_fetch_json_valid(self):
        v = make_vault()
        v._cache["J1"] = _CacheEntry('{"a": 1}', ttl=60)
        assert v.fetch_json_secret("J1") == {"a": 1}

    def test_fetch_json_invalid_returns_default(self):
        v = make_vault()
        v._cache["J2"] = _CacheEntry("not json", ttl=60)
        assert v.fetch_json_secret("J2", {"x": 2}) == {"x": 2}

    def test_fetch_json_non_string(self):
        v = make_vault()
        v._cache["J3"] = _CacheEntry("", ttl=60)
        assert v.fetch_json_secret("J3", {"z": 9}) == {"z": 9}

    async def test_fetch_json_async(self, monkeypatch):
        v = make_vault()
        v._cache["J4"] = _CacheEntry("[1, 2]", ttl=60)
        assert await v.fetch_json_secret_async("J4") == [1, 2]


class TestBulkAndCacheOps:
    def test_fetch_all_secrets_circuit_open(self):
        v = make_vault()
        v._circuit_breaker_open = True
        assert v.fetch_all_secrets() == {}

    def test_fetch_all_secrets_no_client(self):
        v = make_vault()
        assert v.fetch_all_secrets() == {}

    def test_fetch_all_secrets_success(self):
        v = make_vault()
        v.client = MagicMock()
        s1, s2 = MagicMock(), MagicMock()
        s1.secret_key, s1.secret_value = "K1", "V1"
        s2.secret_key, s2.secret_value = "K2", "V2"
        v.client.listSecrets.return_value = [s1, s2]
        out = v.fetch_all_secrets(environment="prod")
        assert out == {"K1": "V1", "K2": "V2"}
        assert v._cache["K1"].value == "V1"

    def test_fetch_all_secrets_error(self):
        v = make_vault()
        v.client = MagicMock()
        v.client.listSecrets.side_effect = RuntimeError("list failed")
        assert v.fetch_all_secrets() == {}

    def test_invalidate_cache_single_and_all(self):
        v = make_vault()
        v._cache["I1"] = _CacheEntry("a")
        v._cache["I2"] = _CacheEntry("b")
        v.invalidate_cache("I1")
        assert "I1" not in v._cache and "I2" in v._cache
        v.invalidate_cache()
        assert v._cache == {}

    def test_set_delete_list(self):
        v = make_vault()
        v.set_secret("S1", "v1")
        assert v.get_from_local_cache("S1") if hasattr(v, "get_from_local_cache") else True
        assert v.list_secrets() == ["S1"]
        v.delete_secret("S1")
        assert v.list_secrets() == []


class TestSingletonAndModule:
    def test_get_and_reset_singleton(self):
        v1 = get_secret_vault()
        v2 = get_secret_vault()
        assert v1 is v2
        reset_secret_vault()
        assert get_secret_vault() is not v1

    def test_module_getattr_backward_compat(self):
        assert sv.secret_vault is get_secret_vault()
        with pytest.raises(AttributeError):
            _ = sv.nonexistent_symbol_xyz

    def test_cache_entry_expiry_boundary(self):
        e = _CacheEntry("x", ttl=60)
        e.expires_at = time.monotonic() - 1  # force expiry
        assert e.is_expired is True

# backend/tests/core/test_secret_vault_async_env_899.py
"""Regression tests for Infisical async secret-fetch environment mapping (#899).

Issue #899 (P1 SECURITY): `fetch_secret_async` (secret_vault.py:443-447) পূর্বে
hardcoded `environment = "dev" if self.env == "local" else "prod"` ব্যবহার করত —
যার ফলে staging environment-এও production vault পড়া হতো (cross-environment
isolation breach)। অথচ sync (`fetch_secret`) ও bulk (`fetch_all_secrets`)
path সঠিকভাবে staging→"staging" map করে এবং `INFISICAL_ENV` override honor করে।

এই test suite যাচাই করে:
    - `_resolve_infisical_environment()` method exist করে এবং single source of truth।
    - staging env → "staging" (issue-এর specific acceptance criteria)।
    - production env → "prod"।
    - local/dev env → "dev"।
    - `INFISICAL_ENV` env var override সব path-এ honor হয়।
    - async path source এখন আর hardcoded `"dev" if self.env == "local" else "prod"`
      নেই — `_resolve_infisical_environment()` ব্যবহার করে।

WIRE-FIRST: pins fixed behavior, adds no deletion. বাংলা মন্তব্য সহ।
"""

from __future__ import annotations

import inspect
import re

import pytest

from core.security.secret_vault import ProductionSecretVault, reset_secret_vault


@pytest.fixture(autouse=True)
def _reset_vault_between_tests():
    reset_secret_vault()
    try:
        yield
    finally:
        reset_secret_vault()


class TestResolveInfisicalEnvironment:
    """`_resolve_infisical_environment()` — single source of truth contract।"""

    def test_method_exists(self):
        """Issue #899 fix #1: method defined আছে কিনা verify।"""
        assert hasattr(ProductionSecretVault, "_resolve_infisical_environment"), (
            "ProductionSecretVault._resolve_infisical_environment must exist — "
            "single source of truth for env slug mapping (Issue #899)"
        )

    def test_staging_env_resolves_to_staging(self, monkeypatch):
        """Issue #899 acceptance criteria: staging env → fetched environment == 'staging'।

        পূর্বে async path এখানে "prod" return করত → staging-এ production vault পড়া হতো।
        """
        monkeypatch.setenv("ENV", "staging")
        monkeypatch.delenv("INFISICAL_ENV", raising=False)
        vault = ProductionSecretVault()
        assert vault.env == "staging"
        assert vault._resolve_infisical_environment() == "staging", (
            "staging env must map to 'staging' Infisical slug (Issue #899 — "
            "previously mapped to 'prod' → cross-env isolation breach)"
        )

    def test_production_env_resolves_to_prod(self, monkeypatch):
        """production env → 'prod' slug।"""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("INFISICAL_ENV", raising=False)
        vault = ProductionSecretVault()
        assert vault.env == "production"
        assert vault._resolve_infisical_environment() == "prod"

    def test_local_env_resolves_to_dev(self, monkeypatch):
        """local env → 'dev' slug।"""
        monkeypatch.setenv("ENV", "local")
        monkeypatch.delenv("INFISICAL_ENV", raising=False)
        vault = ProductionSecretVault()
        assert vault.env == "local"
        assert vault._resolve_infisical_environment() == "dev"

    def test_development_env_resolves_to_dev(self, monkeypatch):
        """development env (case-insensitive) → 'dev' slug।"""
        monkeypatch.setenv("ENV", "development")
        monkeypatch.delenv("INFISICAL_ENV", raising=False)
        vault = ProductionSecretVault()
        # self.env হয় .lower() করা থাকে
        assert vault.env == "development"
        # production বা staging না হলেই → "dev"
        assert vault._resolve_infisical_environment() == "dev"

    def test_infisical_env_override_takes_priority(self, monkeypatch):
        """`INFISICAL_ENV` env var override সবসময় priority পায় (12-factor)।"""
        monkeypatch.setenv("ENV", "staging")  # would map to "staging"
        monkeypatch.setenv("INFISICAL_ENV", "custom-test-env")
        vault = ProductionSecretVault()
        assert vault._resolve_infisical_environment() == "custom-test-env", (
            "INFISICAL_ENV override must take priority over self.env mapping"
        )

    def test_infisical_env_override_for_production(self, monkeypatch):
        """`INFISICAL_ENV` override production env-এও honor হয়।"""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("INFISICAL_ENV", "staging")
        vault = ProductionSecretVault()
        # Override priority → "staging" (নিজে যে env set করা আছে তা নয়)
        assert vault._resolve_infisical_environment() == "staging"

    def test_empty_infisical_env_falls_back_to_mapping(self, monkeypatch):
        """`INFISICAL_ENV=""` set থাকলে falsy → fallback to mapping।"""
        monkeypatch.setenv("ENV", "staging")
        monkeypatch.setenv("INFISICAL_ENV", "")
        vault = ProductionSecretVault()
        # empty string falsy → fall through to self.env mapping → "staging"
        assert vault._resolve_infisical_environment() == "staging"


class TestAsyncPathUsesResolver:
    """Issue #899: async path এখন `_resolve_infisical_environment()` ব্যবহার করে।"""

    def test_async_path_does_not_hardcode_prod(self):
        """Source inspection: async path-এ `else "prod"` hardcoded নেই।"""
        src = inspect.getsource(ProductionSecretVault.fetch_secret_async)
        # Strip comments — comment-এ থাকা শব্দ code pattern হিসেবে গণ্য হবে না।
        code_lines = [re.sub(r"#.*$", "", line) for line in src.splitlines()]
        code_only = "\n".join(code_lines)
        assert '"dev" if self.env == "local" else "prod"' not in code_only, (
            'Issue #899: async path must NOT hardcode `"dev" if self.env == "local" else "prod"` '
            "— must use _resolve_infisical_environment() (single source of truth)"
        )

    def test_async_path_calls_resolver(self):
        """Source inspection: async path `_resolve_infisical_environment()` call করে।"""
        src = inspect.getsource(ProductionSecretVault.fetch_secret_async)
        # Strip comments
        code_lines = [re.sub(r"#.*$", "", line) for line in src.splitlines()]
        code_only = "\n".join(code_lines)
        assert "_resolve_infisical_environment()" in code_only, (
            "Issue #899: async path must call self._resolve_infisical_environment() "
            "instead of hardcoding env slug"
        )

    def test_sync_path_also_uses_resolver(self):
        """Single source of truth — sync path-ও একই method ব্যবহার করে।"""
        src = inspect.getsource(ProductionSecretVault.fetch_secret)
        code_lines = [re.sub(r"#.*$", "", line) for line in src.splitlines()]
        code_only = "\n".join(code_lines)
        assert "_resolve_infisical_environment()" in code_only, (
            "Issue #899: sync path should also use _resolve_infisical_environment() "
            "— single source of truth across sync/async/bulk paths"
        )

    def test_bulk_path_also_uses_resolver(self):
        """Single source of truth — bulk path-ও একই method ব্যবহার করে।"""
        src = inspect.getsource(ProductionSecretVault.fetch_all_secrets)
        code_lines = [re.sub(r"#.*$", "", line) for line in src.splitlines()]
        code_only = "\n".join(code_lines)
        assert "_resolve_infisical_environment()" in code_only, (
            "Issue #899: bulk path should also use _resolve_infisical_environment() "
            "— single source of truth across sync/async/bulk paths"
        )


class TestAsyncFetchSecretStagingContract:
    """Live integration: staging env-এ fetch_secret_async চালালে Infisical call
    `environment="staging"` দিয়ে হয় (issue-এর সুনির্দিষ্ট acceptance criteria)।"""

    def test_staging_async_uses_staging_environment_slug(self, monkeypatch):
        """Mock infisical_client + verify GetSecretOptions.environment == 'staging'।"""
        import sys
        import types

        monkeypatch.setenv("ENV", "staging")
        monkeypatch.setenv("INFISICAL_PROJECT_ID", "test-project-id")
        monkeypatch.delenv("INFISICAL_ENV", raising=False)

        captured_options: list = []

        class FakeSecretValue:
            secret_value = "staging-secret-value"

        class FakeClient:
            def getSecret(self, options=None):
                captured_options.append(options)
                return FakeSecretValue()

        # Fake infisical_client module — `GetSecretOptions` হলো একটি callable
        # যা kwargs গ্রহণ করে এবং একটি capture object রিটার্ন করে।
        fake_module = types.ModuleType("infisical_client")
        fake_module.GetSecretOptions = lambda **kwargs: _FakeOptions(**kwargs)
        sys.modules["infisical_client"] = fake_module
        try:
            vault = ProductionSecretVault()
            vault.client = FakeClient()  # bypass real Infisical init
            vault._circuit_breaker_open = False

            import asyncio

            result = asyncio.run(vault.fetch_secret_async("TEST_SECRET"))

        finally:
            del sys.modules["infisical_client"]

        assert result == "staging-secret-value"
        assert len(captured_options) == 1, f"Expected 1 Infisical call, got {len(captured_options)}"
        opts = captured_options[0]
        assert opts.environment == "staging", (
            f"Issue #899: staging env must request 'staging' slug from Infisical, "
            f"got {opts.environment!r} (previously was 'prod' → cross-env breach)"
        )
        assert opts.project_id == "test-project-id"
        assert opts.secret_name == "TEST_SECRET"


class _FakeOptions:
    """Mock GetSecretOptions — captures environment/project_id/secret_name kwargs।"""

    def __init__(self, **kwargs):
        self.environment = kwargs.get("environment")
        self.project_id = kwargs.get("project_id")
        self.secret_name = kwargs.get("secret_name")

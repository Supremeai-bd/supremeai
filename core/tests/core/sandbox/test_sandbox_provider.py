"""Unit tests for SupremeAI Governed Execution Plane & SandboxProvider.
========================================================================
"""

from __future__ import annotations

import os

import pytest

from core.sandbox import (
    CloudSandboxProvider,
    ExecutionResult,
    LocalDevSandboxProvider,
    SandboxConfig,
    SandboxRegistry,
)


def test_sandbox_config_defaults() -> None:
    config = SandboxConfig()
    assert config.timeout_seconds == 30
    assert config.max_output_bytes == 100_000
    assert "python" in config.allowed_languages
    assert config.network_policy == "blocked"


def test_sanitize_environment_strips_secrets() -> None:
    config = SandboxConfig()
    dirty_env = {
        "PATH": "/usr/bin:/bin",
        "DATABASE_URL": "postgresql://user:pass@secret-db:5432/supreme",
        "SUPREMEAI_API_KEY": "sk-secret-token",
        "JWT_SECRET": "top-secret-signing-key",
        "REDIS_URL": "redis://:secret@redis-cache:6379",
        "OPENAI_API_KEY": "sk-openai-token",
        "PUBLIC_APP_ENV": "development",
    }

    clean_env = config.sanitize_environment(dirty_env)

    assert "PATH" in clean_env
    assert "PUBLIC_APP_ENV" in clean_env
    assert "DATABASE_URL" not in clean_env
    assert "SUPREMEAI_API_KEY" not in clean_env
    assert "JWT_SECRET" not in clean_env
    assert "REDIS_URL" not in clean_env
    assert "OPENAI_API_KEY" not in clean_env


@pytest.mark.asyncio
async def test_local_dev_provider_execution() -> None:
    provider = LocalDevSandboxProvider()
    assert provider.provider_name == "local_dev"
    assert provider.is_trusted_boundary is False

    code = "import sys; print('hello from sandbox'); sys.exit(0)"
    result = await provider.execute(code, language="python")

    assert result.success is True
    assert result.exit_code == 0
    assert "hello from sandbox" in result.stdout
    assert result.timed_out is False
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_local_dev_provider_disallowed_language() -> None:
    provider = LocalDevSandboxProvider()
    config = SandboxConfig(allowed_languages=("python",))

    result = await provider.execute("console.log('hi')", language="javascript", config=config)
    assert result.success is False
    assert "not allowed by sandbox policy" in result.stderr


@pytest.mark.asyncio
async def test_local_dev_provider_timeout() -> None:
    provider = LocalDevSandboxProvider()
    config = SandboxConfig(timeout_seconds=1)

    code = "import time; time.sleep(5); print('done')"
    result = await provider.execute(code, language="python", config=config)

    assert result.success is False
    assert result.timed_out is True
    assert "Timed Out" in result.stderr


@pytest.mark.asyncio
async def test_local_dev_provider_output_cap() -> None:
    provider = LocalDevSandboxProvider()
    config = SandboxConfig(max_output_bytes=30)

    code = "print('A' * 200)"
    result = await provider.execute(code, language="python", config=config)

    assert result.success is True
    assert len(result.stdout) <= 30


def test_sandbox_registry_resolution() -> None:
    registry = SandboxRegistry()
    dev_provider = LocalDevSandboxProvider()
    cloud_provider = CloudSandboxProvider(name="mock_cloud")

    registry.register(dev_provider, set_default=True)
    registry.register(cloud_provider)

    assert registry.get() == dev_provider
    assert registry.get("mock_cloud") == cloud_provider
    assert "local_dev" in registry.list_providers()
    assert "mock_cloud" in registry.list_providers()

    # Test environment override
    os.environ["SUPREMEAI_SANDBOX_PROVIDER"] = "mock_cloud"
    try:
        assert registry.get() == cloud_provider
    finally:
        os.environ.pop("SUPREMEAI_SANDBOX_PROVIDER", None)


@pytest.mark.asyncio
async def test_cloud_sandbox_provider_fail_closed() -> None:
    # Unconfigured provider must fail closed
    provider = CloudSandboxProvider(name="test_unconfigured", api_key=None, endpoint=None)
    assert provider.is_trusted_boundary is True

    result = await provider.execute("print('test')", language="python")
    assert result.success is False
    assert "unconfigured" in result.stderr.lower()

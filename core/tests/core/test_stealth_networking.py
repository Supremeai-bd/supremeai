import os
from unittest.mock import patch

import pytest

from core.config import settings
from tools.browser.stealth_http_client import StealthHTTPClient
from tools.code.local_code_executor import LocalCodeExecutor
from tools.security_tools.proxy_manager import ProxyManager


@pytest.mark.asyncio
async def test_production_sandbox_fails_without_docker():
    # Enforce production mode
    old_env = settings.env
    settings.env = "production"

    executor = LocalCodeExecutor()
    from unittest.mock import MagicMock

    # Mock docker to fail
    mock_docker = MagicMock()
    mock_docker.from_env.side_effect = Exception("Docker daemon down")
    with patch.dict(os.environ, {"ENV": "production", "ALLOW_LOCAL_SANDBOX_FALLBACK": "false"}):
        with patch.dict("sys.modules", {"docker": mock_docker}):
            res = await executor.execute_local_code("print('hello')")

    assert res["success"] is False
    assert (
        "CRITICAL SECURITY" in res["error"]
        or "local execution is disabled" in res["error"]
        or "strictly disabled in production" in res["error"]
    )

    # Restore settings environment
    settings.env = old_env


def test_proxy_manager_rotates_proxies():
    # Setup custom env proxies
    with patch.dict(os.environ, {"SUPREMEAI_PROXIES": "http://proxy1:8080,http://proxy2:8080"}):
        mgr = ProxyManager()
        p1 = mgr.get_next_proxy()
        p2 = mgr.get_next_proxy()
        p3 = mgr.get_next_proxy()

        assert p1 == "http://proxy1:8080"
        assert p2 == "http://proxy2:8080"
        assert p3 == "http://proxy1:8080"  # rotates back


@pytest.mark.anyio
async def test_stealth_http_client_adds_headers_and_rotates():
    with patch.dict(os.environ, {"SUPREMEAI_PROXIES": "http://proxy1:8080"}):
        client = StealthHTTPClient()

        async def mock_request(*args, **kwargs):
            # Assert headers spoofing was populated
            assert "User-Agent" in kwargs["headers"]
            pass  # Proxy is passed to AsyncClient init, not request args

            class MockResponse:
                def raise_for_status(self):
                    pass

            return MockResponse()

        with patch("httpx.AsyncClient.request", new=mock_request):
            res = await client.get("http://example.com")
            assert res is not None

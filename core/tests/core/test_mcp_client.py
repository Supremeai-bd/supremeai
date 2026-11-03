from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.mcp_client import MCPRegistryClient


@pytest.mark.anyio
async def test_mcp_client_fallback_when_no_servers_respond(monkeypatch):
    c = MCPRegistryClient()
    monkeypatch.setattr(
        "core.mcp_client.MCPSecurityGuard.is_safe_url", lambda url, enforce_https: True
    )

    with patch("core.mcp_client.settings", MagicMock(mcp_server_urls=[])):
        with patch("core.mcp_client.httpx.AsyncClient") as client_cls:
            client = MagicMock()
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            client.get = AsyncMock(side_effect=Exception("net"))
            client_cls.return_value = client

            tools = await c.discover_tools(domain="research_analysis")

    assert tools
    assert "web_search" in tools


@pytest.mark.anyio
async def test_mcp_client_filters_by_domain_tags(monkeypatch):
    c = MCPRegistryClient()
    monkeypatch.setattr(
        "core.mcp_client.MCPSecurityGuard.is_safe_url", lambda url, enforce_https: True
    )

    fake_tools = [
        {"name": "t1", "tags": ["research_analysis"]},
        {"name": "t2", "tags": ["code_generation"]},
    ]

    with patch("core.mcp_client.settings", MagicMock(mcp_server_urls=["https://srv1"])):
        with patch("core.mcp_client.httpx.AsyncClient") as client_cls:
            client = MagicMock()
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            client.get = AsyncMock(
                return_value=MagicMock(
                    status_code=200, json=MagicMock(return_value={"tools": fake_tools})
                )
            )
            client_cls.return_value = client

            tools = await c.discover_tools(domain="research_analysis")

    assert tools == ["t1"]

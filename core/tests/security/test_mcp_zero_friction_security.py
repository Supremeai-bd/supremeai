"""Regression tests for Zero-Friction SupremeAI connection boundaries."""

from unittest.mock import patch

import pytest

from core.plugins.mcp_security import MCPSecurityGuard


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/mcp",
        "http://10.0.0.4/mcp",
        "http://192.168.1.10/mcp",
        "https://user:secret@example.com/mcp",
    ],
)
def test_mcp_url_blocks_private_or_credentialed_targets(url: str) -> None:
    with patch(
        "core.plugins.mcp_security.socket.getaddrinfo",
        return_value=[(None, None, None, None, ("127.0.0.1", 443))],
    ):
        assert MCPSecurityGuard.is_safe_url(url, enforce_https=False) is False


def test_mcp_url_rejects_non_standard_ports() -> None:
    assert MCPSecurityGuard.is_safe_url("https://example.com:8443/mcp") is False


def test_mcp_url_checks_all_dns_answers() -> None:
    answers = [
        (None, None, None, None, ("93.184.216.34", 443)),
        (None, None, None, None, ("10.0.0.8", 443)),
    ]
    with patch("core.plugins.mcp_security.socket.getaddrinfo", return_value=answers):
        assert MCPSecurityGuard.is_safe_url("https://example.com/mcp") is False

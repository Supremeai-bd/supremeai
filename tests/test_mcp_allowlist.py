import pytest

from core.mcp_allowlist import MCPAllowlist, get_mcp_servers


def test_get_mcp_servers_shape():
    servers = get_mcp_servers()
    assert "github" in servers
    assert "slack" in servers
    assert "filesystem" in servers
    for name, config in servers.items():
        assert "command" in config
        assert "allowed_tools" in config
        assert "allowed_paths" in config


def test_validate_server_allowed():
    result = MCPAllowlist.validate_server("github")
    assert result["allowed"] is True
    assert result["server"] == "github"
    assert "search_repositories" in result["tools"]


def test_validate_server_denied():
    result = MCPAllowlist.validate_server("nonexistent")
    assert result["allowed"] is False
    assert result["reason"] == "unknown mcp server"


def test_allowed_tools_all_granted():
    result = MCPAllowlist.allowed_tools("github", ["search_repositories", "get_file_contents"])
    assert result["allowed"] is True
    assert result["denied"] == []


def test_allowed_tools_partial_denied():
    result = MCPAllowlist.allowed_tools("github", ["search_repositories", "evil_tool"])
    assert result["allowed"] is False
    assert "evil_tool" in result["denied"]
    assert "search_repositories" in result["allowed_tools"]


def test_allowed_tools_server_denied():
    result = MCPAllowlist.allowed_tools("nonexistent", ["any_tool"])
    assert result["allowed"] is False
    assert result["denied"] == ["any_tool"]

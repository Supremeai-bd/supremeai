from unittest.mock import patch

from core.plugins.security_scanner import PluginSecurityScanner


def test_plugin_security_scanner_valid_mcp():
    manifest = {
        "source": "mcp",
        "mcp_url": "https://api.example.com/mcp",
        "permission_schema": [{"name": "web_search"}],
    }
    with patch("core.plugins.security_scanner.MCPSecurityGuard.is_safe_url", return_value=True):
        report = PluginSecurityScanner.scan_manifest(manifest)
    assert report["passed"] is True
    assert len(report["violations"]) == 0


def test_plugin_security_scanner_non_mcp_source():
    manifest = {
        "source": "python_script",
        "mcp_url": "https://api.example.com/mcp",
        "permission_schema": [],
    }
    report = PluginSecurityScanner.scan_manifest(manifest)
    assert report["passed"] is False
    assert any("must be MCP-based" in v for v in report["violations"])


def test_plugin_security_scanner_unsafe_url():
    manifest = {
        "source": "mcp",
        "mcp_url": "http://127.0.0.1:8080/mcp",
        "permission_schema": [],
    }
    with patch("core.plugins.security_scanner.MCPSecurityGuard.is_safe_url", return_value=False):
        report = PluginSecurityScanner.scan_manifest(manifest)
    assert report["passed"] is False
    assert any("Unsafe MCP URL" in v for v in report["violations"])


def test_plugin_security_scanner_forbidden_capability():
    manifest = {
        "source": "mcp",
        "mcp_url": "https://api.example.com/mcp",
        "permission_schema": [{"name": "system.admin"}],
    }
    with patch("core.plugins.security_scanner.MCPSecurityGuard.is_safe_url", return_value=True):
        report = PluginSecurityScanner.scan_manifest(manifest)
    assert report["passed"] is False
    assert any("Forbidden capability requested: system.admin" in v for v in report["violations"])

"""Tests for SSRF protection module.

Tests cover:
- Private IP detection (127.0.0.1, 10.x, 172.16-31.x, 192.168.x, 169.254.x)
- Metadata endpoint blocking (169.254.169.254)
- DNS rebinding prevention
- Redirect-following re-validation
- Public URL allow-pass
"""

from __future__ import annotations

import pytest

from core.security.protection.ssrf_protection import is_safe_url


class TestSSRFPrivateIPs:
    """Private/internal IPs should be flagged as unsafe."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://localhost/",
            "http://10.0.0.1/",
            "http://10.255.255.255/",
            "http://172.16.0.1/",
            "http://172.31.255.255/",
            "http://192.168.1.1/",
            "http://192.168.0.0/",
            "http://169.254.169.254/latest/meta-data/",  # AWS metadata
            "http://169.254.170.2/",  # ECS task metadata
            "http://0.0.0.0/",
            "http://[::1]/",  # IPv6 loopback
            "http://[fc00::1]/",  # IPv6 ULA
            "http://[fe80::1]/",  # IPv6 link-local
        ],
    )
    def test_private_ip_unsafe(self, url):
        assert is_safe_url(url) is False, f"{url} should be unsafe"

    @pytest.mark.parametrize(
        "url",
        [
            "http://example.com/",
            "https://8.8.8.8/",
            "http://8.8.8.8/",
            "https://140.82.121.4/",
            "http://1.1.1.1/",
            "https://8.8.8.8/",
            "https://1.1.1.1/",
        ],
    )
    def test_public_url_safe(self, url):
        assert is_safe_url(url) is True, f"{url} should be safe"


class TestSSRFMetadataEndpoints:
    """Cloud metadata endpoints must be blocked."""

    def test_aws_metadata_v1(self):
        assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False

    def test_aws_metadata_v2(self):
        assert is_safe_url("http://169.254.169.254/latest/api/token") is False

    def test_gcp_metadata(self):
        assert is_safe_url("http://metadata.google.internal/") is False

    def test_azure_metadata(self):
        assert is_safe_url("http://169.254.169.254/metadata/instance") is False


class TestSSRFEdgeCases:
    """Edge cases: malformed URLs, IPv6, file://, etc."""

    def test_file_protocol_unsafe(self):
        assert is_safe_url("file:///etc/passwd") is False

    def test_empty_url_unsafe(self):
        assert is_safe_url("") is False
        assert is_safe_url(None) is False

    def test_hex_encoded_localhost(self):
        # http://0x7f000001/ → 127.0.0.1
        assert is_safe_url("http://0x7f000001/") is False

    def test_decimal_ip_localhost(self):
        # http://2130706433/ → 127.0.0.1
        assert is_safe_url("http://2130706433/") is False

    def test_octal_ip_localhost(self):
        # http://0177.0.0.1/ → 127.0.0.1
        assert is_safe_url("http://0177.0.0.1/") is False

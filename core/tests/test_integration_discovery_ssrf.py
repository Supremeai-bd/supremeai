"""SSRF ব্লকার — IntegrationDiscoveryService._assert_public_host() টেস্ট।

কভার করে: loopback, RFC1918 প্রাইভেট রেঞ্জ, link-local/cloud metadata
(169.254.169.254), এবং স্বাভাবিক পাবলিক হোস্ট allow হওয়া।
"""

from __future__ import annotations

import pytest

from backend.services.integration_discovery import (
    SSRFBlockedError,
    _assert_public_host,
    _is_blocked_ip,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://127.0.0.1:8080/",  # loopback
        "http://10.0.0.5/",  # RFC1918
        "http://172.16.5.5/",  # RFC1918
        "http://192.168.1.1/",  # RFC1918
        "http://0.0.0.0/",
        "http://[::1]/",
    ],
)
def test_private_and_metadata_urls_are_blocked(url: str) -> None:
    with pytest.raises(SSRFBlockedError):
        _assert_public_host(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "https://github.com",
    ],
)
def test_public_urls_are_allowed(url: str) -> None:
    # resolve করা যাবে এবং কোনো exception ছুঁড়বে না
    _assert_public_host(url)


def test_unparsable_ip_fails_closed() -> None:
    assert _is_blocked_ip("not-an-ip") is True


def test_metadata_ip_specifically_blocked() -> None:
    assert _is_blocked_ip("169.254.169.254") is True

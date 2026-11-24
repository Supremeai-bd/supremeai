"""SSRF and Network Sanitization Security Guard for SupremeAI Browser & Scraper.

Restores the production-grade network isolation originally authored in PR #4377.
Guarantees:
  - Blocks loopback (127.0.0.1, localhost), link-local, private RFC 1918 IPs, and AWS/Cloud metadata (169.254.169.254).
  - Resolves domain names via DNS and verifies that target resolved IPs are public global addresses before navigation.
  - Supports explicit host allowlisting via BROWSER_ALLOWED_HOSTS env var.
"""

from __future__ import annotations

import asyncio
import os
import socket
from urllib.parse import urlparse

# 2026-11-24 (audit item ⑮): the blocklists used to live here as a third copy.
# The standalone image cannot import ``core`` (dockerContext: browser), so this
# module reads ``url_policy`` — a byte-identical mirror of
# ``core/url_policy.py`` enforced by tests/test_url_policy_single_source.py.
try:  # monorepo layout
    from browser.url_policy import (
        host_literal_is_blocked,
        ip_is_blocked,
        normalize_host,
        scheme_is_allowed,
    )
except ImportError:  # flat standalone layout (COPY *.py into /app)
    from url_policy import (  # type: ignore[no-redef]
        host_literal_is_blocked,
        ip_is_blocked,
        normalize_host,
        scheme_is_allowed,
    )

_ALLOWED_HOSTS = {
    host.strip().lower()
    for host in os.getenv("BROWSER_ALLOWED_HOSTS", "").split(",")
    if host.strip()
}


def is_safe_public_ip(ip_str: str) -> bool:
    """Validate that the given IP address is a safe, routable public address.

    Now delegated to the shared policy table (which also blocks CGNAT,
    documentation and benchmarking ranges that ``addr.is_global`` allowed).
    """
    return not ip_is_blocked(ip_str)


def is_private_or_restricted_host(host: str) -> bool:
    """Check if the given host string is a private or restricted IP literal or localhost."""
    return host_literal_is_blocked(host)


def is_safe_url_resolved(raw_url: str) -> bool:
    """Request-time SSRF check: parse-time validation PLUS DNS resolution.

    2026-11-17: ``browser_agent`` and ``web_scraper`` import this name (it is
    the canonical ``core.services.scraper.security`` API), but this standalone
    microservice only defined ``is_safe_url``. The resulting ImportError made
    the whole scraper engine fail to construct, so ``/scrape``, ``/browse`` and
    ``/recipe`` were silently never registered.

    This implementation always resolves the hostname and screens every A/AAAA
    record, so it is the resolving check. ``is_safe_url`` is kept as an alias so
    existing callers keep the exact same behaviour.
    """
    try:
        parsed = urlparse(raw_url)
        if not scheme_is_allowed(parsed.scheme) or not parsed.hostname or parsed.username or parsed.password:
            return False
        host = normalize_host(parsed.hostname)
        if _ALLOWED_HOSTS and host not in _ALLOWED_HOSTS:
            return False
        if is_private_or_restricted_host(host):
            return False
        # Resolve address to ensure DNS rebinding or internal CNAME doesn't target private subnet
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        for _, _, _, _, sockaddr in addresses:
            if not is_safe_public_ip(sockaddr[0]):
                return False
        return True
    except Exception:
        return False


# Backwards-compatible alias: the original public name for the same check.
is_safe_url = is_safe_url_resolved


async def safe_url(raw_url: str) -> str:
    """Asynchronous URL validator returning normalized URL if safe, or raising ValueError."""
    parsed = urlparse(raw_url)
    if not scheme_is_allowed(parsed.scheme) or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public http(s) URLs are allowed")
    host = normalize_host(parsed.hostname)
    if _ALLOWED_HOSTS and host not in _ALLOWED_HOSTS:
        raise ValueError(f"Destination host '{host}' is not allowlisted")
    if is_private_or_restricted_host(host):
        raise ValueError(f"Private or restricted destination host '{host}' is not allowed")
    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo, host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM
        )
    except OSError as exc:
        raise ValueError(f"Destination '{host}' could not be resolved") from exc
    for _, _, _, _, sockaddr in addresses:
        if not is_safe_public_ip(sockaddr[0]):
            raise ValueError(f"Destination resolves to a non-public/restricted IP: {sockaddr[0]}")
    return parsed.geturl()


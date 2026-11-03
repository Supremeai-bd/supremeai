"""SSRF and Network Sanitization Security Guard for SupremeAI Browser & Scraper.

Restores the production-grade network isolation originally authored in PR #4377.
Guarantees:
  - Blocks loopback (127.0.0.1, localhost), link-local, private RFC 1918 IPs, and AWS/Cloud metadata (169.254.169.254).
  - Resolves domain names via DNS and verifies that target resolved IPs are public global addresses before navigation.
  - Supports explicit host allowlisting via BROWSER_ALLOWED_HOSTS env var.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from urllib.parse import urlparse

_ALLOWED_HOSTS = {
    host.strip().lower()
    for host in os.getenv("BROWSER_ALLOWED_HOSTS", "").split(",")
    if host.strip()
}


def is_safe_public_ip(ip_str: str) -> bool:
    """Validate that the given IP address is a safe, routable public address."""
    try:
        addr = ipaddress.ip_address(ip_str)
        return (
            addr.is_global
            and not addr.is_multicast
            and not addr.is_reserved
            and not addr.is_loopback
            and not addr.is_link_local
            and not addr.is_unspecified
        )
    except ValueError:
        return False


def is_private_or_restricted_host(host: str) -> bool:
    """Check if the given host string is a private or restricted IP literal or localhost."""
    host_lower = host.lower().strip()
    if host_lower in {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}:
        return True
    try:
        ipaddress.ip_address(host_lower)
        return not is_safe_public_ip(host_lower)
    except ValueError:
        return False


def is_safe_url(raw_url: str) -> bool:
    """Synchronous check used by FastAPI route validation."""
    try:
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return False
        host = parsed.hostname.lower().rstrip(".")
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


async def safe_url(raw_url: str) -> str:
    """Asynchronous URL validator returning normalized URL if safe, or raising ValueError."""
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public http(s) URLs are allowed")
    host = parsed.hostname.lower().rstrip(".")
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


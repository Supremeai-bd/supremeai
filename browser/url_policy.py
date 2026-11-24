"""Single source of truth for URL / host / IP safety policy (SSRF screening).

Why this module exists (2026-11-24 audit, item ⑮): the repo carried four
independent SSRF implementations, each with its own blocklist, and they had
already drifted

===============  =========================================================
location          what it had that the others lacked
===============  =========================================================
``core/security/protection/ssrf_protection.py``  DNS cache, metadata IPs, rebinding probe — but no CGNAT / documentation / benchmarking ranges
``core/services/scraper/security.py``             strictest network list + IPv4-mapped IPv6 unwrapping — but no metadata-host suffix list
``browser/security.py``                           ``addr.is_global`` shortcut — silently allows IPv4-mapped private literals
``core/services/integration_discovery.py``        ad-hoc ``ip.is_private or …`` chain, no IPv6 networks
===============  =========================================================

This module is the **policy**, not the transport: it is stdlib-only, has no
logging and imports nothing from ``core`` (so it is safe to vendor into the
standalone images — see ``MIRROR`` below). Each call site keeps its own
transport shape (sync/async, DNS cache, fail-closed behaviour); only the
"what is forbidden" table lives here.

MIRROR: ``browser/url_policy.py`` is a byte-identical copy for the standalone
scraper/browser image. That image is built with ``dockerContext: browser``, so
it cannot import ``core`` at all — see ``browser/Dockerfile``. Identity is
enforced by ``tests/test_url_policy_single_source.py``; edit BOTH files or CI
fails.
"""

from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
from urllib.parse import urlparse

# ── schemes ──────────────────────────────────────────────────────────────────
ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

BLOCKED_SCHEMES: frozenset[str] = frozenset(
    {"file", "ftp", "gopher", "dict", "ldap", "javascript", "data"}
)

# ── hostnames ────────────────────────────────────────────────────────────────
#: Hostnames that resolve locally or name a metadata service directly.
BLOCKED_HOSTS: frozenset[str] = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "[::1]",
        "metadata",  # GCP metadata (resolvable via /etc/hosts on GCP)
        "metadata.google.internal",
    }
)

#: Internal TLDs — a resolved public IP does not make these safe to dial.
BLOCKED_HOSTNAME_SUFFIXES: tuple[str, ...] = (
    ".local",
    ".localhost",
    ".internal",
    ".intranet",
    ".lan",
    ".corp",
    ".home",
    ".internal.cloudapp.net",
    ".internal-dns",
)

# ── IP literals ──────────────────────────────────────────────────────────────
#: Cloud metadata endpoints. All of them live inside a blocked network below;
#: they are listed separately so a rejection can name the exact service.
BLOCKED_METADATA_IPS: frozenset[str] = frozenset(
    {
        "169.254.169.254",  # AWS / GCP / Azure metadata
        "169.254.170.2",  # AWS ECS metadata
        "100.100.100.200",  # Alibaba Cloud metadata
    }
)

#: Cheap string prefixes used for early rejection *before* resolution.
PRIVATE_PREFIXES: tuple[str, ...] = (
    "10.",
    "172.16.",
    "192.168.",
    "169.254.",
    "100.64.",
    "fc",
    "fe80:",
)

#: Networks that must never be dialed, matched against resolved IPs as well as
#: literals. Superset of the pre-2026-11 lists: adds CGNAT 100.64/10 (which also
#: covers Alibaba metadata 100.100.100.200), multicast, benchmarking and the
#: documentation/reserved ranges (issue #511).
BLOCKED_V4_NETWORKS: tuple = tuple(
    ip_network(n)
    for n in (
        "0.0.0.0/8",  # unspecified / "this host"
        "10.0.0.0/8",  # private (RFC1918)
        "100.64.0.0/10",  # CGNAT / carrier NAT
        "127.0.0.0/8",  # loopback
        "169.254.0.0/16",  # link-local (AWS/GCP/Azure metadata lives here)
        "172.16.0.0/12",  # private (RFC1918)
        "192.0.0.0/24",  # IETF protocol assignments
        "192.0.2.0/24",  # TEST-NET-1 (documentation)
        "192.168.0.0/16",  # private (RFC1918)
        "198.18.0.0/15",  # benchmarking
        "198.51.100.0/24",  # TEST-NET-2 (documentation)
        "203.0.113.0/24",  # TEST-NET-3 (documentation)
        "224.0.0.0/4",  # multicast
        "240.0.0.0/4",  # reserved (incl. 255.255.255.255)
    )
)

BLOCKED_V6_NETWORKS: tuple = tuple(
    ip_network(n)
    for n in (
        "::/128",  # unspecified
        "::1/128",  # loopback
        "100::/64",  # discard-only
        "2001:db8::/32",  # documentation
        "fc00::/7",  # unique-local (private)
        "fe80::/10",  # link-local
        "ff00::/8",  # multicast
    )
)


def ip_is_blocked(ip: str) -> bool:
    """True when ``ip`` may never be dialed. Fails closed on malformed input.

    IPv4-mapped IPv6 literals are unwrapped first: ``::ffff:10.0.0.1`` is just
    ``10.0.0.1`` in disguise.
    """
    try:
        addr = ip_address(str(ip))
    except (ValueError, TypeError):
        return True
    if isinstance(addr, IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    if isinstance(addr, IPv4Address) and addr.is_multicast:
        return True
    networks = BLOCKED_V4_NETWORKS if addr.version == 4 else BLOCKED_V6_NETWORKS
    return any(addr in network for network in networks)


def normalize_host(host: str) -> str:
    """Lower-case a host and strip the root dot / IPv6 brackets."""
    cleaned = (host or "").strip().lower().rstrip(".")
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1]
    return cleaned


def host_literal_is_blocked(host: str) -> bool:
    """True when the host *string* itself is forbidden (no DNS involved)."""
    cleaned = normalize_host(host)
    if not cleaned:
        return True
    if cleaned in BLOCKED_HOSTS:
        return True
    if cleaned in BLOCKED_METADATA_IPS:
        return True
    for suffix in BLOCKED_HOSTNAME_SUFFIXES:
        if cleaned.endswith(suffix):
            return True
    for prefix in PRIVATE_PREFIXES:
        if cleaned.startswith(prefix):
            return True
    try:
        ip_address(cleaned)
    except ValueError:
        return False  # a real hostname; resolution decides
    return ip_is_blocked(cleaned)


def scheme_is_allowed(scheme: str) -> bool:
    """True only for the schemes the platform actually dials."""
    lowered = (scheme or "").strip().lower()
    return lowered in ALLOWED_SCHEMES and lowered not in BLOCKED_SCHEMES


def parse_url(raw_url: str) -> tuple[str, str, int | None] | None:
    """Split a URL into ``(scheme, host, port)`` or return ``None`` when unsafe.

    Rejects missing hosts, credentials in the URL (``http://user:pass@host`` —
    a redirect/parser-confusion vector) and non-http(s) schemes.
    """
    try:
        parsed = urlparse(str(raw_url))
    except (ValueError, AttributeError):
        return None
    if not scheme_is_allowed(parsed.scheme):
        return None
    host = normalize_host(parsed.hostname or "")
    if not host or parsed.username or parsed.password:
        return None
    return parsed.scheme.lower(), host, parsed.port


__all__ = [
    "ALLOWED_SCHEMES",
    "BLOCKED_HOSTS",
    "BLOCKED_HOSTNAME_SUFFIXES",
    "BLOCKED_METADATA_IPS",
    "BLOCKED_SCHEMES",
    "BLOCKED_V4_NETWORKS",
    "BLOCKED_V6_NETWORKS",
    "PRIVATE_PREFIXES",
    "host_literal_is_blocked",
    "ip_is_blocked",
    "normalize_host",
    "parse_url",
    "scheme_is_allowed",
]

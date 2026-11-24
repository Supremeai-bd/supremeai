"""
Minimal SSRF protection for the standalone scraper service.

Self-contained — this module never imports ``core.security`` (that package's
``__init__`` pulls DB/Redis/asyncpg). It *does* use ``core.url_policy``, the
stdlib-only policy module that holds the blocklists for the whole platform
(2026-11-24 audit, item ⑮: four diverging copies collapsed into one policy).

Two layers (issue #511, BE-05 — SSRF via HTTP redirects + DNS rebinding):

  1. ``is_safe_url()`` — synchronous parse-time screening (scheme + hostname
     literals). Cheap, no DNS. Suitable for request intake.
  2. ``is_safe_url_resolved()`` — request-time screening: resolves the
     hostname to ALL its A/AAAA records and rejects the URL if ANY resolved
     IP is private/loopback/link-local/metadata/reserved. The fetch path must
     call this immediately before EVERY HTTP request (initial URL and every
     redirect hop), closing the redirect and DNS-rebinding bypasses of
     layer 1.

Residual risk (documented per issue #511): between the resolved-IP check and
the actual TCP connect, httpx re-resolves DNS on its own. A rebinding server
flipping its answer inside that TOCTOU window could still land the connection
on a private IP. Full mitigation requires pinning the validated IP at the
transport layer (custom httpcore backend) — intentionally out of scope here;
per-hop re-validation shrinks the window to a single connect.
"""

from socket import gaierror, getaddrinfo

try:  # embedded in the monorepo / installed as a package
    from core.url_policy import (
        host_literal_is_blocked,
        ip_is_blocked,
        parse_url,
    )
except ImportError:  # flat standalone layout: url_policy.py sits next to this file
    from url_policy import (  # type: ignore[no-redef]
        host_literal_is_blocked,
        ip_is_blocked,
        parse_url,
    )


def _is_private_ip(hostname: str) -> bool:
    """Parse-time literal-IP check (kept for backward compatibility)."""
    return host_literal_is_blocked(hostname)


def _is_blocked_ip(ip: str) -> bool:
    """True if ``ip`` may never be dialed. Fails closed on malformed input.

    Thin alias over :func:`core.url_policy.ip_is_blocked` (which unwraps
    IPv4-mapped IPv6 literals such as ``::ffff:10.0.0.1``).
    """
    return ip_is_blocked(ip)


def resolve_hostname(hostname: str) -> list[str]:
    """Resolve ``hostname`` to every A/AAAA record.

    No caching on purpose — a DNS cache would widen the rebinding TOCTOU
    window (issue #511). Returns [] when resolution fails; callers must fail
    closed (a hostile resolver answering NXDOMAIN to us and 127.0.0.1 to
    httpx must not slip through).
    """
    try:
        infos = getaddrinfo(hostname, None)
    except (gaierror, OSError, UnicodeError):
        return []
    ips: list[str] = []
    for info in infos:
        candidate = str(info[4][0])
        if candidate not in ips:
            ips.append(candidate)
    return ips


def is_safe_url(url: str) -> bool:
    """Validate URL to prevent SSRF attacks in the standalone scraper service.

    Parse-time checks only (scheme + hostname literals) — does NOT resolve
    DNS and does NOT see redirect targets. The fetch path must additionally
    call :func:`is_safe_url_resolved` immediately before every request
    (issue #511).
    """
    try:
        # Shared parse: rejects non-http(s) schemes, missing hosts and
        # credentials in the URL (`http://user:pass@host` — a parser-confusion
        # vector the browser surface already refused). 2026-11-24.
        parsed = parse_url(url)
        if parsed is None:
            return False
        _scheme, hostname, _port = parsed

        # One policy call covers: literal blocklist, internal TLD suffixes,
        # private prefixes and IP literals (see core/url_policy.py).
        return not host_literal_is_blocked(hostname)
    except Exception:  # noqa: BLE001
        return False


def is_safe_url_resolved(url: str) -> bool:
    """Request-time SSRF validation for the fetch path (issue #511).

    Runs the parse-time checks, then resolves the hostname and rejects the
    URL if ANY resolved A/AAAA record is private/loopback/link-local/etc.
    Fails closed when DNS resolution fails.
    """
    if not is_safe_url(url):
        return False
    parsed = parse_url(url)
    if parsed is None:
        return False
    hostname = parsed[1]
    resolved = resolve_hostname(hostname)
    if not resolved:
        return False  # DNS failure — fail closed (issue #511)
    return all(not _is_blocked_ip(ip) for ip in resolved)

"""One SSRF policy source, one enforced mirror (audit item ⑮).

The repo had four independent SSRF implementations with four blocklists, and
they had already drifted (one missed CGNAT, one missed documentation ranges,
one let IPv4-mapped literals through). They now share ``core/url_policy.py``.

Two things need guarding, and this file does both:

1. **The vendored mirror stays identical.** ``browser/url_policy.py`` exists
   only because the standalone browser/scraper image is built with
   ``dockerContext: browser`` and therefore cannot import ``core`` at all
   (``browser/Dockerfile`` does ``COPY *.py ./``). Byte-identity is the contract;
   a one-character edit to one file must fail CI, not silently fork the policy.

2. **Nobody re-grows a private blocklist.** The four call sites
   (``core/security/protection/ssrf_protection.py``,
   ``core/services/scraper/security.py``, ``browser/security.py``,
   ``core/services/integration_discovery.py``) may *use* the policy but must not
   define their own network/host tables. The scan fails on a
   ``ip_network("10.0.0.0/8")``-style literal in those files, which is exactly
   how the previous copies appeared.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL = REPO_ROOT / "core" / "url_policy.py"
MIRROR = REPO_ROOT / "browser" / "url_policy.py"

#: Modules allowed to talk about the policy; none of them may define it.
CALL_SITES = (
    "core/security/protection/ssrf_protection.py",
    "core/security/__init__.py",
    "core/services/scraper/security.py",
    "browser/security.py",
    "core/services/integration_discovery.py",
)

#: A private range literal, e.g. ip_network("10.0.0.0/8") or "192.168.0.0/16".
_NETWORK_LITERAL = re.compile(r"ip_network\(\s*[\"'][0-9a-fA-F:.]+/\d+[\"']")


def test_mirror_is_still_required_by_the_build_layout():
    """The mirror must not outlive its reason.

    If the scraper image stops being built with ``dockerContext: browser``, the
    mirror is obsolete: delete ``browser/url_policy.py``, import core directly,
    and remove the jscpd exemption.
    """
    render = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")
    browser_block = render.split("name: supremeai-browser", 1)
    assert len(browser_block) == 2, "supremeai-browser service disappeared from render.yaml"
    service_yaml = browser_block[1].split("- type:", 1)[0]
    assert "dockerContext: browser" in service_yaml, (
        "supremeai-browser no longer builds with dockerContext: browser — the "
        "vendored mirror browser/url_policy.py is now unnecessary. Delete it, "
        "import core.url_policy from browser/security.py, and drop the "
        "browser/url_policy.py entry in scripts/ci/detect_new_duplicates.py."
    )
    dockerfile = (REPO_ROOT / "browser" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chown=supremeai:supremeai *.py ./" in dockerfile, (
        "browser/Dockerfile no longer copies a flat *.py tree — re-check whether "
        "the mirror is still needed."
    )


def test_mirror_is_byte_identical():
    assert CANONICAL.is_file(), "core/url_policy.py is the single policy source"
    assert MIRROR.is_file(), (
        "browser/url_policy.py must exist: the standalone image cannot import core"
    )
    canonical = CANONICAL.read_bytes()
    mirror = MIRROR.read_bytes()
    assert canonical == mirror, (
        "browser/url_policy.py drifted from core/url_policy.py — the standalone "
        "scraper image would enforce a different SSRF policy than core. Edit both "
        "(they must stay byte-identical)."
    )


def test_no_call_site_defines_its_own_network_table():
    offenders = []
    for rel in CALL_SITES:
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        for match in _NETWORK_LITERAL.finditer(source):
            line = source[: match.start()].count("\n") + 1
            offenders.append(f"{rel}:{line}: {match.group(0)}")
    assert not offenders, (
        "SSRF network tables belong in core/url_policy.py only; these call sites "
        "grew private copies again:\n  " + "\n  ".join(offenders)
    )


def test_no_call_site_defines_its_own_blocklist_constants():
    """A dict/set/tuple of blocked hosts is the other way drift reappears."""
    offenders = []
    for rel in CALL_SITES:
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [t.id for t in targets if isinstance(t, ast.Name)]
            for name in names:
                upper = name.upper()
                if not upper.startswith("_"):
                    continue
                if "BLOCKED" in upper or upper.endswith("_PRIVATE_PREFIXES"):
                    offenders.append(f"{rel}:{name}")
    assert not offenders, (
        "blocklist constants must come from core/url_policy.py, found: "
        + ", ".join(sorted(offenders))
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8080/",
        "http://10.1.2.3/",
        "http://100.64.0.1/",  # CGNAT — missed by the pre-2026-11 core table
        "http://192.0.2.5/",  # TEST-NET-1 — missed by the pre-2026-11 core table
        "http://[::1]/",
        "http://[::ffff:10.0.0.1]/",  # IPv4-mapped private literal
        "file:///etc/passwd",
        "javascript:alert(1)",
        "http://user:pass@example.com/",
    ],
)
def test_every_surface_agrees_on_blocked_urls(url):
    """Cross-implementation agreement — the whole point of one policy."""
    from browser.security import is_safe_url as browser_is_safe
    from core.services.integration_discovery import SSRFBlockedError, _assert_public_host
    from core.services.scraper.security import is_safe_url as scraper_is_safe

    assert browser_is_safe(url) is False, f"browser surface allowed {url}"
    assert scraper_is_safe(url) is False, f"scraper surface allowed {url}"
    with pytest.raises(SSRFBlockedError):
        _assert_public_host(url)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "http://user:pass@example.com/",  # credentials in the URL
        "https://",  # no host at all
        "",
    ],
)
def test_parse_url_rejects_unsafe_shapes(url):
    from core.url_policy import parse_url

    assert parse_url(url) is None


def test_parse_url_accepts_a_normal_url():
    from core.url_policy import parse_url

    assert parse_url("https://example.com/a?b=1") == ("https", "example.com", None)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/",
        "https://api.github.com/repos",
        "http://1.1.1.1/",  # public literal
    ],
)
def test_every_surface_agrees_on_allowed_urls(url):
    from browser.security import is_safe_url as browser_is_safe
    from core.services.scraper.security import is_safe_url as scraper_is_safe

    assert browser_is_safe(url) is True, f"browser surface blocked public URL {url}"
    assert scraper_is_safe(url) is True, f"scraper surface blocked public URL {url}"


def test_ipv4_mapped_literal_is_unwrapped():
    from core.url_policy import ip_is_blocked

    assert ip_is_blocked("::ffff:10.0.0.1") is True
    assert ip_is_blocked("::ffff:8.8.8.8") is False


def test_malformed_ip_fails_closed():
    from core.url_policy import ip_is_blocked

    assert ip_is_blocked("not-an-ip") is True
    assert ip_is_blocked("") is True

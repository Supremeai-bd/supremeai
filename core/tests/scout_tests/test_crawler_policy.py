"""Unit tests for Crawler Policy Engine and Legacy Adapter."""

from __future__ import annotations

import pytest

from scout.models import CrawlPolicy, DomainRule, TrustLevel
from scout.policy import PolicyEngine
from scout.web_crawler_agent import APPROVED_DOMAINS, crawl


def test_policy_engine_ssrf_blocking() -> None:
    policy = CrawlPolicy(tenant_id="test-tenant", allowed_domains=["*"])
    engine = PolicyEngine(policy)

    # Private IPs / loopback should be rejected
    allowed, reason = engine.is_url_allowed("http://127.0.0.1:8000/admin")
    assert not allowed
    assert "unsafe" in reason.lower() or "blocked" in reason.lower()

    allowed, _ = engine.is_url_allowed("http://169.254.169.254/latest/meta-data")
    assert not allowed

    allowed, _ = engine.is_url_allowed("http://localhost:5000")
    assert not allowed


def test_policy_engine_domain_filtering() -> None:
    policy = CrawlPolicy(
        tenant_id="test-tenant",
        allowed_domains=["github.com", "*.python.org"],
        blocked_domains=["malicious.com"],
        domain_rules=[
            DomainRule(domain="github.com", trust_level=TrustLevel.TRUSTED),
        ],
    )
    engine = PolicyEngine(policy)

    # Allowed domain
    allowed, _ = engine.is_url_allowed("https://github.com/torvalds/linux")
    assert allowed

    # Subdomain wildcard
    allowed, _ = engine.is_url_allowed("https://docs.python.org/3/library/")
    assert allowed

    # Explicitly blocked domain
    allowed, reason = engine.is_url_allowed("https://malicious.com/exploit")
    assert not allowed
    assert "blocked" in reason.lower()

    # Unlisted domain when allowlist is active
    allowed, reason = engine.is_url_allowed("https://random-site.org/page")
    assert not allowed
    assert "allowed" in reason.lower()


def test_policy_engine_depth_limit() -> None:
    policy = CrawlPolicy(tenant_id="test-tenant", allowed_domains=["*"], max_depth=2)
    engine = PolicyEngine(policy)

    allowed, _ = engine.is_url_allowed("https://example.com/page", current_depth=1)
    assert allowed

    allowed, reason = engine.is_url_allowed("https://example.com/page", current_depth=3)
    assert not allowed
    assert "depth" in reason.lower()


@pytest.mark.asyncio
async def test_legacy_crawler_adapter_disallowed_domain() -> None:
    with pytest.raises(PermissionError) as exc_info:
        await crawl("https://unapproved-domain.xyz", tenant_id="test-tenant")
    assert "Domain not approved" in str(exc_info.value)

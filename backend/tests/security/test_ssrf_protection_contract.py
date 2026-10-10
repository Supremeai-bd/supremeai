# বাংলা মন্তব্য: tests/security/test_ssrf_protection_contract.py
# ============================================================
# Issue: core/security/protection/ssrf_protection.py — SSRF প্রতিরোধ মডিউলের
# কন্ট্র্যাক্ট-লেভেল টেস্ট। টাস্ক #2766।
#
# কনটেক্সট: আগের tests/security/test_ssrf_protection.py রিয়েল DNS রেজোলিউশনের
# উপর নির্ভর করে (socket.gethostbyname) — অফলাইন CI/স্যান্ডবক্সে ফ্ল্যাকি।
# এই ফাইলটি পুরোপুরি অফলাইন: socket.gethostbyname মকড করা হয়েছে, কোনো
# নেটওয়ার্ক কল নেই।
#
# কভারেজ:
#   • localhost / 127.0.0.1 blocked
#   • private subnets (10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12) blocked
#   • cloud metadata IP (169.254.169.254) blocked
#   • public URLs allowed
#   • DNS rebinding prevention (protocol bypass blocked)
#   • non-http(s) schemes blocked (file://, ftp://, gopher://)
#
# AGENTS.md rules followed:
#   - Rule #6: বাংলা কোড কমেন্ট বাধ্যতামূলক
#   - Rule #61: happy + sad paths (happy = public URL; sad = private/metadata IP)
#   - Rule #64: কোনো external API/network কল নেই — সব মকড
#   - Rule #66: boundary tests (subnet edges, IPv6, scheme bypass)
#   - Rule #67: Given-When-Then ডকস্ট্রিং স্ট্রাকচার
# ============================================================

from __future__ import annotations

import ipaddress
import socket
from unittest.mock import patch

import pytest

from core.security.protection.ssrf_protection import (
    SSRFProtection,
    SSRFValidationResult,
    is_safe_url,
    reset_ssrf_protection,
)


# ============================================================
# হেল্পার: একটি প্রাইভেট DNS-resolved হোস্টনেম + IP মক করার জন্য
# ============================================================
def _patch_dns(monkeypatch, hostname_to_ip: dict[str, str]):
    """socket.gethostbyname + getaddrinfo মক করে — কোনো রিয়েল DNS কল নয়।

    বাংলা: hostname_to_ip dict হলো {hostname: ip} ম্যাপিং। প্রতিটি কলে একই IP
    রিটার্ন করবে — DNS rebinding test ছাড়া বাকি সব ক্ষেত্রে এটি stable।
    """

    def _fake_gethostbyname(host: str) -> str:
        if host in hostname_to_ip:
            return hostname_to_ip[host]
        # বাংলা: ডিফল্ট পাবলিক IP রিটার্ন করি (1.1.1.1) যাতে unknown host-এর জন্য
        # ফেইল না হয়।
        return "1.1.1.1"

    def _fake_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        ip = hostname_to_ip.get(host, "1.1.1.1")
        return [(family, type, proto, "", (ip, port))]

    monkeypatch.setattr(socket, "gethostbyname", _fake_gethostbyname)
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)


@pytest.fixture(autouse=True)
def _reset_ssrf_singleton():
    """প্রতিটি টেস্টের আগে গ্লোবাল SSRFProtection singleton রিসেট করি।

    বাংলা: টেস্ট আইসোলেশন — singleton state leak করবে না।
    """
    reset_ssrf_protection()
    yield
    reset_ssrf_protection()


# ============================================================
# 1. Loopback / Localhost ব্লক কন্ট্র্যাক্ট
# ============================================================
class TestLoopbackBlocked:
    """127.0.0.1, ::1, localhost — সব ধরনের loopback ব্লক।"""

    @pytest.mark.parametrize(
        "url,resolved_ip",
        [
            ("http://127.0.0.1/", "127.0.0.1"),
            ("http://127.0.0.1:8080/admin", "127.0.0.1"),
            ("http://localhost/", "127.0.0.1"),  # hostname loopback
        ],
    )
    def test_loopback_ipv4_blocked(self, monkeypatch, url, resolved_ip):
        """Given: URL যা 127.0.0.1-এ resolve হয়।
        When: validate_url() কল করা হয়।
        Then: is_safe=False — loopback কখনো accept নয়।
        """
        # Given
        _patch_dns(monkeypatch, {"localhost": resolved_ip})
        protection = SSRFProtection()

        # When
        result = protection.validate_url(url)

        # Then: বাংলা: loopback IP ব্লক
        assert result.is_safe is False
        assert "loopback" in result.reason.lower() or "blocklist" in result.reason.lower()

    def test_loopback_ipv6_blocked(self, monkeypatch):
        """Given: ::1 IPv6 loopback।
        When: validate_url("http://[::1]/")।
        Then: is_safe=False।
        """
        # Given
        _patch_dns(monkeypatch, {"::1": "::1"})
        protection = SSRFProtection()

        # When
        result = protection.validate_url("http://[::1]/")

        # Then
        assert result.is_safe is False


# ============================================================
# 2. Private Subnet ব্লক কন্ট্র্যাক্ট
# ============================================================
class TestPrivateSubnetsBlocked:
    """10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12 — সব প্রাইভেট সাবনেট ব্লক।"""

    @pytest.mark.parametrize(
        "ip",
        [
            # 10.0.0.0/8 range
            "10.0.0.1",
            "10.255.255.254",
            "10.1.2.3",
            # 192.168.0.0/16 range
            "192.168.0.1",
            "192.168.1.1",
            "192.168.255.254",
            # 172.16.0.0/12 range (172.16.0.0 - 172.31.255.255)
            "172.16.0.1",
            "172.31.255.254",
            "172.20.10.5",
        ],
    )
    def test_private_ip_blocked(self, monkeypatch, ip):
        """Given: একটি প্রাইভেট subnet IP।
        When: _check_ip_safety(ip) কল করা হয়।
        Then: is_safe=False "private IP" — boundary coverage সহ।
        """
        # Given
        protection = SSRFProtection()

        # When: সরাসরি IP-safety চেক (network resolution ছাড়া)
        result = protection._check_ip_safety(ip, "test.example.com")

        # Then: প্রাইভেট IP ব্লক
        assert result.is_safe is False
        assert "private" in result.reason.lower()

    def test_private_subnet_boundary_172_15_not_blocked(self, monkeypatch):
        """Given: 172.15.x.x (12-bit subnet এর বাইরে, পাবলিক)।
        When: _check_ip_safety("172.15.0.1") কল করা হয়।
        Then: is_safe=True — boundary test (172.16.0.0/12 শুরু হয় 172.16.0.0 থেকে)।
        """
        # Given
        protection = SSRFProtection()

        # When: 172.15.x.x প্রাইভেট সাবনেটের বাইরে
        result = protection._check_ip_safety("172.15.0.1", "test.example.com")

        # Then: পাবলিক
        assert result.is_safe is True

    def test_private_subnet_boundary_172_32_not_blocked(self, monkeypatch):
        """Given: 172.32.x.x (12-bit subnet এর উপরে, পাবলিক)।
        When: _check_ip_safety("172.32.0.1")।
        Then: is_safe=True — boundary test (172.16.0.0/12 শেষ 172.31.255.255)।
        """
        # Given
        protection = SSRFProtection()

        # When
        result = protection._check_ip_safety("172.32.0.1", "test.example.com")

        # Then
        assert result.is_safe is True

    @pytest.mark.parametrize(
        "url,ip",
        [
            ("http://internal.corp/", "10.0.0.5"),
            ("http://router.local/", "192.168.1.1"),
            ("http://intranet.lan/", "172.16.0.50"),
        ],
    )
    def test_internal_hostname_suffix_blocked(self, monkeypatch, url, ip):
        """Given: URL যার hostname এর শেষে .corp/.local/.lan suffix।
        When: validate_url()।
        Then: is_safe=False "internal hostname suffix" — hostname-level block।
        """
        # Given
        _patch_dns(monkeypatch, {})
        protection = SSRFProtection()

        # When
        result = protection.validate_url(url)

        # Then: বাংলা: hostname suffix ব্লক (DNS resolve হওয়ার আগেই)
        assert result.is_safe is False
        assert "suffix" in result.reason.lower() or "hostname" in result.reason.lower()


# ============================================================
# 3. Cloud Metadata IP ব্লক কন্ট্র্যাক্ট
# ============================================================
class TestCloudMetadataIPBlocked:
    """169.254.169.254 (AWS/GCP/Azure), 169.254.170.2 (ECS), 100.100.100.200 (Aliyun)।"""

    @pytest.mark.parametrize(
        "ip,description",
        [
            ("169.254.169.254", "AWS/GCP/Azure IMDS"),
            ("169.254.170.2", "AWS ECS task metadata"),
            ("100.100.100.200", "Alibaba Cloud metadata"),
        ],
    )
    def test_metadata_ip_blocked(self, ip, description):
        """Given: একটি cloud metadata IP।
        When: _check_ip_safety(ip)।
        Then: is_safe=False "metadata IP"।
        """
        # Given
        protection = SSRFProtection()

        # When
        result = protection._check_ip_safety(ip, "metadata.test")

        # Then: বাংলা: cloud metadata IP কখনো access করা যাবে না
        assert result.is_safe is False
        assert "metadata" in result.reason.lower()

    def test_aws_metadata_endpoint_via_url(self, monkeypatch):
        """Given: http://169.254.169.254/latest/meta-data/ URL।
        When: validate_url()।
        Then: is_safe=False — IMDSv1 attack blocked।
        """
        # Given
        protection = SSRFProtection()

        # When
        result = protection.validate_url("http://169.254.169.254/latest/meta-data/")

        # Then
        assert result.is_safe is False
        assert "metadata" in result.reason.lower()

    def test_aws_ecs_metadata_endpoint(self, monkeypatch):
        """Given: http://169.254.170.2/ URL (ECS task metadata)।
        When: validate_url()।
        Then: is_safe=False।
        """
        # Given
        protection = SSRFProtection()

        # When
        result = protection.validate_url("http://169.254.170.2/v2/metadata")

        # Then
        assert result.is_safe is False

    def test_link_local_range_blocked(self, monkeypatch):
        """Given: 169.254.x.x link-local IP (metadata IP ছাড়াও)।
        When: _check_ip_safety("169.254.5.5")।
        Then: is_safe=False — বাংলা নোট: Python ipaddress মডিউলে is_private
              ও is_link_local উভয়ই True হয় 169.254.x.x-এর জন্য, এবং আসল কোড
              is_private check আগে করে বলে reason "private IP" আসে।
              কন্ট্র্যাক্ট: link-local IP কখনো accept হবে না (যে কারণেই ব্লক হোক)।
        """
        # Given
        protection = SSRFProtection()

        # When: link-local range-এর অন্য একটি IP (169.254.169.254 ছাড়া)
        result = protection._check_ip_safety("169.254.5.5", "test.local")

        # Then: বাংলা: কোনো কারণেই accept নয় — হয় "private" বা "link-local"
        assert result.is_safe is False
        reason_lower = result.reason.lower()
        assert (
            "private" in reason_lower or "link-local" in reason_lower or "metadata" in reason_lower
        )


# ============================================================
# 4. Public URL Allowed কন্ট্র্যাক্ট (Happy Path)
# ============================================================
class TestPublicURLsAllowed:
    """পাবলিক IP / hostname — happy path, কোনো false positive নয়।"""

    @pytest.mark.parametrize(
        "url,hostname,ip",
        [
            ("https://example.com/", "example.com", "93.184.216.34"),
            ("https://www.google.com/", "www.google.com", "142.250.80.46"),
            ("http://8.8.8.8/", "8.8.8.8", "8.8.8.8"),
            ("https://1.1.1.1/dns-query", "1.1.1.1", "1.1.1.1"),
            ("https://github.com/supremeai/repo", "github.com", "140.82.121.4"),
        ],
    )
    def test_public_url_allowed(self, monkeypatch, url, hostname, ip):
        """Given: একটি পাবলিক URL যা পাবলিক IP-তে resolve হয়।
        When: validate_url()।
        Then: is_safe=True — happy path।
        """
        # Given: DNS মক করে পাবলিক IP রিটার্ন করছি
        _patch_dns(monkeypatch, {hostname: ip})
        protection = SSRFProtection()

        # When
        result = protection.validate_url(url)

        # Then
        assert result.is_safe is True, f"Expected safe, got: {result.reason}"
        assert result.resolved_ip == ip

    def test_public_url_returns_validation_result_object(self, monkeypatch):
        """Given: পাবলিক URL।
        When: validate_url()।
        Then: SSRFValidationResult instance সঠিক fields সহ রিটার্ন হয়।
        """
        # Given
        _patch_dns(monkeypatch, {"example.com": "93.184.216.34"})
        protection = SSRFProtection()

        # When
        result = protection.validate_url("https://example.com/path?q=1")

        # Then
        assert isinstance(result, SSRFValidationResult)
        assert result.is_safe is True
        assert result.reason == "OK"
        assert result.resolved_ip == "93.184.216.34"
        assert result.validated_url == "https://example.com/path?q=1"
        assert result.validation_time_ms >= 0

    def test_is_safe_url_backward_compatible_wrapper(self, monkeypatch):
        """Given: পাবলিক URL।
        When: is_safe_url() legacy wrapper কল করা হয়।
        Then: True রিটার্ন করে।
        """
        # Given
        _patch_dns(monkeypatch, {"example.com": "93.184.216.34"})

        # When
        result = is_safe_url("https://example.com/")

        # Then
        assert result is True


# ============================================================
# 5. DNS Rebinding Prevention কন্ট্র্যাক্ট
# ============================================================
class TestDNSRebindingPrevention:
    """DNS rebinding: প্রথম resolve পাবলিক, দ্বিতীয় resolve প্রাইভেট → ব্লক।"""

    def test_dns_rebinding_attack_blocked(self, monkeypatch):
        """Given: প্রথম DNS lookup পাবলিক IP, দ্বিতীয়টি প্রাইভেট IP।
        When: validate_url() — double-resolution check।
        Then: is_safe=False "DNS rebinding" — protocol bypass blocked।
        """
        # Given
        # বাংলা: DNS rebinding attack সিমুলেট করছি — প্রথম কলে পাবলিক IP,
        # দ্বিতীয় কলে প্রাইভেট IP (10.0.0.1) রিটার্ন করছি।
        call_count = {"n": 0}
        rebinding_seq = ["93.184.216.34", "10.0.0.1"]  # public → private

        def _rebinding_gethostbyname(host: str) -> str:
            idx = min(call_count["n"], len(rebinding_seq) - 1)
            ip = rebinding_seq[idx]
            call_count["n"] += 1
            return ip

        def _rebinding_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            idx = min(call_count["n"], len(rebinding_seq) - 1)
            ip = rebinding_seq[idx]
            call_count["n"] += 1
            return [(family, type, proto, "", (ip, port))]

        monkeypatch.setattr(socket, "gethostbyname", _rebinding_gethostbyname)
        monkeypatch.setattr(socket, "getaddrinfo", _rebinding_getaddrinfo)

        protection = SSRFProtection(enable_dns_rebinding_protection=True)

        # When
        result = protection.validate_url("http://rebinding.attacker.com/")

        # Then: বাংলা: DNS rebinding detected — protocol bypass ব্লক হয়েছে
        assert result.is_safe is False
        assert "rebinding" in result.reason.lower()

    def test_dns_round_robin_does_not_trigger_rebinding(self, monkeypatch):
        """Given: DNS round-robin — দুটি আলাদা পাবলিক IP (CDN সাধারণ প্যাটার্ন)।
        When: validate_url()।
        Then: is_safe=True — round-robin legitimate, false positive নয়।
        """
        # Given
        # বাংলা: CDN/DNS round-robin প্যাটার্ন — দুটি আলাদা পাবলিক IP, কিন্তু দুটোই
        # পাবলিক, তাই এটি rebinding নয়।
        call_count = {"n": 0}
        public_ips = ["93.184.216.34", "104.16.85.20"]

        def _round_robin_gethostbyname(host: str) -> str:
            idx = min(call_count["n"], len(public_ips) - 1)
            ip = public_ips[idx]
            call_count["n"] += 1
            return ip

        def _round_robin_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            idx = min(call_count["n"], len(public_ips) - 1)
            ip = public_ips[idx]
            call_count["n"] += 1
            return [(family, type, proto, "", (ip, port))]

        monkeypatch.setattr(socket, "gethostbyname", _round_robin_gethostbyname)
        monkeypatch.setattr(socket, "getaddrinfo", _round_robin_getaddrinfo)

        protection = SSRFProtection(enable_dns_rebinding_protection=True)

        # When
        result = protection.validate_url("https://cdn.example.com/")

        # Then: round-robin পাবলিক IP — legitimate, ব্লক হবে না
        assert result.is_safe is True, f"Expected safe, got: {result.reason}"

    def test_dns_rebinding_protection_can_be_disabled(self, monkeypatch):
        """Given: DNS rebinding protection disabled + IP প্রথম পাবলিক, দ্বিতীয় প্রাইভেট।
        When: validate_url()।
        Then: is_safe=True — disabled হলে rebinding check skip হয়।
        """
        # Given
        call_count = {"n": 0}
        rebinding_seq = ["93.184.216.34", "10.0.0.1"]

        def _rebinding_gethostbyname(host: str) -> str:
            idx = min(call_count["n"], len(rebinding_seq) - 1)
            ip = rebinding_seq[idx]
            call_count["n"] += 1
            return ip

        def _rebinding_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            idx = min(call_count["n"], len(rebinding_seq) - 1)
            ip = rebinding_seq[idx]
            call_count["n"] += 1
            return [(family, type, proto, "", (ip, port))]

        monkeypatch.setattr(socket, "gethostbyname", _rebinding_gethostbyname)
        monkeypatch.setattr(socket, "getaddrinfo", _rebinding_getaddrinfo)

        # বাংলা: protection disabled
        protection = SSRFProtection(enable_dns_rebinding_protection=False)

        # When
        result = protection.validate_url("http://rebinding.attacker.com/")

        # Then: বাংলা: rebinding protection বন্ধ থাকলে first resolution পাবলিক,
        # তাই সেফ রিপোর্ট করে (যদিও আসলে প্রাইভেট IP হয়ে যেতে পারত)।
        assert result.is_safe is True


# ============================================================
# 6. URL Scheme Validation কন্ট্র্যাক্ট
# ============================================================
class TestURISchemeValidation:
    """শুধু http/https allow — file://, ftp://, gopher://, dict:// ব্লক।"""

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://ftp.example.com/file",
            "gopher://gopher.example.com/",
            "dict://dict.example.com/",
            "ldap://ldap.example.com/",
            "jar://http://example.com/!/",
            "",
            "   ",
        ],
    )
    def test_non_http_schemes_blocked(self, monkeypatch, url):
        """Given: non-http(s) URL বা malformed URL।
        When: validate_url()।
        Then: is_safe=False — protocol bypass blocked।
        """
        # Given
        _patch_dns(monkeypatch, {})
        protection = SSRFProtection()

        # When
        result = protection.validate_url(url)

        # Then
        assert result.is_safe is False
        # বাংলা: কারণ scheme, না হলেও hostname missing — যেকোনো কারণে ব্লক
        assert result.reason != ""

    def test_https_scheme_allowed(self, monkeypatch):
        """Given: https://example.com/ (পাবলিক)।
        When: validate_url()।
        Then: is_safe=True — https allow।
        """
        # Given
        _patch_dns(monkeypatch, {"example.com": "93.184.216.34"})
        protection = SSRFProtection()

        # When
        result = protection.validate_url("https://example.com/secure")

        # Then
        assert result.is_safe is True

    def test_http_scheme_allowed(self, monkeypatch):
        """Given: http://example.com/ (পাবলিক, non-TLS)।
        When: validate_url()।
        Then: is_safe=True — http-ও allow।
        """
        # Given
        _patch_dns(monkeypatch, {"example.com": "93.184.216.34"})
        protection = SSRFProtection()

        # When
        result = protection.validate_url("http://example.com/insecure")

        # Then
        assert result.is_safe is True

    def test_url_with_no_hostname_blocked(self, monkeypatch):
        """Given: URL "http://" (কোনো hostname নেই)।
        When: validate_url()।
        Then: is_safe=False "no hostname" — boundary test।
        """
        # Given
        protection = SSRFProtection()

        # When
        result = protection.validate_url("http://")

        # Then
        assert result.is_safe is False
        assert "hostname" in result.reason.lower()


# ============================================================
# 7. Custom Blocklist + Singleton কন্ট্র্যাক্ট
# ============================================================
class TestCustomBlocklistAndSingleton:
    """Custom blocklist + get_ssrf_protection singleton কন্ট্র্যাক্ট।"""

    def test_custom_blocklist_blocks_hostname(self, monkeypatch):
        """Given: custom_blocklist={"evil.attacker.com"}।
        When: validate_url("http://evil.attacker.com/")।
        Then: is_safe=False "blocklist"।
        """
        # Given
        protection = SSRFProtection(custom_blocklist={"evil.attacker.com"})

        # When
        result = protection.validate_url("http://evil.attacker.com/")

        # Then: বাংলা: custom blocklist-এ যোগ হয়েছে
        assert result.is_safe is False
        assert "blocklist" in result.reason.lower()

    def test_env_var_blocklist_blocks_hostname(self, monkeypatch):
        """Given: SSRF_BLOCKLIST_HOSTNAMES env var set।
        When: validate_url()।
        Then: env var hostname ব্লক হয়।
        """
        # Given
        monkeypatch.setenv("SSRF_BLOCKLIST_HOSTNAMES", "blocked.example.org,evil.example.com")
        protection = SSRFProtection()

        # When
        result = protection.validate_url("http://blocked.example.org/")

        # Then
        assert result.is_safe is False
        assert "blocklist" in result.reason.lower()

    def test_singleton_returns_same_instance(self):
        """Given: SSRFProtection singleton।
        When: get_ssrf_protection() দুবার কল করা হয়।
        Then: একই instance রিটার্ন করে।
        """
        # Given
        from core.security.protection.ssrf_protection import get_ssrf_protection

        # When
        first = get_ssrf_protection()
        second = get_ssrf_protection()

        # Then
        assert first is second

    def test_dns_cache_size_increases_after_resolution(self, monkeypatch):
        """Given: নতুন SSRFProtection, empty DNS cache।
        When: একটি পাবলিক URL validate করা হয়।
        Then: DNS cache size বেড়েছে।
        """
        # Given
        _patch_dns(monkeypatch, {"unique.example.com": "93.184.216.34"})
        protection = SSRFProtection()
        assert protection.dns_cache_size == 0

        # When
        protection.validate_url("https://unique.example.com/")

        # Then: DNS cache populated
        assert protection.dns_cache_size == 1

    def test_clear_dns_cache_empties_state(self, monkeypatch):
        """Given: DNS cache populated।
        When: clear_dns_cache() কল করা হয়।
        Then: cache size 0।
        """
        # Given
        _patch_dns(monkeypatch, {"cached.example.com": "93.184.216.34"})
        protection = SSRFProtection()
        protection.validate_url("https://cached.example.com/")
        assert protection.dns_cache_size == 1

        # When
        protection.clear_dns_cache()

        # Then
        assert protection.dns_cache_size == 0

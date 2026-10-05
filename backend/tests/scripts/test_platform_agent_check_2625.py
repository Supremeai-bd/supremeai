#!/usr/bin/env python3
"""#2625 — platform-sweep probe hardening: শ্রেণীবিভাগ + অ্যালার্ট-প্লাম্বিং টেস্ট।

বাংলা: platform_agent_check.py-এর তিনটি #2625-চুক্তি —
  ১. models() 403 → ok=None environment-skip (CF-1010/JSON-Forbidden); 401 → WARN (#3260); 5xx → FAIL
  ২. mirror 6-24h WARN ব্যান্ড → alert=True (upsert-র ⚠️ সেকশনে পৌঁছায়)
  ৩. http() ডিফল্ট User-Agent (Python-urllib-নির্ভর CF-1010 ব্লক এড়াতে)
importlib-লোড + monkeypatch — কোনো নেটওয়ার্ক কল হয় না।
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "platform_agent_check.py"


def _load():
    if str(SCRIPT.parent) not in sys.path:
        sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("platform_agent_check_2625", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def pac():
    mod = _load()
    mod.results.clear()
    yield mod
    mod.results.clear()


CF_PAGE = "<!DOCTYPE html><html><!-- error code: 1010 cloudflare --></html>"


def _fake_http_factory(responses: dict):
    """url → (status, body); অজানা url → (0, 'network', {})"""

    def fake(method, url, *, headers=None, body=None, timeout=12):
        return responses.get(url, (0, "network-unreachable", {}))

    return fake


class TestModelsClassification:
    """#2625 চুক্তি ১ — 403 ≠ প্রোভাইডার আউটেজ; 401/5xx/নেটওয়ার্ক-ই আসল ফেইল।"""

    def test_403_cf1010_is_environment_skip(self, pac, monkeypatch):
        monkeypatch.setattr(
            pac,
            "http",
            _fake_http_factory(
                {
                    "https://api.cerebras.ai/v1/models": (403, CF_PAGE, {}),
                }
            ),
        )
        pac.probe_ai_providers({"CEREBRAS_API_KEY": "k"})
        r = [x for x in pac.results if x["platform"] == "cerebras"][0]
        assert r["ok"] is None, "403 CF-1010 এখন SKIP হওয়ার কথা (environment-skip)"
        assert "CF-1010" in r["detail"] or "WAF" in r["detail"]

    def test_403_json_is_environment_skip(self, pac, monkeypatch):
        monkeypatch.setattr(
            pac,
            "http",
            _fake_http_factory(
                {
                    "https://api.groq.com/openai/v1/models": (
                        403,
                        '{"error":{"message":"Forbidden"}}',
                        {},
                    ),
                }
            ),
        )
        pac.probe_ai_providers({"GROQ_API_KEY": "k"})
        r = [x for x in pac.results if x["platform"] == "groq"][0]
        assert r["ok"] is None
        assert "provider-side 403" in r["detail"]

    def test_401_is_warn(self, pac, monkeypatch):
        # বাংলা (#3288): #3260-এর পর 401 AUTH_INVALID এখন WARN (ok=None, alert=True),
        # FAIL (ok=False) নয় — কারণ credentials issue platform outage নয়, আলাদা tracked (#3228)।
        monkeypatch.setattr(
            pac,
            "http",
            _fake_http_factory(
                {
                    "https://api.openai.com/v1/models": (401, '{"error":"invalid key"}', {}),
                }
            ),
        )
        pac.probe_ai_providers({"OPENAI_API_KEY": "k"})
        r = [x for x in pac.results if x["platform"] == "openai"][0]
        assert r["ok"] is None, "401 = WARN (#3260) — ok=None, alert=True (not FAIL)"

    def test_5xx_is_fail(self, pac, monkeypatch):
        monkeypatch.setattr(
            pac,
            "http",
            _fake_http_factory(
                {
                    "https://api.mistral.ai/v1/models": (503, "upstream overloaded", {}),
                }
            ),
        )
        pac.probe_ai_providers({"MISTRAL_API_KEY": "k"})
        r = [x for x in pac.results if x["platform"] == "mistral"][0]
        assert r["ok"] is False

    def test_200_pass_unchanged(self, pac, monkeypatch):
        monkeypatch.setattr(
            pac,
            "http",
            _fake_http_factory(
                {
                    "https://api.groq.com/openai/v1/models": (200, '{"data": []}', {}),
                }
            ),
        )
        pac.probe_ai_providers({"GROQ_API_KEY": "k"})
        r = [x for x in pac.results if x["platform"] == "groq"][0]
        assert r["ok"] is True


class TestMirrorWarnAlert:
    """#2625 চুক্তি ২ — mirror 6-24h WARN ব্যান্ড alert=True (upsert-পাথে ওঠে)।"""

    def _mirror_http(self, hours: float):
        pushed = (datetime.now(UTC) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

        def fake(method, url, *, headers=None, body=None, timeout=12):
            if url.endswith("/repos/paykaribazaronline/supremeai"):
                return 200, f'{{"pushed_at": "{pushed}"}}', {}
            return 0, "network-unreachable", {}

        return fake

    def test_target_12h_is_alert_not_fail(self, pac, monkeypatch):
        monkeypatch.setattr(pac, "http", self._mirror_http(12.0))
        pac.probe_mirror({})  # no gitlab token → gitlab SKIP
        tgt = [
            x for x in pac.results if x["platform"] == "mirror" and x["check"] == "target freshness"
        ][0]
        assert tgt["ok"] is None
        assert tgt.get("alert") is True, "WARN ব্যান্ডের alert=True হওয়ার কথা (#2625)"

    def test_target_2h_is_pass_no_alert(self, pac, monkeypatch):
        monkeypatch.setattr(pac, "http", self._mirror_http(2.0))
        pac.probe_mirror({})
        tgt = [
            x for x in pac.results if x["platform"] == "mirror" and x["check"] == "target freshness"
        ][0]
        assert tgt["ok"] is True and not tgt.get("alert")

    def test_target_30h_is_fail(self, pac, monkeypatch):
        monkeypatch.setattr(pac, "http", self._mirror_http(30.0))
        pac.probe_mirror({})
        tgt = [
            x for x in pac.results if x["platform"] == "mirror" and x["check"] == "target freshness"
        ][0]
        assert tgt["ok"] is False and not tgt.get("alert")


class TestUpsertAlertSection:
    """#2625 চুক্তি ২-এর প্লাম্বিং — upsert_issue এখন alerts= নেয়, ⚠️ সেকশন বানায়।"""

    def test_alert_only_upsert_creates_issue_with_warn_section(self, pac, monkeypatch):
        monkeypatch.setattr(pac, "ensure_label", lambda: None)
        captured = {}

        def fake_gh_api(method, path, payload=None):
            if method == "GET":
                return 200, {"items": []}
            captured["payload"] = payload
            return 201, {"number": 4242}

        monkeypatch.setattr(pac, "gh_api", fake_gh_api)
        alert = {
            "platform": "mirror",
            "check": "target freshness",
            "detail": "target 12.0h behind — WARN",
        }
        pac.upsert_issue([], "https://run", alerts=[alert])
        assert "payload" in captured, "alerts-only কলেও issue তৈরি/আপডেট হওয়ার কথা"
        assert "⚠️ Alerts" in captured["payload"]["body"]
        assert "12.0h behind" in captured["payload"]["body"]


class TestDefaultUserAgent:
    """#2625 চুক্তি ৩ — http() ডিফল্ট UA (caller-override সম্ভব)।"""

    def test_default_ua_set_on_request(self, pac, monkeypatch):
        seen = {}

        class _Res:
            status = 200

            def read(self):
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=12):
            seen["headers"] = {k: v for k, v in req.header_items()}
            return _Res()

        monkeypatch.setattr(pac.urllib.request, "urlopen", fake_urlopen)
        pac.http("GET", "https://example.invalid/x")
        ua = seen["headers"].get("User-agent") or seen["headers"].get("User-Agent")
        assert ua and ua.startswith("SupremeAI-PlatformSweep/"), f"UA সেট হওয়ার কথা, পেলাম: {ua!r}"

    def test_caller_header_override_wins(self, pac, monkeypatch):
        seen = {}

        class _Res:
            status = 200

            def read(self):
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=12):
            seen["headers"] = {k: v for k, v in req.header_items()}
            return _Res()

        monkeypatch.setattr(pac.urllib.request, "urlopen", fake_urlopen)
        pac.http("GET", "https://example.invalid/x", headers={"User-Agent": "custom-agent/1.0"})
        ua = seen["headers"].get("User-agent") or seen["headers"].get("User-Agent")
        assert ua == "custom-agent/1.0", "caller-override এখনো কার্যকর থাকার কথা"

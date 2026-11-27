"""SSRF regression tests for ``tools.browser.web_scraper`` (audit 2026-11-24).

The module used to call ``httpx.get(url, follow_redirects=True)`` with only a
parse-time ``is_safe_url`` — a redirect (or an internal target reached via a
relative Location) sailed straight through into private space. The rewrite
walks redirects manually and re-validates every hop; these tests pin that.
All HTTP is scripted — no network access.
"""

from __future__ import annotations

import httpx
import pytest

from pathlib import Path
import importlib.util

# Import by file path so the test always exercises the canonical
# ``core/tools/browser/web_scraper.py`` regardless of sys.path order (the old
# ``browser/tools`` shadow copy that once made ``tools`` ambiguous is removed).
_MODULE_PATH = Path(__file__).resolve().parents[3] / "core" / "tools" / "browser" / "web_scraper.py"
_spec = importlib.util.spec_from_file_location("supremeai_core_tools_browser_web_scraper", _MODULE_PATH)
ws = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ws)

HTML = "<html><head><title>T</title></head><body><p>hello</p></body></html>"


def _response(status: int, *, location: str | None = None, url: str) -> httpx.Response:
    headers = {"location": location} if location is not None else {}
    request = httpx.Request("GET", url)
    return httpx.Response(status, headers=headers, request=request, text=HTML)


class FakeClient:
    def __init__(self, scripted):
        self.scripted = scripted
        self.requested: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url: str) -> httpx.Response:
        self.requested.append(url)
        for prefix, resp in self.scripted:
            if url.startswith(prefix):
                return resp
        raise AssertionError(f"unexpected fetch: {url}")


def _install(monkeypatch: pytest.MonkeyPatch, scripted, safe=lambda url: True) -> FakeClient:
    client = FakeClient(scripted)
    monkeypatch.setattr(ws, "is_safe_url", safe)
    monkeypatch.setattr(ws.httpx, "Client", lambda *a, **k: client)
    return client


def test_redirect_into_private_target_is_blocked(monkeypatch):
    def safe(url: str) -> bool:
        return url.startswith("https://") and not url.startswith("https://169.254.169.254")

    scripted = [
        ("https://example.com/start",
         _response(302, location="https://169.254.169.254/latest/meta-data", url="https://example.com/start")),
    ]
    client = _install(monkeypatch, scripted, safe=safe)

    result = ws.WebScraper().fetch_page("https://example.com/start")

    assert result["success"] is False
    assert "redirect" in result["error"].lower()
    # The private target must never be fetched.
    assert client.requested == ["https://example.com/start"]


def test_relative_redirect_is_resolved_and_followed(monkeypatch):
    scripted = [
        ("https://example.com/start",
         _response(302, location="/next", url="https://example.com/start")),
        ("https://example.com/next", _response(200, url="https://example.com/next")),
    ]
    client = _install(monkeypatch, scripted)

    result = ws.WebScraper().fetch_page("https://example.com/start")

    assert result["success"] is True
    assert result["title"] == "T"
    assert client.requested == ["https://example.com/start", "https://example.com/next"]


def test_redirect_chain_is_bounded(monkeypatch):
    hops = [
        ("https://example.com/h0",
         _response(302, location="https://example.com/h1", url="https://example.com/h0")),
    ] + [
        (f"https://example.com/h{i}",
         _response(302, location=f"https://example.com/h{i + 1}", url=f"https://example.com/h{i}"))
        for i in range(1, 6)
    ]
    client = _install(monkeypatch, hops)

    result = ws.WebScraper().fetch_page("https://example.com/h0")

    assert result["success"] is False
    assert "redirect" in result["error"].lower()
    assert len(client.requested) <= ws._MAX_REDIRECTS + 1


def test_initial_unsafe_url_returns_failure_without_fetching(monkeypatch):
    client = _install(monkeypatch, [], safe=lambda url: False)

    result = ws.WebScraper().fetch_page("http://169.254.169.254/")

    assert result["success"] is False
    assert client.requested == []


def test_redirect_to_unsafe_scheme_is_blocked(monkeypatch):
    def safe(url: str) -> bool:
        return url.startswith("https://")

    scripted = [
        ("https://example.com/start",
         _response(302, location="file:///etc/passwd", url="https://example.com/start")),
    ]
    client = _install(monkeypatch, scripted, safe=safe)

    result = ws.WebScraper().fetch_page("https://example.com/start")

    assert result["success"] is False
    assert client.requested == ["https://example.com/start"]

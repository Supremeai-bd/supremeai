"""Search SSOT consolidation tests (issue #1751).

Restores the core search SSOT validation suite pruned in PR #4995.
Tiers verified offline (no network, stdlib + installed deps only):
1. Behavioral: core.search.web_search provider selection (Brave, Tavily, DDGS fallback).
2. Acceptance regression: no bot-hostile duckduckgo.com/html endpoints left in open surfaces.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

import pytest

from core import search as search_mod
from core.search import web_search

REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    """Stands in for httpx.Client; records requests, serves queued payloads."""

    calls: ClassVar[list[dict[str, Any]]] = []
    payloads: ClassVar[list[dict[str, Any]]] = []
    explode: bool = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def _record(self, method: str, url: Any, **kwargs: Any) -> _FakeResponse:
        _FakeClient.calls.append(
            {"method": method, "url": str(url), **{k: v for k, v in kwargs.items()}}
        )
        if _FakeClient.explode:
            raise RuntimeError("transport down (simulated)")
        return _FakeResponse(_FakeClient.payloads.pop(0) if _FakeClient.payloads else {})

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        return self._record("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        return self._record("POST", url, **kwargs)


@pytest.fixture()
def fake_http(monkeypatch: pytest.MonkeyPatch) -> type[_FakeClient]:
    _FakeClient.calls = []
    _FakeClient.payloads = []
    _FakeClient.explode = False
    monkeypatch.setattr("httpx.Client", _FakeClient)
    return _FakeClient


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """No stray provider keys — tests opt in explicitly via setenv."""
    for env_name, _provider in getattr(search_mod, "_KEYED_PROVIDERS", []):
        monkeypatch.delenv(env_name, raising=False)


@pytest.fixture()
def ddgs_spy(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    seen: list[tuple[str, int]] = []

    def _fake_ddgs(query: str, max_results: int) -> list[dict[str, Any]]:
        seen.append((query, max_results))
        return [{"title": "ddgs-hit", "href": "https://ddg.example/x", "body": "free lane"}]

    monkeypatch.setattr(search_mod, "_ddgs_search", _fake_ddgs)
    return seen


# ------------------------------------------------------- tier 1: behavioral


def test_no_keys_keeps_zero_cost_ddgs_lane(ddgs_spy: list) -> None:
    """Key-less runs keep today's behavior: ddgs only, no provider traffic."""
    out = web_search("hello", max_results=3)
    assert _FakeClient.calls == []
    assert ddgs_spy == [("hello", 3)]
    assert out[0]["href"] == "https://ddg.example/x"


def test_brave_key_goes_provider_first(fake_http: type, ddgs_spy: list) -> None:
    """Keyed provider is tried BEFORE ddgs and its shape maps to the contract."""
    _FakeClient.payloads = [
        {
            "web": {
                "results": [
                    {
                        "title": "Brave Result",
                        "url": "https://brave.example/r1",
                        "description": "brave says hi",
                    }
                ]
            }
        }
    ]
    monkey_key = "test-brave-key"
    os.environ["SUPREME_SEARCH_BRAVE_KEY"] = monkey_key
    try:
        out = web_search("q", max_results=5)
    finally:
        os.environ.pop("SUPREME_SEARCH_BRAVE_KEY", None)

    assert len(_FakeClient.calls) == 1
    call = _FakeClient.calls[0]
    assert call["method"] == "GET"
    assert "api.search.brave.com" in call["url"]
    assert call["headers"]["X-Subscription-Token"] == monkey_key
    assert call["params"]["count"] == 5
    assert out == [
        {"title": "Brave Result", "href": "https://brave.example/r1", "body": "brave says hi"}
    ]
    assert ddgs_spy == []


def test_tavily_key_uses_bearer_post(fake_http: type, ddgs_spy: list) -> None:
    _FakeClient.payloads = [
        {
            "results": [
                {"title": "Tavily Result", "url": "https://tav.example/r1", "content": "tavily"}
            ]
        }
    ]
    os.environ["SUPREME_SEARCH_TAVILY_KEY"] = "test-tavily-key"
    try:
        out = web_search("q2", max_results=4)
    finally:
        os.environ.pop("SUPREME_SEARCH_TAVILY_KEY", None)

    call = _FakeClient.calls[0]
    assert call["method"] == "POST"
    assert "api.tavily.com" in call["url"]
    assert call["headers"]["Authorization"] == "Bearer test-tavily-key"
    assert call["json"]["max_results"] == 4
    assert out == [
        {"title": "Tavily Result", "href": "https://tav.example/r1", "body": "tavily"}
    ]
    assert ddgs_spy == []


def test_provider_transport_failure_falls_closed_to_ddgs(
    fake_http: type, ddgs_spy: list
) -> None:
    """Fail-closed doctrine: provider failure degrades to ddgs, never raises."""
    _FakeClient.explode = True
    os.environ["SUPREME_SEARCH_BRAVE_KEY"] = "k"
    try:
        out = web_search("q3", max_results=2)
    finally:
        os.environ.pop("SUPREME_SEARCH_BRAVE_KEY", None)

    assert ddgs_spy == [("q3", 2)]
    assert out[0]["title"] == "ddgs-hit"


def test_provider_empty_result_falls_through_to_ddgs(
    fake_http: type, ddgs_spy: list
) -> None:
    _FakeClient.payloads = [{"web": {"results": []}}]
    os.environ["SUPREME_SEARCH_BRAVE_KEY"] = "k"
    try:
        out = web_search("q4", max_results=2)
    finally:
        os.environ.pop("SUPREME_SEARCH_BRAVE_KEY", None)

    assert ddgs_spy == [("q4", 2)]
    assert out[0]["title"] == "ddgs-hit"


def test_web_search_signature_is_stable() -> None:
    """Callers across the repo rely on (query, max_results=5)."""
    import inspect

    sig = inspect.signature(web_search)
    assert list(sig.parameters) == ["query", "max_results"]
    assert sig.parameters["max_results"].default == 5


# ------------------------------------------- tier 2: acceptance regression


def test_no_bot_hostile_ddg_html_endpoint_left_in_open_surfaces() -> None:
    """The issue's mechanical acceptance criterion: no legacy scraping endpoints."""
    offenders: list[str] = []
    for top in ("gateway", "core"):
        top_dir = REPO_ROOT / top
        if not top_dir.exists():
            continue
        for path in top_dir.rglob("*.py"):
            if "duckduckgo.com/html" in path.read_text(encoding="utf-8", errors="replace"):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == [], f"bot-hostile DDG-HTML scrape reappeared in: {offenders}"


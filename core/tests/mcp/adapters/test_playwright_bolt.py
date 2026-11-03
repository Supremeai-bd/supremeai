"""Bolt + Lovable adapter tests — MESH-5 (#943)।

বাংলা: playwright সম্পূর্ণ fake page/locator দিয়ে mock — কোনো ব্রাউজার
লঞ্চ নেই; Lovable httpx.MockTransport দিয়ে — কোনো নেটওয়ার্ক নেই।
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from mcp_adapters.adapters.playwright_bolt import BoltAdapter


# ── Fake playwright objects ──────────────────────────────────────────────────
class FakeLocator:
    def __init__(self, href: str | None = None):
        self._href = href

    @property
    def first(self) -> FakeLocator:
        return self

    def count(self) -> int:
        return 1 if self._href else 0

    def get_attribute(self, name: str) -> str | None:
        return self._href if name == "href" else None


class FakePage:
    def __init__(self, pr_url: str | None = "https://github.com/org/repo/pull/7"):
        self.url = "https://bolt.new/new"
        self.filled: list[tuple[str, str]] = []
        self.clicked: list[str] = []
        self.keys: list[str] = []
        self.navigated: list[str] = []
        self._pr_url = pr_url
        self.wait_calls = 0

    def goto(self, url: str, **kwargs) -> None:
        self.navigated.append(url)

    def fill(self, selector: str, value: str) -> None:
        self.filled.append((selector, value))

    def click(self, selector: str) -> None:
        self.clicked.append(selector)

    def keyboard(self):  # pragma: no cover — attribute style
        raise AssertionError

    def press_key(self, key: str) -> None:  # unused; keyboard.press path faked below
        self.keys.append(key)

    @property
    def keyboard_obj(self):  # noqa: ANN201
        return self

    def wait_for_timeout(self, ms: int) -> None:
        self.wait_calls += 1

    def locator(self, selector: str) -> FakeLocator:
        if "Export" in selector:
            return FakeLocator("present")  # count>0 → export ready
        if "github.com" in selector:
            return FakeLocator(self._pr_url)
        return FakeLocator("present")

    def evaluate(self, script: str) -> dict:
        return {}


class FakeKeyboard:
    def __init__(self, page: FakePage):
        self.page = page

    def press(self, key: str) -> None:
        self.page.keys.append(key)


def make_adapter(page: FakePage, monkeypatch) -> BoltAdapter:
    adapter = BoltAdapter()
    adapter._page = page  # noqa: SLF001 — টেস্ট injection
    adapter._browser = object()  # noqa: SLF001
    page.keyboard = FakeKeyboard(page)  # type: ignore[attr-defined]
    # playwright লাগবেই না — already started ধরা হচ্ছে
    monkeypatch.setattr(adapter, "_require_playwright", lambda: None)
    return adapter


def test_push_task_full_flow(monkeypatch):
    page = FakePage(pr_url="https://github.com/org/repo/pull/42")
    adapter = make_adapter(page, monkeypatch)
    url = adapter.push_task("task-42", "build a landing page", "mesh/task-task-42")
    assert url == "https://github.com/org/repo/pull/42"
    # ফ্লো: goto → fill spec → Enter → Export click → branch fill → Enter
    assert page.navigated == [BoltAdapter.BOLT_NEW_URL]
    assert any("build a landing page" in v for _sel, v in page.filled)
    assert any("Export to GitHub" in s for s in page.clicked)
    assert any(t == ("input[placeholder*='branch' i]", "mesh/task-task-42") for t in page.filled)
    assert "Enter" in page.keys


def test_push_task_default_branch_naming(monkeypatch):
    page = FakePage()
    adapter = make_adapter(page, monkeypatch)
    adapter.push_task("77", "spec", branch="")
    assert any(t[1] == "mesh/task-77" for t in page.filled)


def test_push_task_timeout_when_no_pr_url(monkeypatch):
    page = FakePage(pr_url=None)
    adapter = make_adapter(page, monkeypatch)
    adapter._wait_for_pr_url = lambda page_, timeout_seconds=180: (_ for _ in ()).throw(
        TimeoutError("PR URL never appeared")
    )
    with pytest.raises(TimeoutError):
        adapter.push_task("t1", "spec", "mesh/task-t1")


def test_adapter_unavailable_without_playwright(monkeypatch):
    adapter = BoltAdapter()
    monkeypatch.setattr("mcp_adapters.adapters.playwright_bolt.PLAYWRIGHT_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="playwright is not installed"):
        adapter._require_playwright()


# ── LovableAdapter ───────────────────────────────────────────────────────────
def test_lovable_fail_closed_without_token(monkeypatch):
    from mcp_adapters.adapters.lovable_adapter import LovableAdapter

    monkeypatch.delenv("LOVABLE_API_TOKEN", raising=False)
    adapter = LovableAdapter()
    assert adapter.configured is False
    code, data = asyncio.run(adapter.create_project("p", "spec"))
    assert code == 401 and "fail-closed" in data["detail"]


def test_lovable_create_project_calls_official_api(monkeypatch):
    from mcp_adapters.adapters.lovable_adapter import LovableAdapter

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        return httpx.Response(201, json={"id": "proj-1"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr("mcp_adapters.adapters.lovable_adapter.httpx.AsyncClient", factory)
    adapter = LovableAdapter(api_token="tok-1")
    code, data = asyncio.run(adapter.create_project("demo", "make a dashboard"))
    assert code == 201 and data["id"] == "proj-1"
    assert seen["auth"] == "Bearer tok-1"
    assert seen["url"].endswith("/v1/projects")


def test_lovable_network_error_never_raises(monkeypatch):
    from mcp_adapters.adapters.lovable_adapter import LovableAdapter

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr("mcp_adapters.adapters.lovable_adapter.httpx.AsyncClient", factory)
    adapter = LovableAdapter(api_token="t")
    code, data = asyncio.run(adapter.get_project("p1"))
    assert code == 0 and "unreachable" in str(data)

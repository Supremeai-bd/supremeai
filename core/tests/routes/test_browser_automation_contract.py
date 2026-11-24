"""Contract tests for the ``/api/browser/automation/*`` family (audit item ⑯).

These endpoints are the most dangerous surface in the product: they drive a real
Chromium (navigate / click / fill / screenshot) against pages a logged-in user
chooses. Before this file the whole family had **zero** tests — the only browser
route test covered the cookie vault.

What is pinned here (all offline: the session pool is faked, no Chromium):

* SSRF screening on every URL entry point (``sessions``, ``actions:navigate``,
  ``vault/execute``).
* Argument validation (missing selector/value → 422, unknown action → 422).
* Owner identity: ``get_current_user_token`` returns a dict, so the pool must be
  keyed by its ``sub`` claim. A dict key used to crash ``pause`` (unhashable)
  and made ``/automation/pause`` a no-op against live sessions.
* Honest status codes: paused owner → 423, unknown session → 404 (used to be a
  500 from an uncaught ``KeyError``), no browser → 503 (never a fake 200).
* Actionability: a locator that never becomes visible → 408 with the reason.

The suite intentionally does **not** assert that automation "works" — it asserts
that the API tells the truth about ownership, authorization and failure.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# NOTE: import through the canonical ``core.*`` name. Importing the same files as
# ``api.*`` (core/ is on pytest's pythonpath) executes the package a *second*
# time: the route modules then register on the ``core.api.routes.browser``
# router while the test holds the ``api.routes.browser`` one, so every request
# 404s. ``core/tests/routes/test_browser_vault_sync.py`` was broken exactly that
# way and is fixed alongside this file.
from core.api.deps import get_current_user_token
from core.api.routes.browser import router

OWNER = "owner-42"
SAFE_URL = "https://example.com/login"
UNSAFE_URL = "http://169.254.169.254/latest/meta-data/"


class _FakeLocator:
    def __init__(self, page: "_FakePage", selector: str, *, visible: bool = True) -> None:
        self._page = page
        self._selector = selector
        self._visible = visible

    async def wait_for(self, state: str = "visible", timeout: int = 0) -> None:
        if not self._visible:
            raise TimeoutError(f"{self._selector} stayed hidden for {timeout}ms")

    async def click(self, timeout: int = 0) -> None:
        self._page.calls.append(("click", self._selector))

    async def fill(self, value: str, timeout: int = 0) -> None:
        self._page.calls.append(("fill", self._selector, value))

    async def inner_text(self, timeout: int = 0) -> str:
        return f"text of {self._selector}"


class _FakePage:
    def __init__(self, *, visible: bool = True) -> None:
        self.url = "about:blank"
        self.calls: list[tuple[Any, ...]] = []
        self._visible = visible

    async def goto(self, url: str, **kwargs: Any) -> None:
        self.url = url
        self.calls.append(("goto", url))

    async def title(self) -> str:
        return "Example Domain"

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self, selector, visible=self._visible)

    async def screenshot(self, **kwargs: Any) -> bytes:
        return b"\x89PNG\r\n\x1a\n"

    async def go_back(self, **kwargs: Any) -> bool:
        return False

    async def go_forward(self, **kwargs: Any) -> bool:
        return False

    async def reload(self, **kwargs: Any) -> None:
        self.calls.append(("reload",))


class _FakeSession:
    def __init__(self, session_id: str, owner_id: str, page: _FakePage) -> None:
        self.id = session_id
        self.owner_id = owner_id
        self.page = page
        self.label = "test"
        self.saved_url = None
        self.allowed_actions = (
            "navigate",
            "click",
            "fill",
            "type",
            "screenshot",
            "content",
            "extract",
            "back",
            "forward",
            "reload",
        )


class _FakeSessionManager:
    """Same public shape as ``core.browser_session_manager.session_manager``."""

    def __init__(self) -> None:
        self.sessions: dict[str, _FakeSession] = {}
        self.paused: set[str] = set()
        self.create_error: Exception | None = None
        self.page_visible = True
        self.created_for: list[str] = []

    async def create(self, owner_id: str, label: str = "", saved_url=None, storage_state=None):
        if self.create_error is not None:
            raise self.create_error
        if owner_id in self.paused:
            raise PermissionError("Browser automation is paused for this owner")
        if not isinstance(owner_id, str):
            # Regression guard: a dict owner would break pause (unhashable) and
            # silently disable owner scoping.
            raise AssertionError(f"owner_id must be str, got {type(owner_id)!r}")
        self.created_for.append(owner_id)
        session = _FakeSession(f"bs_{len(self.sessions)}", owner_id, _FakePage(visible=self.page_visible))
        self.sessions[session.id] = session
        return session

    async def get(self, session_id: str, owner_id: str) -> _FakeSession:
        if owner_id in self.paused:
            raise PermissionError("Browser automation is paused for this owner")
        session = self.sessions.get(session_id)
        if session is None or session.owner_id != owner_id:
            raise KeyError("Browser session not found")
        return session

    async def close(self, session_id: str, owner_id: str) -> bool:
        session = self.sessions.get(session_id)
        if session is None or session.owner_id != owner_id:
            return False
        del self.sessions[session_id]
        return True

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {"session_id": s.id, "owner_id": s.owner_id, "url": s.page.url, "label": s.label}
            for s in self.sessions.values()
        ]

    def pause_owner(self, owner_id: str) -> None:
        self.paused.add(owner_id)  # raises TypeError if owner is a dict

    def resume_owner(self, owner_id: str) -> None:
        self.paused.discard(owner_id)

    def is_paused(self, owner_id: str) -> bool:
        return owner_id in self.paused


@pytest.fixture()
def fake_manager(monkeypatch):
    from core.api.routes.browser import _automation

    manager = _FakeSessionManager()
    monkeypatch.setattr(_automation, "session_manager", manager)
    return manager


@pytest.fixture()
def client(fake_manager):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_token] = lambda: {"sub": OWNER, "tenant_id": "t-1"}
    return TestClient(app)


@pytest.fixture()
def anonymous_client(fake_manager):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_token] = lambda: {"role": "user"}
    return TestClient(app)


# ── session lifecycle ────────────────────────────────────────────────────────


def test_create_session_uses_str_subject_as_owner(client, fake_manager):
    res = client.post("/api/browser/automation/sessions", json={"label": "Login flow"})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "ready"
    # dict-owner regression: pool must be keyed by the sub claim, not the payload
    assert fake_manager.created_for == [OWNER]


def test_create_session_rejects_unsafe_saved_url(client, fake_manager):
    res = client.post(
        "/api/browser/automation/sessions", json={"saved_url": UNSAFE_URL}
    )
    assert res.status_code == 400
    assert fake_manager.created_for == []  # never dialed


def test_create_session_reports_paused_owner_as_423(client, fake_manager):
    fake_manager.pause_owner(OWNER)
    res = client.post("/api/browser/automation/sessions", json={})
    assert res.status_code == 423


def test_create_session_reports_missing_browser_as_503(client, fake_manager):
    fake_manager.create_error = RuntimeError("chromium executable not found")
    res = client.post("/api/browser/automation/sessions", json={})
    assert res.status_code == 503
    assert "chromium" in res.json()["detail"]


def test_create_session_without_subject_is_401(anonymous_client):
    res = anonymous_client.post("/api/browser/automation/sessions", json={})
    assert res.status_code == 401


def test_list_sessions_is_owner_scoped(client, fake_manager):
    client.post("/api/browser/automation/sessions", json={"label": "mine"})
    fake_manager.sessions["bs_other"] = _FakeSession("bs_other", "someone-else", _FakePage())
    res = client.get("/api/browser/automation/sessions")
    assert res.status_code == 200
    sessions = res.json()["sessions"]
    assert [s["owner_id"] for s in sessions] == [OWNER]


def test_close_unknown_session_is_404(client):
    res = client.delete("/api/browser/automation/sessions/bs_missing")
    assert res.status_code == 404


def test_close_own_session_removes_it(client, fake_manager):
    created = client.post("/api/browser/automation/sessions", json={}).json()
    res = client.delete(f"/api/browser/automation/sessions/{created['session_id']}")
    assert res.status_code == 200
    assert fake_manager.sessions == {}


# ── pause / resume ───────────────────────────────────────────────────────────


def test_pause_then_actions_is_423_then_resume_restores(client, fake_manager):
    """The exact loop the unhashable-dict bug broke."""
    session_id = client.post("/api/browser/automation/sessions", json={}).json()["session_id"]

    assert client.post("/api/browser/automation/pause").json() == {"status": "paused"}
    blocked = client.post(
        "/api/browser/automation/actions",
        json={"session_id": session_id, "action": "navigate", "url": SAFE_URL},
    )
    assert blocked.status_code == 423  # paused really gates the action

    assert client.post("/api/browser/automation/resume").json() == {"status": "active"}
    ok = client.post(
        "/api/browser/automation/actions",
        json={"session_id": session_id, "action": "navigate", "url": SAFE_URL},
    )
    assert ok.status_code == 200, ok.text


# ── actions ─────────────────────────────────────────────────────────────────


def _new_session(client) -> str:
    return client.post("/api/browser/automation/sessions", json={}).json()["session_id"]


def test_action_navigate_validates_ssrf_and_records_goto(client, fake_manager):
    session_id = _new_session(client)
    bad = client.post(
        "/api/browser/automation/actions",
        json={"session_id": session_id, "action": "navigate", "url": UNSAFE_URL},
    )
    assert bad.status_code == 400
    assert fake_manager.sessions[session_id].page.calls == []  # no navigation attempted

    good = client.post(
        "/api/browser/automation/actions",
        json={"session_id": session_id, "action": "navigate", "url": SAFE_URL},
    )
    assert good.status_code == 200, good.text
    assert fake_manager.sessions[session_id].page.calls == [("goto", SAFE_URL)]
    assert good.json()["title"] == "Example Domain"


def test_action_click_requires_selector(client):
    session_id = _new_session(client)
    res = client.post(
        "/api/browser/automation/actions", json={"session_id": session_id, "action": "click"}
    )
    assert res.status_code == 422


def test_action_fill_requires_value(client):
    session_id = _new_session(client)
    res = client.post(
        "/api/browser/automation/actions",
        json={"session_id": session_id, "action": "fill", "selector": "#email"},
    )
    assert res.status_code == 422


def test_action_click_and_fill_reach_the_page(client, fake_manager):
    session_id = _new_session(client)
    client.post(
        "/api/browser/automation/actions",
        json={"session_id": session_id, "action": "click", "selector": "#submit"},
    )
    client.post(
        "/api/browser/automation/actions",
        json={"session_id": session_id, "action": "fill", "selector": "#email", "value": "a@b.c"},
    )
    assert fake_manager.sessions[session_id].page.calls == [
        ("click", "#submit"),
        ("fill", "#email", "a@b.c"),
    ]


def test_action_not_actionable_is_408_with_reason(client, fake_manager):
    session_id = _new_session(client)
    fake_manager.sessions[session_id].page._visible = False
    res = client.post(
        "/api/browser/automation/actions",
        json={"session_id": session_id, "action": "click", "selector": "#hidden"},
    )
    assert res.status_code == 408
    assert "#hidden" in res.json()["detail"]


def test_action_unknown_session_is_404(client):
    res = client.post(
        "/api/browser/automation/actions",
        json={"session_id": "bs_missing", "action": "content"},
    )
    assert res.status_code == 404


def test_action_unknown_verb_is_rejected_by_schema(client):
    session_id = _new_session(client)
    res = client.post(
        "/api/browser/automation/actions",
        json={"session_id": session_id, "action": "rm -rf"},
    )
    assert res.status_code == 422


def test_action_screenshot_returns_base64_png(client):
    session_id = _new_session(client)
    res = client.post(
        "/api/browser/automation/actions",
        json={"session_id": session_id, "action": "screenshot"},
    )
    assert res.status_code == 200
    assert res.json()["screenshot"].startswith("iVBORw0KGgo")  # base64 of \x89PNG


def test_action_extract_returns_body_text(client):
    session_id = _new_session(client)
    res = client.post(
        "/api/browser/automation/actions",
        json={"session_id": session_id, "action": "extract"},
    )
    assert res.status_code == 200
    assert res.json()["content"].startswith("text of body")


def test_action_back_without_history_is_409(client):
    session_id = _new_session(client)
    res = client.post(
        "/api/browser/automation/actions",
        json={"session_id": session_id, "action": "back"},
    )
    assert res.status_code == 409


# ── vault/execute SSRF gate ─────────────────────────────────────────────────


def test_vault_execute_rejects_unsafe_url(client, fake_manager):
    res = client.post(
        "/api/browser/automation/vault/execute",
        json={"service": "example.com", "url": UNSAFE_URL, "actions": []},
    )
    assert res.status_code == 400
    assert fake_manager.created_for == []


def test_vault_execute_without_service_claim_is_401(anonymous_client):
    res = anonymous_client.post(
        "/api/browser/automation/vault/execute",
        json={"service": "example.com", "url": SAFE_URL},
    )
    assert res.status_code == 401

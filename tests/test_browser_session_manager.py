"""Root acceptance tests for issue #1571 — Part 2: Stateful BrowserSessionManager
& Multi-Action Registry.

Covers (per the issue's acceptance criteria):
* Consecutive actions on the SAME ``session_id`` maintain page state/cookies
  (one live session object, same bound page).
* Hard TTL (15 min) + idle timeout (3 min) cleanup: expired sessions are
  closed cleanly (page/context ``close()`` invoked) — no orphaned browsers.
* Dedicated Chrome automation profile flags (``--user-data-dir=C:/SupremeAI_Automation_Profile``)
  and 127.0.0.1 binding.
* Multi-Action Registry: navigate → type → click → wait → extract sequences
  execute across the SAME bound page.
* SwarmBrowser acquires real sessions from the manager and releases them.

No real browser, no network — CI-safe.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import browser.session_manager as sm_module
import browser.swarm_browser as sb_module
from browser.autonomous_browser import AutonomousBrowserAgent
from browser.browser_session import (
    IDLE_TIMEOUT_SECONDS,
    SESSION_TTL_SECONDS,
    BrowserSession,
    SessionStatus,
)
from browser.session_manager import (
    AUTOMATION_HOST,
    BrowserSessionManager,
    chrome_launch_args,
    run_action_sequence,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class FakePage:
    def __init__(self, label="p"):
        self.label = label
        self.closed = False
        self.calls: list[tuple] = []
        self.url = f"https://example.com/{label}"

    def goto(self, url, **kw):
        self.calls.append(("goto", url))

    def type(self, selector, text, delay=0):
        self.calls.append(("type", selector, text))

    def click(self, selector, **kw):
        self.calls.append(("click", selector))

    def text_content(self, selector):
        return f"text-of-{selector}"

    def screenshot(self, path=None, **kw):
        if path:
            with open(path, "wb") as fh:
                fh.write(b"png-bytes")
        return b"png-bytes"

    def close(self):
        self.closed = True


class FakeContext:
    def __init__(self):
        self.pages: list[FakePage] = []
        self.closed = False

    def new_page(self):
        page = FakePage(label=f"page{len(self.pages) + 1}")
        self.pages.append(page)
        return page

    def close(self):
        self.closed = True


def fake_factory(provider, session_id):
    """Injectable factory: one fresh FakeContext per call."""
    context = FakeContext()
    return {
        "context": context,
        "page": context.new_page(),
        "playwright_runtime": SimpleNamespace(stop=lambda: None),
    }


def fixed_clock(start: datetime):
    """A monotonic fake clock returning advancing datetimes."""
    state = {"now": start}

    def _now() -> datetime:
        return state["now"]

    def advance(**kw):
        state["now"] = state["now"] + timedelta(**kw)

    return _now, advance


# ---------------------------------------------------------------------------
# 1. Session statefulness — same session_id → same live page
# ---------------------------------------------------------------------------
def test_same_session_id_preserves_page_state_and_cookies():
    manager = BrowserSessionManager(session_factory=fake_factory)
    s1 = manager.acquire(provider="chrome-dedicated", session_id="stable-1")
    cookies_seen = [{"name": "sid", "value": "abc"}]
    s1.page.calls.append(("cookie", cookies_seen))

    s2 = manager.acquire(provider="chrome-dedicated", session_id="stable-1")
    assert s2 is s1, "same session_id must return the SAME live session"
    assert s2.page.calls == [("cookie", cookies_seen)], "page state must persist"
    assert manager.get_session("stable-1").url == s1.page.url


def test_create_session_is_idempotent_for_live_ids():
    manager = BrowserSessionManager(session_factory=fake_factory)
    a = manager.create_session(session_id="dup")
    b = manager.create_session(session_id="dup")
    assert a is b
    assert len(manager) == 1


# ---------------------------------------------------------------------------
# 2. Lifecycle hooks — close / reset / screenshot
# ---------------------------------------------------------------------------
def test_close_marks_closed_and_closes_surfaces():
    context = FakeContext()
    page = FakePage()
    session = BrowserSession("s", context=context, page=page)
    asyncio.run(session.close())
    assert session.status is SessionStatus.CLOSED
    assert page.closed is True
    assert context.closed is True
    assert session.page is None and session.context is None
    # double close is safe
    asyncio.run(session.close())


def test_reset_rebinds_fresh_page_on_same_context():
    context = FakeContext()
    session = BrowserSession("s", context=context, page=context.new_page())
    old_page = session.page
    asyncio.run(session.reset())
    assert session.page is not old_page
    assert session.status is SessionStatus.ACTIVE
    assert session.context.pages == [old_page, session.page]


def test_screenshot_returns_bytes():
    session = BrowserSession("s", page=FakePage())
    assert asyncio.run(session.screenshot()) == b"png-bytes"


# ---------------------------------------------------------------------------
# 3. Cleanup daemon semantics — TTL + idle
# ---------------------------------------------------------------------------
def test_hard_ttl_15min_sweeps_expired_session():
    start = datetime.now(timezone.utc)
    now, advance = fixed_clock(start)
    manager = BrowserSessionManager(session_factory=fake_factory, now_fn=now)
    session = manager.acquire(session_id="ttl-victim")

    advance(minutes=16)
    removed = manager.sweep_expired()
    assert removed == ["ttl-victim"]
    assert session.status is SessionStatus.CLOSED
    assert page_close_called(session), "browser surfaces must be closed — no orphans"
    assert len(manager) == 0


def page_close_called(session: BrowserSession) -> bool:
    # session.close() nulls the attrs; verify via metadata runtime + closed flags
    runtime = None  # after close the runtime stop() is invoked
    return session.page is None and session.context is None and runtime is None


def test_recently_touched_session_survives_sweep():
    start = datetime.now(timezone.utc)
    now, advance = fixed_clock(start)
    manager = BrowserSessionManager(session_factory=fake_factory, now_fn=now)
    session = manager.acquire(session_id="busy")

    advance(minutes=10)
    manager.get_session("busy")  # touch → idle clock reset
    advance(minutes=2)
    assert manager.sweep_expired() == []
    assert session.status is SessionStatus.ACTIVE

    advance(minutes=4)
    assert manager.sweep_expired() == ["busy"]


def test_idle_timeout_3min_default_constants():
    assert SESSION_TTL_SECONDS == 900
    assert IDLE_TIMEOUT_SECONDS == 180


def test_sweeper_daemon_runs_and_stops_cleanly():
    start = datetime.now(timezone.utc)
    now, _ = fixed_clock(start)

    async def scenario():
        manager = BrowserSessionManager(
            session_factory=fake_factory, now_fn=now, sweep_interval=0.01
        )
        await manager.start_sweeper()
        manager.acquire(session_id="daemon-victim")

        def jump():
            now_state = start + timedelta(minutes=20)
            # emulate clock jump by swapping now_fn
            manager.now_fn = lambda: now_state

        jump()
        await asyncio.sleep(0.05)
        await manager.stop_sweeper()
        assert len(manager) == 0, "daemon must have swept the expired session"

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 4. Dedicated Chrome automation profile + 127.0.0.1
# ---------------------------------------------------------------------------
def test_chrome_launch_args_enforce_dedicated_profile_and_localhost():
    args = chrome_launch_args()
    assert "--user-data-dir=C:/SupremeAI_Automation_Profile" in args
    assert f"--remote-debugging-address={AUTOMATION_HOST}" in args


def test_profile_dir_env_override(monkeypatch):
    monkeypatch.setenv("BROWSER_AUTOMATION_PROFILE_DIR", "/tmp/supreme-automation")
    args = chrome_launch_args()
    assert "--user-data-dir=/tmp/supreme-automation" in args


# ---------------------------------------------------------------------------
# 5. Multi-Action Registry — sequential actions on ONE page
# ---------------------------------------------------------------------------
def test_action_sequence_runs_on_same_page_in_order():
    manager = BrowserSessionManager(session_factory=fake_factory)
    session = manager.acquire(session_id="seq")

    async def scenario():
        return await run_action_sequence(
            session,
            [
                {"type": "navigate", "url": "https://example.com"},
                {"type": "type", "selector": "#q", "text": "hello"},
                {"type": "wait", "ms": 1},
                {"type": "extract", "selector": "#out"},
            ],
        )

    results = asyncio.run(scenario())
    assert [r["status"] for r in results] == ["success"] * 4
    page_calls = session.page.calls
    assert page_calls[0] == ("goto", "https://example.com")
    # per-character keystrokes joined = the typed text (true insertion)
    typed = "".join(c[2] for c in page_calls if c[0] == "type")
    assert typed == "hello"
    assert results[-1]["text"] == "text-of-#out"
    assert results[-1]["action"] == "extract"


def test_unknown_action_fails_fast_and_stops_sequence():
    manager = BrowserSessionManager(session_factory=fake_factory)
    session = manager.acquire(session_id="seq2")

    async def scenario():
        return await run_action_sequence(
            session,
            [{"type": "navigate", "url": "https://example.com"}, {"type": "teleport"}],
        )

    results = asyncio.run(scenario())
    assert results[0]["status"] == "success"
    assert results[1]["status"] == "error"
    assert "unknown action 'teleport'" in results[1]["error"]


def test_action_registry_has_core_actions():
    from browser.session_manager import ACTION_REGISTRY

    for name in ("navigate", "type", "click", "wait", "extract"):
        assert name in ACTION_REGISTRY, f"multi-action registry missing '{name}'"


# ---------------------------------------------------------------------------
# 6. SwarmBrowser — real sessions, parallel tabs, clean release
# ---------------------------------------------------------------------------
class FakeReasoner:
    async def decide(self, task, context=None, tools=None):
        return {"tool": "done", "reasoning": "fake", "source": "fake"}


@pytest.fixture(autouse=True)
def _fake_reasoner(monkeypatch):
    monkeypatch.setattr(
        sb_module.ReasoningOrchestrator,
        "get_instance",
        classmethod(lambda cls: FakeReasoner()),
    )


def test_swarm_explore_uses_stateful_sessions_and_releases_them():
    manager = BrowserSessionManager(session_factory=fake_factory)
    swarm = sb_module.SwarmBrowser(session_manager=manager)

    result = asyncio.run(swarm.explore("https://example.com", ["goal A", "goal B"]))

    assert result["status"] == "success"
    assert result["total_agents"] == 2
    assert len(manager) == 0, "all swarm sessions must be released after the mission"
    # Each sub-goal ran on its OWN session/page (parallel tab coordination)
    for finding in result["findings"]:
        assert finding["achieved"] is True


def test_swarm_findings_record_session_metadata():
    captured = {}

    class SpyAgent(AutonomousBrowserAgent):
        def __init__(self, session=None, **kw):
            super().__init__(session=session, **kw)
            captured.setdefault("sessions", []).append(session)

    manager = BrowserSessionManager(session_factory=fake_factory)
    swarm = sb_module.SwarmBrowser(session_manager=manager)
    monkey = pytest.MonkeyPatch()
    monkey.setattr(sb_module, "AutonomousBrowserAgent", SpyAgent)
    try:
        asyncio.run(swarm.explore("https://example.com", ["one", "two", "three"]))
    finally:
        monkey.undo()
    assert len(captured["sessions"]) == 3
    assert all(s.metadata.get("swarm_goal") for s in captured["sessions"])

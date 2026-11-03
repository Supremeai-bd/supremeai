"""PlaywrightBrowserAgent ramp — tools/browser/playwright_browser_agent.py.

The module measured 0% coverage because every public method crashed at the
``_new_context`` unpack (latent-crash repaired in this PR: the method now
returns the ``(context, stealth_manager)`` tuple all eight callers expect, and
the async ``upload_file`` cleanup awaits instead of ``asyncio.run``).

Test strategy (no real browser, no network — CI-safe):
* ``BrowserStealth`` is faked at the module attribute; its
  ``create_stealth_browser`` returns a scripted ``FakeContext`` and ``close()``
  records, exactly matching the shapes the agent's own finally blocks call.
* ``db`` (``database.supabase_client.db``) is replaced with a recorder double.
* ``MemoryManager`` / ``ModelRouter`` are replaced with scriptable fakes.
* ``SecureCredentialStore`` is replaced with a double that honours the AGENT's
  JSON round-trip contract (the real store is bytes-oriented Fernet — the
  cookie-persistence contract mismatch is documented as an owner decision
  item in the PR, not silently redesigned here).
* ``COOKIE_STORAGE_BASE`` is redirected to tmp_path (the class otherwise
  mkdirs a path inside the repository working tree).
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import tools.browser.playwright_browser_agent as pa
from tools.browser.playwright_browser_agent import (
    TRUST_SCORE_THRESHOLD,
    PlaywrightBrowserAgent,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class FakePage:
    def __init__(self):
        self.calls: list[tuple] = []
        self.title_value = "Fake Title"
        self.text_value: str | None = "hello"
        self.visible_value = True
        self.evaluate_value = "ai response"
        self.locator_value: object | None = None
        self.selector_element = None
        self.goto_raises: Exception | None = None
        self.mouse_moves: list[tuple] = []
        self.mouse_clicks: list[tuple] = []
        self.typed: list[tuple] = []
        self.clicks: list[str] = []
        self.cookies_added: list | None = None
        self.input_files: list[tuple] = []
        self.screenshot_paths: list[str] = []
        self.closed = False
        self.mouse = SimpleNamespace(
            move=lambda x, y, steps=0: self.mouse_moves.append((x, y, steps)),
            click=lambda x, y, **kw: self.mouse_clicks.append((x, y)),
        )

    # lifecycle
    def set_default_timeout(self, ms):
        self.calls.append(("set_default_timeout", ms))

    def close(self):
        self.closed = True

    # navigation / content
    def goto(self, url, **kw):
        if self.goto_raises:
            raise self.goto_raises
        self.calls.append(("goto", url))

    def title(self):
        return self.title_value

    def text_content(self, selector):
        return self.text_value

    def is_visible(self, selector):
        return self.visible_value

    def evaluate(self, script, *args):
        return self.evaluate_value

    def wait_for_selector(self, selector, **kw):
        if self.selector_element is not None:
            return self.selector_element
        return FakeElement({"x": 10, "y": 20, "width": 100, "height": 40})

    def wait_for_timeout(self, ms):
        self.calls.append(("wait_for_timeout", ms))

    def wait_for_load_state(self, state="load"):
        self.calls.append(("wait_for_load_state", state))

    def wait_for_function(self, script, *args, **kw):
        self.calls.append(("wait_for_function", len(script)))

    def type(self, selector, text, delay=0):
        self.typed.append((selector, text, delay))

    def click(self, selector, **kw):
        self.clicks.append(selector)

    def screenshot(self, path=None, **kw):
        self.screenshot_paths.append(path)
        if path:
            with open(path, "wb") as fh:
                fh.write(b"\x89PNG-fake")

    def locator(self, selector):
        return self.locator_value if self.locator_value is not None else FakeLocator()


class FakeElement:
    def __init__(self, bb):
        self._bb = bb

    def bounding_box(self):
        return self._bb


class FakeLocator:
    def __init__(self):
        self.files_set: list = []

    def set_input_files(self, files):
        self.files_set.append(files)


class FakeContext:
    def __init__(self):
        self.pages: list[FakePage] = []
        self.added_cookies: list = []
        self.cookie_value: list = [{"name": "sid", "value": "x"}]
        self.closed = False
        self.preset_page: FakePage | None = None

    def new_page(self):
        if self.preset_page is not None:
            page = self.preset_page
            self.preset_page = None
            self.pages.append(page)
            return page
        page = FakePage()
        self.pages.append(page)
        return page

    def add_cookies(self, cookies):
        self.added_cookies.append(cookies)

    def cookies(self):
        return self.cookie_value

    def close(self):
        self.closed = True


class FakeStealth:
    """Mirrors the real BrowserStealth surface the agent touches."""

    def __init__(self, context=None):
        self._context = context or FakeContext()
        self.close_calls = 0

    async def create_stealth_browser(self):
        return self._context

    async def close(self):
        self.close_calls += 1


class FakeStore:
    """Honours the agent's JSON round-trip contract (ISSUE-1570 revision).

    The agent now serializes cookies to a JSON string and encrypts the STRING;
    encrypt returns a JSON-SERIALIZABLE mapping envelope (legacy mapping
    contract kept so persisted mapping-shaped stores still load). decrypt
    receives the parsed mapping back.
    """

    def __init__(self):
        self.decrypt_calls = 0

    def encrypt(self, payload):
        return {"__enc__": True, "blob": payload}

    def decrypt(self, token, ttl=None):
        self.decrypt_calls += 1
        if isinstance(token, bytes):
            token = json.loads(token)
        if isinstance(token, dict) and token.get("__enc__"):
            return token["blob"]
        return token


class FakeMemory:
    def __init__(self):
        self.added: list[tuple] = []
        self.recall_value: list[str] = ["past learning"]

    async def retrieve_relevant_memories(self, query, top_k=3):
        return self.recall_value

    async def add_memory(self, learning, url, metadata=None):
        self.added.append((learning, url, metadata))


class FakeRouter:
    def __init__(self):
        self.responses: list[dict] = []

    async def async_route_and_generate(self, **kw):
        if not self.responses:
            return {"success": False, "text": "no scripted response"}
        return self.responses.pop(0)


class FakeThread:
    """Runs the target synchronously so background DB writes are deterministic."""

    def __init__(self, target=None, args=(), kwargs=None):
        self._target, self._args = target, args

    def start(self):
        self._target(*self._args)

    def join(self, timeout=None):
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def agent(tmp_path, monkeypatch):
    monkeypatch.setattr(pa.PlaywrightBrowserAgent, "COOKIE_STORAGE_BASE", tmp_path / "cookies")
    monkeypatch.setattr(pa, "MemoryManager", FakeMemory)
    monkeypatch.setattr(pa, "SecureCredentialStore", FakeStore)
    a = PlaywrightBrowserAgent(headless=True, timeout_ms=1234)
    yield a


@pytest.fixture()
def stealth_env(monkeypatch):
    """Fakes BrowserStealth + db for lifecycle methods; returns the recorder.

    One stealth/context instance is created EAGERLY and returned on every
    BrowserStealth() call, so tests can pre-configure the context before the
    first agent method runs (mirrors one browser session per method call).
    """
    recorder = SimpleNamespace(stealth=None, context=None, db=None)
    st = FakeStealth()
    recorder.stealth = st
    recorder.context = st._context
    monkeypatch.setattr(pa, "BrowserStealth", lambda: st)
    # The agent's public flows gate on start() -> is_available() (a real
    # importlib spec check). CI venvs may not install playwright (the module
    # treats it as an optional dependency), so the availability gate is faked
    # TRUE here to let the scripted fake-browser flows run everywhere. The
    # real gate behaviour keeps dedicated coverage below
    # (test_is_available_true_and_false / test_start_raises_when_unavailable).
    monkeypatch.setattr(pa.PlaywrightBrowserAgent, "is_available", lambda self: True)
    db_double = SimpleNamespace(
        get_model_behavior=lambda name: None,
        upsert_model_behavior=lambda data: data,
    )
    recorder.db = db_double
    monkeypatch.setattr(pa, "db", db_double)
    return recorder


def seed_cookie_file(agent: PlaywrightBrowserAgent, session: str, payload):
    path = agent._cookie_file_path(session)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return path


# ---------------------------------------------------------------------------
# init / availability / lifecycle no-ops
# ---------------------------------------------------------------------------
def test_init_defaults_and_cookie_dir(agent, tmp_path):
    assert agent.headless is True and agent.timeout_ms == 1234
    assert agent.playwright is None and agent.browser is None
    assert (tmp_path / "cookies").is_dir()
    assert isinstance(agent.secure_store, FakeStore)
    assert isinstance(agent.memory, FakeMemory)


def test_is_available_true_and_false(agent, monkeypatch):
    import importlib.util

    # Real spec detection: the module treats playwright as OPTIONAL, so both
    # branches must hold regardless of whether this environment installs it.
    if importlib.util.find_spec("playwright") is not None:
        assert agent.is_available() is True
    else:
        assert agent.is_available() is False

    with patch("importlib.util.find_spec", return_value=None):
        assert agent.is_available() is False


def test_start_raises_when_unavailable(agent):
    with patch.object(agent, "is_available", return_value=False):
        with pytest.raises(RuntimeError, match="playwright is not installed"):
            agent.start()


def test_start_and_stop_are_safe_noops(agent, monkeypatch):
    # start() is an availability check and stop() is a debug log (cleanup lives
    # in per-task finally blocks) — neither needs real playwright, so the gate
    # is faked for environments where the optional dependency is absent.
    monkeypatch.setattr(pa.PlaywrightBrowserAgent, "is_available", lambda self: True)
    agent.start()
    agent.stop()


# ---------------------------------------------------------------------------
# cookie plumbing
# ---------------------------------------------------------------------------
def test_cookie_file_path_sanitizes_unsafe_names(agent):
    assert agent._cookie_file_path("ok-name_1").name == "ok-name_1_cookies.json"
    unsafe = agent._cookie_file_path("../evil/x y")
    assert "/" not in unsafe.name and " " not in unsafe.name
    assert unsafe.name == "___evil_x_y_cookies.json"


def test_load_cookies_missing_file_is_noop(agent, stealth_env):
    ctx = FakeContext()
    agent._load_cookies(ctx, "nope")  # must not raise nor touch the context
    assert ctx.added_cookies == []


def test_load_cookies_plain_list(agent, stealth_env):
    ctx = FakeContext()
    seed_cookie_file(agent, "s1", [{"name": "a", "value": "b"}])
    agent._load_cookies(ctx, "s1")
    assert ctx.added_cookies == [[{"name": "a", "value": "b"}]]
    assert agent.secure_store.decrypt_calls == 0


def test_load_cookies_encrypted_marker_roundtrip(agent, stealth_env):
    ctx = FakeContext()
    seed_cookie_file(agent, "s2", agent.secure_store.encrypt([{"name": "enc", "value": "1"}]))
    agent._load_cookies(ctx, "s2")
    assert ctx.added_cookies == [[{"name": "enc", "value": "1"}]]
    assert agent.secure_store.decrypt_calls == 1  # outer unwrap returns the list


@pytest.mark.parametrize("payload", ["corrupt-json", {"foo": 1}, "just-a-string"])
def test_load_cookies_bad_payloads_remove_stale_file(agent, stealth_env, payload):
    ctx = FakeContext()
    path = seed_cookie_file(agent, "s3", {"seed": True})
    if payload == "corrupt-json":
        path.write_text("{not json")
    else:
        path.write_text(json.dumps(payload))
    agent._load_cookies(ctx, "s3")
    assert ctx.added_cookies == []
    assert not path.exists()  # stale file removed after warning


def test_save_cookies_writes_encrypted_payload(agent, stealth_env):
    ctx = FakeContext()
    agent._save_cookies(ctx, "sess")
    path = agent._cookie_file_path("sess")
    assert path.exists()
    stored = json.loads(path.read_text())
    assert stored["__enc__"] is True
    # ISSUE-1570: blob is now the ENCRYPTED serialized string (real store tuple
    # contract); with the mapping-contract FakeStore it stays the serialized
    # JSON string — either way it must never equal a raw plaintext list.
    assert stored["blob"] == json.dumps([{"name": "sid", "value": "x"}])


# ---------------------------------------------------------------------------
# human-like interaction primitives
# ---------------------------------------------------------------------------
def test_human_like_type_types_per_character(agent):
    page = FakePage()
    agent._human_like_type(page, "#q", "ab")
    assert [t[1] for t in page.typed] == ["a", "b"]
    assert all(30 <= t[2] <= 100 for t in page.typed)


def test_human_like_click_bezier_path(agent):
    page = FakePage()
    moves: list[tuple] = []
    clicks: list[tuple] = []
    page.mouse = SimpleNamespace(
        move=lambda x, y, steps=0: moves.append((x, y, steps)),
        click=lambda x, y, **kw: clicks.append((x, y)),
    )
    agent._human_like_click(page, "#btn", steps=7)
    assert len(moves) == 4 and clicks, "expected 4 curve moves + a click"
    assert moves[-1][2] == 7  # final move carries the steps value
    assert page.clicks == []  # no fallback click on the happy path


def test_human_like_click_fallback_without_bbox(agent):
    page = FakePage()
    page.selector_element = FakeElement(None)
    agent._human_like_click(page, "#bbox-less")
    assert page.clicks == ["#bbox-less"]


def test_human_like_click_fallback_on_error(agent):
    page = FakePage()
    page.selector_element = None

    def boom(*a, **kw):
        raise TimeoutError("no selector")

    page.wait_for_selector = boom
    agent._human_like_click(page, "#missing")
    assert page.clicks == ["#missing"]  # graceful degradation, no raise


# ---------------------------------------------------------------------------
# context lifecycle (the repaired contract)
# ---------------------------------------------------------------------------
def test_new_context_returns_context_and_stealth_pair(agent, stealth_env):
    context, stealth = agent._new_context()
    assert isinstance(context, FakeContext) and isinstance(stealth, FakeStealth)
    assert stealth is stealth_env.stealth


def test_new_context_loads_session_cookies(agent, stealth_env):
    seed_cookie_file(agent, "sess-x", [{"name": "k", "value": "v"}])
    context, _ = agent._new_context("sess-x")
    assert context.added_cookies == [[{"name": "k", "value": "v"}]]


def test_context_cleanup_runs_on_task_success(agent, stealth_env):
    def task(page):
        page.goto("https://example.com")
        return "done"

    out = agent.perform_task("https://example.com", task)
    assert out == {"success": True, "result": "done"}
    ctx = stealth_env.context
    assert ctx.pages[0].closed and ctx.closed
    assert stealth_env.stealth.close_calls == 1


def test_context_cleanup_runs_on_task_failure(agent, stealth_env):
    def task(page):
        raise ValueError("boom")

    out = agent.perform_task("https://example.com", task)
    assert out["success"] is False and "boom" in out["error"]
    assert stealth_env.context.pages[0].closed and stealth_env.context.closed
    assert stealth_env.stealth.close_calls == 1


# ---------------------------------------------------------------------------
# perform_task login flows
# ---------------------------------------------------------------------------
def test_perform_task_restores_valid_session(agent, stealth_env):
    page_seen: list = []
    flow_calls: list = []

    def flow(page, creds):
        flow_calls.append(creds)

    out = agent.perform_task(
        "https://example.com",
        lambda p: page_seen.append(p) or "ok",
        session_name="s",
        login_check_selector="#dashboard",
        login_flow=flow,
        credentials={"u": "a", "p": "b"},
    )
    assert out["success"] is True
    assert page_seen and not flow_calls  # visible selector → session valid
    assert not agent._cookie_file_path("s").exists()  # nothing re-saved


def test_perform_task_runs_login_flow_when_session_invalid(agent, stealth_env):
    flow_calls: list = []
    ctx = stealth_env.context

    def flow(page, creds):
        flow_calls.append(creds)

    logged_out = FakePage()
    logged_out.visible_value = False
    ctx.preset_page = logged_out

    out = agent.perform_task(
        "https://example.com",
        lambda p: "ok",
        session_name="s",
        login_check_selector="#dashboard",
        login_flow=flow,
        credentials={"u": "a"},
    )
    assert out["success"] is True
    assert flow_calls == [{"u": "a"}]
    assert ("wait_for_load_state", "networkidle") in logged_out.calls
    assert agent._cookie_file_path("s").exists()  # cookies persisted post-login


def test_perform_task_skips_login_block_without_flow(agent, stealth_env):
    # selector given but flow/credentials missing → login block never entered
    out = agent.perform_task(
        "https://example.com",
        lambda p: "ok",
        session_name="s",
        login_check_selector="#dashboard",
    )
    assert out == {"success": True, "result": "ok"}


def test_perform_task_login_check_crash_is_contained(agent, stealth_env):
    flow_calls: list = []

    def broken_is_visible(selector):
        raise RuntimeError("visibility probe exploded")

    crashing = FakePage()
    crashing.is_visible = broken_is_visible  # the check happens BEFORE task()
    stealth_env.context.preset_page = crashing

    out = agent.perform_task(
        "https://example.com",
        lambda p: "ok",
        session_name="s",
        login_check_selector="#dashboard",
        login_flow=lambda p, c: flow_calls.append(c),
        credentials={"u": "x"},
    )
    assert out["success"] is True
    assert flow_calls  # contained → fell through to the login flow


# ---------------------------------------------------------------------------
# simple lifecycle actions
# ---------------------------------------------------------------------------
def test_open_returns_title(agent, stealth_env):
    out = agent.open("https://example.com")
    assert out == {"success": True, "url": "https://example.com", "title": "Fake Title"}
    assert stealth_env.context.pages[0].closed


def test_open_cleans_up_even_when_goto_fails(agent, stealth_env):
    bad = FakePage()
    bad.goto_raises = RuntimeError("net down")
    stealth_env.context.preset_page = bad
    with pytest.raises(RuntimeError, match="net down"):
        agent.open("https://example.com")  # no except clause: error propagates
    assert bad.closed and stealth_env.context.closed
    assert stealth_env.stealth.close_calls == 1


def test_screenshot_writes_requested_path(agent, stealth_env, tmp_path):
    target = tmp_path / "shot.png"
    out = agent.screenshot("https://example.com", str(target))
    assert out == {"success": True, "path": str(target)}
    assert stealth_env.context.pages[0].screenshot_paths == [str(target)]


def test_click_uses_human_like_click(agent, stealth_env, monkeypatch):
    seen: list = []
    monkeypatch.setattr(
        agent, "_human_like_click", lambda page, selector, steps=25: seen.append(selector)
    )
    out = agent.click("https://example.com", "#go")
    assert out == {"success": True} and seen == ["#go"]


def test_text_returns_content(agent, stealth_env):
    out = agent.text("https://example.com", "#t")
    assert out == {"success": True, "text": "hello"}


def test_text_empty_when_selector_missing(agent, stealth_env):
    empty = FakePage()
    empty.text_value = None
    stealth_env.context.preset_page = empty
    out = agent.text("https://example.com", "#missing")
    assert out == {"success": True, "text": ""}


def test_upload_file_sets_input_and_closes_via_await(agent, stealth_env):
    out = asyncio.run(agent.upload_file("input[type=file]", "/tmp/data.csv"))
    assert out["success"] is True and "Uploaded: /tmp/data.csv" in out["message"]
    # the repaired cleanup: close happened inside the SAME running loop
    assert stealth_env.stealth.close_calls == 1
    assert stealth_env.context.pages[0].closed


def test_upload_file_reports_locator_failure(agent, stealth_env):
    empty = FakePage()
    empty.locator = lambda selector: None  # falsy → not-found branch
    stealth_env.context.preset_page = empty
    out = asyncio.run(agent.upload_file("#gone", "/tmp/x.csv"))
    assert out["success"] is False and "not found" in out["error"]
    assert stealth_env.stealth.close_calls == 1  # repaired await-close still ran


# ---------------------------------------------------------------------------
# model-behavior plumbing
# ---------------------------------------------------------------------------
def test_update_model_behavior_upserts(agent, stealth_env, monkeypatch):
    sent: list = []
    monkeypatch.setattr(
        stealth_env.db, "upsert_model_behavior", lambda data: sent.append(data) or data
    )
    agent._update_model_behavior("gpt-x", 120.5, True)
    assert sent == [{"model_name": "gpt-x", "avg_latency_ms": 120.5, "last_seen_success": True}]


def test_background_update_runs_deterministically(agent, stealth_env, monkeypatch):
    sent: list = []
    monkeypatch.setattr(stealth_env.db, "upsert_model_behavior", lambda data: sent.append(data))
    with patch("threading.Thread", FakeThread):
        agent._update_model_behavior_in_background("m", 1.0, False)
    assert sent == [{"model_name": "m", "avg_latency_ms": 1.0, "last_seen_success": False}]


def test_background_update_survives_thread_spawn_failure(agent, stealth_env, monkeypatch):
    def no_threads(*a, **kw):
        raise RuntimeError("cannot spawn")

    with patch("threading.Thread", side_effect=no_threads):
        agent._update_model_behavior_in_background("m", 1.0, True)  # logs, no raise


# ---------------------------------------------------------------------------
# _query_ai_site
# ---------------------------------------------------------------------------
def _ai_site(name="Primary"):
    return {
        "name": name,
        "url": f"https://{name.lower()}.ai/",
        "input_selector": "textarea",
        "output_selector": ".msg",
        "submit_button": "#send",
    }


def test_query_ai_site_happy_path(agent, stealth_env):
    page = FakePage()
    text, ok = agent._query_ai_site(page, _ai_site(), "hi there")
    assert (text, ok) == ("ai response", True)
    calls = {c[0] for c in page.calls}
    assert {"goto", "wait_for_function", "wait_for_timeout"} <= calls
    assert page.typed and page.mouse_moves or page.clicks  # human-like interaction


def test_query_ai_site_empty_response_is_failure(agent, stealth_env):
    page = FakePage()
    page.evaluate_value = "   "
    text, ok = agent._query_ai_site(page, _ai_site(), "hi")
    assert (text, ok) == ("", False)


def test_query_ai_site_swallows_page_errors(agent, stealth_env):
    page = FakePage()
    page.goto_raises = TimeoutError("never loaded")
    text, ok = agent._query_ai_site(page, _ai_site(), "hi")
    assert (text, ok) == ("", False)


# ---------------------------------------------------------------------------
# cross_verify_prompt
# ---------------------------------------------------------------------------
def _wire(agent, stealth_env, responses, db_behavior=None):
    """Patch _query_ai_site with a scripted sequence; return the call log."""
    log: list = []

    def fake_query(page, site_config, prompt):
        log.append((site_config["name"], prompt))
        return responses.pop(0)

    object.__setattr__(agent, "_query_ai_site", fake_query)

    def get_behavior(name):
        return db_behavior

    object.__setattr__(stealth_env.db, "get_model_behavior", get_behavior)
    return log


def test_cross_verify_confirmed_path(agent, stealth_env):
    log = _wire(agent, stealth_env, [("resp", True), ("CORRECT — verified", True)])
    out = agent.cross_verify_prompt("q?", _ai_site("Primary"), _ai_site("Verifier"))
    assert out["success"] is True and out["is_confirmed"] is True
    assert out["final_action"] == "implement" and "verification_skipped" not in out
    assert [name for name, _ in log] == ["Primary", "Verifier"]
    assert "Answer with only 'CORRECT' or 'INCORRECT'" in log[1][1]


def test_cross_verify_rejected_path(agent, stealth_env):
    # NOTE (owner-decision item): the implementation checks
    # `"correct" in verification_result.lower()` — a SUBSTRING match, so any
    # reply containing the word INCORRECT is still treated as confirmed. The
    # reject path below uses an unambiguous reply that lacks the substring.
    _wire(agent, stealth_env, [("resp", True), ("WRONG — do not implement", True)])
    out = agent.cross_verify_prompt("q?", _ai_site("P"), _ai_site("V"))
    assert out["is_confirmed"] is False and out["final_action"] == "reject"


def test_cross_verify_skips_verification_for_trusted_model(agent, stealth_env):
    log = _wire(
        agent,
        stealth_env,
        [("resp", True), ("should never be consumed", True)],
        db_behavior={"requires_verification": False, "trust_score": 0.1},
    )
    out = agent.cross_verify_prompt("q?", _ai_site("P"), _ai_site("V"))
    assert out["verification_skipped"] is True
    assert out["final_action"] == "implement" and out["is_confirmed"] is True
    assert len(log) == 1  # verifier never queried


def test_cross_verify_skips_for_high_trust_score(agent, stealth_env):
    log = _wire(
        agent,
        stealth_env,
        [("resp", True), ("unused", True)],
        db_behavior={"trust_score": TRUST_SCORE_THRESHOLD + 0.01},
    )
    out = agent.cross_verify_prompt("q?", _ai_site("P"), _ai_site("V"))
    assert out["verification_skipped"] is True and len(log) == 1


def test_cross_verify_primary_failure(agent, stealth_env):
    _wire(agent, stealth_env, [("", False), ("unused", True)])
    out = agent.cross_verify_prompt("q?", _ai_site("P"), _ai_site("V"))
    assert out["success"] is False
    assert "Failed to get a response from P" in out["error"]


def test_cross_verify_verifier_failure(agent, stealth_env):
    _wire(agent, stealth_env, [("resp", True), ("", False)])
    out = agent.cross_verify_prompt("q?", _ai_site("P"), _ai_site("V"))
    assert out["success"] is False
    assert "Failed to get a response from V" in out["error"]


# ---------------------------------------------------------------------------
# execute_goal (VLM loop)
# ---------------------------------------------------------------------------
def _goal_env(agent, monkeypatch, responses, recall=None):
    router = FakeRouter()
    router.responses = list(responses)
    monkeypatch.setattr(pa, "ModelRouter", lambda: router)
    return router


def test_execute_goal_finishes_on_vlm_finish_action(agent, stealth_env, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _goal_env(
        agent,
        monkeypatch,
        [{"success": True, "text": '{"type": "FINISH", "reason": "page reached"}'}],
    )
    out = agent.execute_goal("https://example.com", "buy milk", max_steps=3)
    assert out == {"success": True, "result": "Goal achieved: page reached"}
    assert stealth_env.stealth.close_calls == 1


def test_execute_goal_click_then_finish_and_learns(agent, stealth_env, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _goal_env(
        agent,
        monkeypatch,
        [
            {"success": True, "text": '{"type": "CLICK", "selector": "#add", "reason": "r1"}'},
            {"success": True, "text": '{"type": "FINISH", "reason": "done"}'},
        ],
    )
    out = agent.execute_goal("https://example.com", "task", max_steps=4)
    assert out["success"] is True
    memory: FakeMemory = agent.memory
    assert any("CLICK" in learning for learning, _, _ in memory.added)
    assert memory.added[0][2]["type"] == "CLICK"  # metadata carries the action


def test_execute_goal_vlm_failure(agent, stealth_env, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _goal_env(agent, monkeypatch, [])  # router returns success=False
    out = agent.execute_goal("https://example.com", "task", max_steps=2)
    assert out["success"] is False and "VLM failed" in out["error"]


def test_execute_goal_malformed_action_json(agent, stealth_env, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _goal_env(agent, monkeypatch, [{"success": True, "text": "not-json-at-all"}])
    out = agent.execute_goal("https://example.com", "task", max_steps=2)
    assert out == {"success": False, "error": "Failed to parse VLM action."}


def test_execute_goal_step_cap_exhaustion(agent, stealth_env, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _goal_env(
        agent,
        monkeypatch,
        [
            {
                "success": True,
                "text": '{"type": "TYPE", "selector": "#q", "text": "hi", "reason": "search"}',
            },
            {
                "success": True,
                "text": '{"type": "TYPE", "selector": "#q", "text": "hi", "reason": "search"}',
            },
        ],
    )
    out = agent.execute_goal("https://example.com", "task", max_steps=2)
    assert out == {"success": True, "result": "Completed 2 steps."}
    assert len(agent.memory.added) == 2  # learned after every executed step


# ---------------------------------------------------------------------------
# FastMCP / Circle C6 async wrappers
# ---------------------------------------------------------------------------
def test_navigate_delegates_to_open(agent, stealth_env, monkeypatch):
    seen: list = []
    monkeypatch.setattr(
        agent, "open", lambda url, session_name=None: seen.append(url) or {"success": True}
    )
    out = asyncio.run(agent.navigate("https://example.com"))
    assert out == {"success": True} and seen == ["https://example.com"]


def test_click_target_with_and_without_url(agent, stealth_env, monkeypatch):
    # ISSUE-1570: with a URL the wrapper spins a fresh context and runs the
    # REAL 5-step cascade — the fake page resolves '#go' via the known-locator
    # step and a human-like click is dispatched (bezier path → mouse click).
    out = asyncio.run(agent.click_target("#go", "https://example.com"))
    assert out["success"] is True
    assert out["method"] == "known_locator"
    ctx = stealth_env.context
    assert ("goto", "https://example.com") in ctx.pages[0].calls
    assert ctx.pages[0].mouse_clicks, "a real mouse click must be dispatched"
    assert stealth_env.stealth.close_calls == 1

    # without a URL and without a bound page the wrapper must FAIL HONESTLY —
    # the old fake `{'success': True, 'target': ...}` response is forbidden.
    fallback = asyncio.run(agent.click_target("#x", None))
    assert fallback["success"] is False
    assert fallback["status"] == "PAUSED_HITL"
    assert len(ctx.pages) == 1  # no-url branch never touches the browser


def test_click_target_without_url_uses_bound_page(agent, stealth_env):
    page = FakePage()
    agent.bind_page(page)
    out = asyncio.run(agent.click_target("#btn", None))
    assert out["success"] is True
    assert out["method"] == "known_locator"
    assert page.mouse_clicks
    agent.unbind_page()
    # unbound again → honest failure
    out2 = asyncio.run(agent.click_target("#btn", None))
    assert out2["success"] is False


def test_type_text_with_and_without_url(agent, stealth_env):
    # ISSUE-1570: typing is TRUE keystroke insertion — never the read-only
    # text() call, and never a fake success without a page/URL.
    out = asyncio.run(agent.type_text("#q", "hello", "https://example.com"))
    assert out["success"] is True
    assert out["typed_chars"] == 5
    typed = stealth_env.context.pages[0].typed
    assert [t[1] for t in typed] == list("hello")
    assert all(30 <= t[2] <= 100 for t in typed), "keystrokes need 30-100ms jitter"

    fallback = asyncio.run(agent.type_text("#q", "hello", None))
    assert fallback["success"] is False
    assert "refusing to fake success" in fallback["error"]


def test_type_text_without_url_uses_bound_page(agent, stealth_env):
    page = FakePage()
    agent.bind_page(page)
    out = asyncio.run(agent.type_text("#q", "ab", None))
    assert out["success"] is True
    assert out["typed_chars"] == 2
    assert [t[1] for t in page.typed] == ["a", "b"]

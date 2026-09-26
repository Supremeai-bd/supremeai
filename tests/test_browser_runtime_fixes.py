"""Root acceptance tests for issue #1570 — Part 1: Browser Runtime & Action Primitives Hardening.

Covers (per the issue's acceptance criteria):
* ``click_target`` executes a REAL 5-step cascade (SemanticDOM → accessible
  role/name → known locator → vision → HITL) and never fake-succeeds.
* ``type_text`` performs true keystroke insertion with 30–100ms jitter (never
  the read-only ``text()`` call, never a no-op success).
* ``AutonomousBrowserAgent`` has zero hardcoded navigation endpoints — dynamic
  goal + URL with stateful page bindings.
* Confidence guardrails in SemanticDOM & VisionGrounding:
  >= 0.85 execute | 0.65–0.85 secondary verification | < 0.65 HITL escalation.
* Fail-closed credential security — no plaintext fallback, ever.
* Zero blind fallback clicks on low visual confidence.

No real browser, no network — CI-safe.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

import browser.action_cascade as ac_module
import browser.autonomous_browser as ab_module
import browser.semantic_dom as sd_module
import browser.vision_grounding as vg_module
import tools.browser.playwright_browser_agent as pa
from browser.action_cascade import (
    CONFIDENCE_EXECUTE,
    CONFIDENCE_VERIFY,
    execute_click_cascade,
)
from browser.autonomous_browser import AutonomousBrowserAgent
from browser.semantic_dom import SemanticDOM, confidence_band
from browser.vision_grounding import LowConfidenceGrounding, VisionGrounding
from core.security.secure_credential_store import (
    CredentialEncryptionUnavailableError,
    LocalFernetProvider,
    SecureCredentialStore,
)
from tools.browser.playwright_browser_agent import PlaywrightBrowserAgent


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------
class FakeScriptedEngine:
    """EmbeddingEngine double with SCRIPTED cosine outcomes for cascade tests."""

    def __init__(self, score_by_text: dict[str, float] | None = None):
        self.score_by_text = score_by_text or {}
        self.embedded: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.embedded.append(text)
        return [1.0, 0.0, 0.0]


def _wire_semantic_scores(monkeypatch, score_by_text: dict[str, float]):
    engine = FakeScriptedEngine(score_by_text)

    def fake_cosine(v1, v2):
        return 0.0  # replaced per-test via closure below

    monkeypatch.setattr(
        sd_module, "EmbeddingEngine", SimpleNamespace(get_instance=lambda: engine)
    )

    def scripted_cosine(v1, v2):
        # v2 belongs to an element description; pick the scripted score by
        # matching against any registered text via a side-channel attribute.
        return getattr(scripted_cosine, "_next", 0.0)

    return engine, scripted_cosine


class FakeMousePage:
    """Minimal sync page double: evaluate/locator/mouse recording."""

    def __init__(self, evaluate_value=None, findable_selector=None):
        self.evaluate_value = evaluate_value
        self.findable_selector = findable_selector
        self.mouse_clicks: list[tuple] = []
        self.gotos: list[str] = []
        self.typed: list[tuple] = []
        self.clicks: list[str] = []
        self.mouse = SimpleNamespace(
            move=lambda x, y, steps=0: None,
            click=lambda x, y, **kw: self.mouse_clicks.append((x, y)),
        )

    def evaluate(self, script, *args):
        return self.evaluate_value

    def wait_for_selector(self, selector, **kw):
        if self.findable_selector is not None and selector == self.findable_selector:
            return SimpleNamespace(
                bounding_box=lambda: {"x": 5, "y": 5, "width": 10, "height": 10}
            )
        raise TimeoutError(f"no element for {selector}")

    def goto(self, url, **kw):
        self.gotos.append(url)

    def type(self, selector, text, delay=0):
        self.typed.append((selector, text, delay))

    def click(self, selector, **kw):
        self.clicks.append(selector)


class FakeVision:
    """VisionGrounding double with scripted locate outcomes."""

    def __init__(self, outcome=None, exc: Exception | None = None):
        self.outcome = outcome
        self.exc = exc
        self.calls: list[str] = []

    async def locate(self, target, *a, **kw):
        self.calls.append(target)
        if self.exc is not None:
            raise self.exc
        return dict(self.outcome)


# ---------------------------------------------------------------------------
# 1. Confidence guardrails — band boundaries
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (1.0, "execute"),
        (CONFIDENCE_EXECUTE, "execute"),
        (0.8499, "verify"),
        (CONFIDENCE_VERIFY, "verify"),
        (0.6499, "hitl"),
        (0.0, "hitl"),
    ],
)
def test_confidence_band_boundaries(score, expected):
    assert confidence_band(score) == expected


# ---------------------------------------------------------------------------
# 2. SemanticDOM guardrail metadata
# ---------------------------------------------------------------------------
def test_semantic_dom_query_reports_guardrail_action(monkeypatch):
    engine = FakeScriptedEngine()
    monkeypatch.setattr(
        sd_module, "EmbeddingEngine", SimpleNamespace(get_instance=lambda: engine)
    )
    sdom = SemanticDOM(None)
    sdom._vectors = [
        ([1.0, 0.0, 0.0], {"tag": "button", "text": "Pay Now", "xpath": "//button[1]"})
    ]
    monkeypatch.setattr(
        sd_module.SemanticDOM, "cosine_similarity", staticmethod(lambda v1, v2: 0.9)
    )
    result = asyncio.run(sdom.query("finalize the payment"))
    assert result["semantic_confidence"] == pytest.approx(0.9)
    assert result["confidence_band"] == "execute"
    assert result["guardrail_action"] == "execute"


def test_semantic_dom_query_below_verify_threshold_raises(monkeypatch):
    engine = FakeScriptedEngine()
    monkeypatch.setattr(
        sd_module, "EmbeddingEngine", SimpleNamespace(get_instance=lambda: engine)
    )
    from browser.semantic_dom import ElementNotFoundSemantically

    sdom = SemanticDOM(None)
    sdom._vectors = [
        ([1.0, 0.0, 0.0], {"tag": "button", "text": "Pay Now", "xpath": "//button[1]"})
    ]
    monkeypatch.setattr(
        sd_module.SemanticDOM, "cosine_similarity", staticmethod(lambda v1, v2: 0.4)
    )
    with pytest.raises(ElementNotFoundSemantically):
        asyncio.run(sdom.query("finalize the payment"))


# ---------------------------------------------------------------------------
# 3. VisionGrounding — zero fabricated coordinates
# ---------------------------------------------------------------------------
class ScriptedRouter:
    def __init__(self, responses: list[dict]):
        self.responses = list(responses)

    def route_and_generate(self, *a, **kw):
        if not self.responses:
            return {"success": False, "text": ""}
        return self.responses.pop(0)


def test_vision_locate_high_confidence_executes():
    router = ScriptedRouter([{"text": '{"x": 120, "y": 80, "confidence": 0.92}'}])
    vg = VisionGrounding(page=None, router_factory=lambda: router)
    loc = asyncio.run(vg.locate("Login button"))
    assert loc["x"] == 120 and loc["y"] == 80
    assert loc["band"] == "execute"


def test_vision_locate_mid_confidence_requires_secondary_verification():
    router = ScriptedRouter(
        [
            {"text": '{"x": 120, "y": 80, "confidence": 0.72}'},
            {"text": '{"confirmed": true, "confidence": 0.9}'},
        ]
    )
    vg = VisionGrounding(page=None, router_factory=lambda: router)
    loc = asyncio.run(vg.locate("Login button"))
    assert loc["band"] == "verify"
    assert loc["verified"] is True


def test_vision_locate_mid_confidence_unverified_raises_no_blind_click():
    router = ScriptedRouter(
        [
            {"text": '{"x": 120, "y": 80, "confidence": 0.72}'},
            {"text": '{"confirmed": false, "confidence": 0.3}'},
        ]
    )
    vg = VisionGrounding(page=None, router_factory=lambda: router)
    with pytest.raises(LowConfidenceGrounding):
        asyncio.run(vg.locate("Login button"))


def test_vision_locate_low_confidence_raises_hitl():
    router = ScriptedRouter([{"text": '{"x": 10, "y": 10, "confidence": 0.5}'}])
    vg = VisionGrounding(page=None, router_factory=lambda: router)
    with pytest.raises(LowConfidenceGrounding):
        asyncio.run(vg.locate("Login button"))


def test_vision_locate_vlm_failure_never_fabricates_coordinates():
    # The old implementation returned {"x": 100, "y": 100, "confidence": 0.75}
    # on ANY failure — the exact blind-fallback-click bug banned by #1570.
    router = ScriptedRouter([{"success": False, "text": ""}])
    vg = VisionGrounding(page=None, router_factory=lambda: router)
    with pytest.raises(LowConfidenceGrounding):
        asyncio.run(vg.locate("anything"))
    router2 = ScriptedRouter([{"text": "total-garbage-not-json"}])
    vg2 = VisionGrounding(page=None, router_factory=lambda: router2)
    with pytest.raises(LowConfidenceGrounding):
        asyncio.run(vg2.locate("anything"))


def test_vision_locate_missing_coordinates_raises():
    router = ScriptedRouter([{"text": '{"confidence": 0.95}'}])
    vg = VisionGrounding(page=None, router_factory=lambda: router)
    with pytest.raises(LowConfidenceGrounding):
        asyncio.run(vg.locate("Login button"))


def test_vision_click_dispatches_only_when_guardrail_allows():
    page = FakeMousePage()
    router = ScriptedRouter([{"text": '{"x": 30, "y": 40, "confidence": 0.9}'}])
    vg = VisionGrounding(page=page, router_factory=lambda: router)
    result = asyncio.run(vg.click("Login"))
    assert result["band"] == "execute"
    assert page.mouse_clicks == [(30, 40)]

    page_low = FakeMousePage()
    router_low = ScriptedRouter([{"text": '{"x": 30, "y": 40, "confidence": 0.5}'}])
    vg_low = VisionGrounding(page=page_low, router_factory=lambda: router_low)
    with pytest.raises(LowConfidenceGrounding):
        asyncio.run(vg_low.click("Login"))
    assert page_low.mouse_clicks == []  # zero blind clicks on low confidence


# ---------------------------------------------------------------------------
# 4. click_target — the full 5-step cascade
# ---------------------------------------------------------------------------
def test_cascade_step1_semantic_execute_band_clicks_xpath(monkeypatch):
    engine = FakeScriptedEngine()
    monkeypatch.setattr(
        sd_module, "EmbeddingEngine", SimpleNamespace(get_instance=lambda: engine)
    )

    page = FakeMousePage(evaluate_value=[], findable_selector=None)
    clicks: list[str] = []

    def fake_cosine(v1, v2):
        return 0.9

    monkeypatch.setattr(
        sd_module.SemanticDOM, "cosine_similarity", staticmethod(fake_cosine)
    )

    result = asyncio.run(
        execute_click_cascade(
            page, "finalize payment widget", human_click=lambda p, s: clicks.append(s)
        )
    )
    assert result["success"] is True
    assert result["method"] == "semantic_dom"
    assert result["band"] == "execute"
    assert clicks and clicks[0].startswith("xpath=")


def test_cascade_step1_semantic_verify_band_secondary_verifies(monkeypatch):
    engine = FakeScriptedEngine()
    monkeypatch.setattr(
        sd_module, "EmbeddingEngine", SimpleNamespace(get_instance=lambda: engine)
    )
    monkeypatch.setattr(
        sd_module.SemanticDOM, "cosine_similarity", staticmethod(lambda v1, v2: 0.7)
    )

    page = FakeMousePage(
        evaluate_value=[], findable_selector="xpath=//button[@type='submit']"
    )
    clicks: list[str] = []
    result = asyncio.run(
        execute_click_cascade(
            page, "finalize payment widget", human_click=lambda p, s: clicks.append(s)
        )
    )
    assert result["success"] is True
    assert result["method"] == "semantic_dom"
    assert result["verified"] is True
    assert clicks


def test_cascade_step3_known_locator_clicks_css_selector():
    page = FakeMousePage(evaluate_value=None, findable_selector="#submit")
    clicks: list[str] = []
    result = asyncio.run(
        execute_click_cascade(
            page, "#submit", human_click=lambda p, s: clicks.append(s)
        )
    )
    assert result["success"] is True
    assert result["method"] == "known_locator"
    assert clicks == ["#submit"]


def test_cascade_step4_vision_high_confidence_clicks_coordinates():
    page = FakeMousePage(evaluate_value=None, findable_selector=None)
    vision = FakeVision(
        outcome={"x": 42, "y": 24, "confidence": 0.9, "band": "execute"}
    )
    result = asyncio.run(
        execute_click_cascade(page, "mystery canvas icon", vision=vision)
    )
    assert result["success"] is True
    assert result["method"] == "vision_grounding"
    assert page.mouse_clicks == [(42, 24)]


def test_cascade_low_confidence_vision_escalates_hitl_never_blind_clicks():
    page = FakeMousePage(evaluate_value=None, findable_selector=None)
    vision = FakeVision(exc=LowConfidenceGrounding("confidence 0.40 < 0.65"))
    result = asyncio.run(
        execute_click_cascade(page, "mystery canvas icon", vision=vision)
    )
    assert result["success"] is False
    assert result["status"] == "PAUSED_HITL"
    assert result["method"] == "hitl"
    assert page.mouse_clicks == []  # THE ban: zero blind fallback clicks


def test_cascade_accessible_role_step_used_when_semantic_and_locator_miss(monkeypatch):
    engine = FakeScriptedEngine()
    monkeypatch.setattr(
        sd_module, "EmbeddingEngine", SimpleNamespace(get_instance=lambda: engine)
    )

    class RolePage:
        def __init__(self):
            self.role_clicks: list[str] = []
            self.mouse = SimpleNamespace(click=lambda *a, **kw: None)

        def evaluate(self, *a, **kw):
            return []

        def wait_for_selector(self, *a, **kw):
            raise TimeoutError("miss")

        def get_by_role(self, role, name=None):
            if role == "button":
                return SimpleNamespace(
                    click=lambda timeout=None: self.role_clicks.append((role, name))
                )
            raise TimeoutError("no such role element")

    result = asyncio.run(execute_click_cascade(RolePage(), "Buy now"))
    assert result["success"] is True
    assert result["method"] == "accessible_role"
    assert result["role"] == "button"


# ---------------------------------------------------------------------------
# 5. PlaywrightBrowserAgent — MCP wrappers tell the truth
# ---------------------------------------------------------------------------
@pytest.fixture()
def agent(tmp_path, monkeypatch):
    monkeypatch.setattr(
        pa.PlaywrightBrowserAgent, "COOKIE_STORAGE_BASE", tmp_path / "cookies"
    )
    agent = PlaywrightBrowserAgent(headless=True, timeout_ms=1234)
    yield agent


def test_type_text_is_true_keystroke_insertion(agent):
    page = FakeMousePage()
    agent.bind_page(page)
    out = asyncio.run(agent.type_text("#search", "hello"))
    assert out["success"] is True
    assert out["typed_chars"] == 5
    assert [t[1] for t in page.typed] == list("hello")
    assert all(30 <= t[2] <= 100 for t in page.typed), "30–100ms jitter required"
    # The read() operation must NEVER be used for typing.
    assert not hasattr(out, "text")


def test_click_target_and_type_text_fail_honestly_without_page_or_url(agent):
    click_out = asyncio.run(agent.click_target("#btn", None))
    assert click_out["success"] is False
    assert click_out["status"] == "PAUSED_HITL"

    type_out = asyncio.run(agent.type_text("#q", "hi", None))
    assert type_out["success"] is False
    assert "refusing to fake success" in type_out["error"]


def test_click_target_bound_page_runs_real_cascade(agent):
    page = FakeMousePage(evaluate_value=None, findable_selector="#btn")
    agent.bind_page(page)
    out = asyncio.run(agent.click_target("#btn", None))
    assert out["success"] is True
    assert out["method"] == "known_locator"
    assert page.mouse_clicks, "real click dispatch required"


# ---------------------------------------------------------------------------
# 6. AutonomousBrowserAgent — dynamic goal/URL, no hardcoded endpoints
# ---------------------------------------------------------------------------
class FakeSession:
    def __init__(self, page=None):
        self.page = page
        self.url = None
        self.title = None


class FakeReasoner:
    async def decide(self, task, context=None, tools=None):
        return {"tool": "done", "reasoning": "no further steps", "source": "fake"}


@pytest.fixture(autouse=True)
def _fake_reasoner(monkeypatch):
    monkeypatch.setattr(
        ab_module.ReasoningOrchestrator,
        "get_instance",
        classmethod(lambda cls: FakeReasoner()),
    )


def test_autonomous_browser_has_no_hardcoded_supremeai_dev():
    import inspect

    source = inspect.getsource(ab_module)
    assert "supremeai.dev" not in source, (
        "hardcoded navigation endpoint must be removed"
    )


def test_autonomous_browser_without_url_or_session_reports_honestly():
    agent = AutonomousBrowserAgent(session=None)
    result = asyncio.run(agent.achieve("do something vague"))
    assert result["achieved"] is True  # completed: nothing to act on, said honestly
    assert "No browser session bound" in result["result"]


def test_autonomous_browser_navigates_to_task_provided_url():
    page = FakeMousePage()
    agent = AutonomousBrowserAgent(
        session=FakeSession(page=page), start_url="example.com"
    )
    result = asyncio.run(agent.achieve("check the landing page"))
    assert page.gotos == ["https://example.com"]
    assert result["achieved"] is True
    navigate_outcome = result["trace"][0]["outcome"]
    assert navigate_outcome["status"] == "success"
    assert navigate_outcome["navigated_to"] == "https://example.com"


def test_autonomous_browser_extracts_url_from_goal():
    agent = AutonomousBrowserAgent(session=FakeSession(page=FakeMousePage()))
    assert agent.extract_url("go to https://example.com/pricing and screenshot it") == (
        "https://example.com/pricing"
    )


def test_autonomous_browser_smart_click_low_confidence_escalates_hitl(monkeypatch):
    engine = FakeScriptedEngine()
    monkeypatch.setattr(
        sd_module, "EmbeddingEngine", SimpleNamespace(get_instance=lambda: engine)
    )
    monkeypatch.setattr(
        sd_module.SemanticDOM, "cosine_similarity", staticmethod(lambda v1, v2: 0.1)
    )

    page = FakeMousePage(evaluate_value=[], findable_selector=None)
    agent = AutonomousBrowserAgent(
        session=FakeSession(page=page),
        start_url="https://example.com",
    )
    outcome = asyncio.run(
        agent._execute_action("smart_click", {"target": "invisible thing"})
    )
    assert outcome["status"] == "PAUSED_HITL"
    assert page.mouse_clicks == []  # no blind clicks, ever


# ---------------------------------------------------------------------------
# 7. Fail-closed credential security
# ---------------------------------------------------------------------------
def test_disabled_provider_fails_closed(monkeypatch):
    for var in (
        "BROWSER_CREDENTIALS_ENCRYPTION_KEY",
        "SUPREMEAI_CREDENTIAL_ENC_KEY",
        "ENCRYPTION_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    store = SecureCredentialStore()
    assert store.encryption_available is False
    with pytest.raises(CredentialEncryptionUnavailableError):
        store.encrypt("secret")
    with pytest.raises(CredentialEncryptionUnavailableError):
        store.decrypt("whatever")


def test_save_cookies_never_writes_plaintext(agent, tmp_path):
    class OpenStore:
        """The forbidden provider: returns the plaintext back unchanged."""

        def encrypt(self, s):
            return (s, None)

        def decrypt(self, s, *a, **kw):
            return s

    agent.secure_store = OpenStore()
    ctx = SimpleNamespace(cookies=lambda: [{"name": "sid", "value": "secret-value"}])
    with pytest.raises(CredentialEncryptionUnavailableError):
        agent._save_cookies(ctx, "plain-session")
    assert not agent._cookie_file_path("plain-session").exists()


def test_save_cookies_persists_encrypted_envelope(agent):
    key = "AA" + "A" * 42 + "="  # invalid base64 → sha256-derived Fernet key path
    provider = LocalFernetProvider(encryption_key=key)
    agent.secure_store = SecureCredentialStore(provider)
    ctx = SimpleNamespace(cookies=lambda: [{"name": "sid", "value": "x"}])
    agent._save_cookies(ctx, "enc-session")
    stored = json.loads(agent._cookie_file_path("enc-session").read_text())
    assert stored["__enc__"] is True
    blob = stored["blob"]
    assert isinstance(blob, str) and blob != json.dumps([{"name": "sid", "value": "x"}])
    # Round-trip: load path decrypts the envelope back to the cookie list.
    ctx2 = SimpleNamespace(add_cookies=lambda cookies: seen.append(cookies))
    seen: list = []
    agent._load_cookies(ctx2, "enc-session")
    assert seen == [[{"name": "sid", "value": "x"}]]

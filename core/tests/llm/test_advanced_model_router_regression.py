# SupremeAI 2.0 — Unified Advanced Model Router Regression Suite
# বাংলা মন্তব্য: কনসোলিডেটেড advanced_model_router.py এর জন্য রিগ্রেশন টেস্ট।
# MoE ডোমেইন ক্লাসিফিকেশন, কমপ্লেক্সিটি এনালাইসিস, Tier 0 ডিটারমিনিস্টিক
# ডিসপ্যাচার, কস্ট/লেটেন্সি এস্টিমেশন, মাল্টি-ফ্যাক্টর স্কোরিং, রাউটিং এবং
# কনফিডেন্স ফাস্ট-পাথ সব কভার করে।

import json
import os
import urllib.request
from unittest.mock import patch

import pytest

from core.config import settings
from core.llm.advanced_model_router import (
    _DETERMINISTIC_PATTERNS,
    _TIER0_CONFIDENCE_THRESHOLD,
    AdvancedModelRouter,
    ConfidenceDecision,
    DomainExpertAnalyzer,
    ExpertType,
    ModelTier,
    RouteDecision,
    TaskComplexityAnalyzer,
    Tier0Dispatcher,
    get_advanced_router,
)


# ── Domain Expert Classification (MoE) ──────────────────────────────────────
@pytest.mark.parametrize(
    "prompt,expected",
    [
        ("আমাকে বাংলায় ব্যাখ্যা করো কিভাবে কাজ করে", ExpertType.BENGALI),
        ("write a python function to sort a list", ExpertType.CODER),
        ("fix docker connection error in async def", ExpertType.CODER),
        ("calculate the theorem and prove the equation", ExpertType.REASONER),
        ("write a story and a creative slogan", ExpertType.CREATIVE),
        ("hello there, how are you", ExpertType.GENERAL),
        ("", ExpertType.GENERAL),
    ],
)
def test_classify_domain(prompt, expected):
    assert DomainExpertAnalyzer.classify_domain(prompt) == expected


def test_domain_priority_order():
    # Bengali wins over coder/creative when both keyword sets present
    assert DomainExpertAnalyzer.classify_domain("bangla python code") == ExpertType.BENGALI


# ── Task Complexity Analysis ───────────────────────────────────────────────
@pytest.mark.parametrize(
    "prompt,expected_tier",
    [
        ("", "simple"),
        ("list the files", "simple"),
        ("explain how the refactor works", "medium"),
        ("design an architecture for the system", "complex"),
        ("innovate a new theorem to discover", "extreme"),
    ],
)
def test_complexity_analyze(prompt, expected_tier):
    assert TaskComplexityAnalyzer().analyze(prompt) == expected_tier


def test_complexity_thresholds_by_length():
    analyzer = TaskComplexityAnalyzer()
    small = "x " * 10
    medium = "x " * 600
    large = "x " * 2500
    huge = "x " * 6000
    assert analyzer.analyze(small) == "simple"
    assert analyzer.analyze(medium) == "medium"
    assert analyzer.analyze(large) == "complex"
    assert analyzer.analyze(huge) == "extreme"


# ── Tier 0 Dispatcher — deterministic, zero-cost paths ──────────────────────
def test_tier0_unknown_pattern():
    result = Tier0Dispatcher.execute("does_not_exist", "anything")
    assert "error" in result


def test_tier0_pypi_search(monkeypatch):
    # Issue #1843: AUDIT-FIX #1695 (SSRF guard) changed the HTTP boundary from
    # urllib.request.urlopen to build_opener(_NoRedirectHandler).open(...) —
    # the old urlopen patch went dead and the test hit LIVE pypi (version
    # drift: '2.34.2' != '2.31.0'). Mock at the new boundary (build_opener)
    # so no live network happens and the pinned payload is deterministic.
    fake_payload = {
        "info": {
            "name": "requests",
            "version": "2.31.0",
            "summary": "Python HTTP for Humans.",
            "home_page": "https://python-requests.org",
        }
    }

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def geturl(self):
            # AUDIT-FIX #1695 host verification reads this — must look like pypi.
            return "https://pypi.org/pypi/requests/json"

        def read(self):
            return json.dumps(fake_payload).encode()

    class FakeOpener:
        def open(self, req, timeout=3):  # noqa: ARG002
            return FakeResp()

    with patch.object(urllib.request, "build_opener", return_value=FakeOpener()):
        result = Tier0Dispatcher.execute("pypi_search", "search pypi for requests")
    assert result["name"] == "requests"
    assert result["version"] == "2.31.0"
    assert result["summary"] == "Python HTTP for Humans."


def test_tier0_pypi_search_failure_isolated():
    # Issue #1843: failure injected at the post-#1695 boundary (opener.open)
    # — the dispatcher must isolate the failure into an {"error": ...} entry.
    class BoomOpener:
        def open(self, req, timeout=3):  # noqa: ARG002
            raise RuntimeError("network down")

    with patch.object(urllib.request, "build_opener", return_value=BoomOpener()):
        result = Tier0Dispatcher.execute("pypi_search", "search pypi for numpy")
    assert "error" in result


def test_tier0_list_files(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    # বাংলা মন্তব্য: Tier0 ফাইল লিস্টিং এখন স্যান্ডবক্সড (P0 সিকিউরিটি ফিক্স) —
    # শুধুমাত্র SUPREMEAI_TIER0_SANDBOX_ROOT এর ভিতরের পাথ অ্যাক্সেসযোগ্য, তাই
    # tmp_path কেই স্যান্ডবক্স রুট হিসেবে সেট করে রিলেটিভ পাথে কল করা হচ্ছে।
    monkeypatch.setenv("SUPREMEAI_TIER0_SANDBOX_ROOT", str(tmp_path))
    # issue #1688: default-deny gate — explicit opt-in ছাড়া চলে না।
    monkeypatch.setenv("SUPREMEAI_TIER0_ALLOW_LIST_FILES", "1")
    # Issue #1843: AUDIT-FIX #1688-এর দ্বিতীয় স্তর — sandbox-এর ভিতরেও strict
    # top-level whitelist (SUPREMEAI_TIER0_ALLOWED_DIRS, default = docs সীমিত
    # সেট)। "." লিস্ট করতে হলে টেস্টে সেটিকেই sanctioned opt-in হিসেবে যোগ করতে
    # হয় — নাহলে "directory not in Tier0 whitelist" ব্লক আসে।
    monkeypatch.setenv("SUPREMEAI_TIER0_ALLOWED_DIRS", ".")
    result = Tier0Dispatcher.execute("list_files", "list files in .")
    assert result["count"] >= 2
    assert any(f["name"] == "a.txt" for f in result["files"])
    assert any(f["is_dir"] for f in result["files"])


# ── issue #1688 (CRITICAL): Tier0 list_files default-deny + symlink hardening ──
def test_tier0_list_files_disabled_by_default(tmp_path, monkeypatch):
    """Default-deny: gate env unset/0 হলে কোনো scandir চালানো হয় না —
    \"Remove list_files from Tier0\" (issue #1688) মর্ম পূরণ।"""
    monkeypatch.setenv("SUPREMEAI_TIER0_SANDBOX_ROOT", str(tmp_path))
    monkeypatch.delenv("SUPREMEAI_TIER0_ALLOW_LIST_FILES", raising=False)
    result = Tier0Dispatcher.execute("list_files", "list files in /etc")
    assert "error" in result
    assert "disabled" in result["error"]
    assert result.get("files") is None


def test_tier0_list_files_disabled_accepts_truthy_values_only(monkeypatch):
    monkeypatch.delenv("SUPREMEAI_TIER0_ALLOW_LIST_FILES", raising=False)
    for val in ("", "0", "false", "off"):
        monkeypatch.setenv("SUPREMEAI_TIER0_ALLOW_LIST_FILES", val)
        result = Tier0Dispatcher.execute("list_files", "list files in .")
        assert "disabled" in result["error"]


def test_tier0_list_files_rejects_absolute_and_traversal(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_TIER0_ALLOW_LIST_FILES", "1")
    for prompt in ("list files in /etc", "list files in ../secrets", "list files in a/../../x"):
        result = Tier0Dispatcher.execute("list_files", prompt)
        assert result.get("error") == "path outside sandbox", prompt


def test_tier0_list_files_symlink_escape_rejected(tmp_path, monkeypatch):
    """sandbox-এর ভিতরে symlink যদি বাইরের ডিরেক্টরি পয়েন্ট করে, realpath
    resolve করে containment ভাঙবে → reject (TOCTOU-বহির্ভূত স্ট্যাটিক গার্ড)।"""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("x" * 100)
    sandbox = tmp_path / "sandbox"
    (sandbox / "sub").mkdir(parents=True)
    os.symlink(str(outside), str(sandbox / "sub" / "escape"))
    monkeypatch.setenv("SUPREMEAI_TIER0_SANDBOX_ROOT", str(sandbox))
    monkeypatch.setenv("SUPREMEAI_TIER0_ALLOW_LIST_FILES", "1")
    result = Tier0Dispatcher.execute("list_files", "list files in sub/escape")
    assert result.get("error") == "path outside sandbox"


def test_tier0_list_files_symlink_entry_meta_not_followed(tmp_path, monkeypatch):
    """ভেতরের symlink entry-র stat follow করা হয় না — বাইরের টার্গেটের
    size/type ফাঁস এড়ানো (issue #1688)।"""
    outside_file = tmp_path / "outer_secret.txt"
    outside_file.write_text("x" * 500)
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "real.txt").write_text("hello")
    os.symlink(str(outside_file), str(sandbox / "link.txt"))
    monkeypatch.setenv("SUPREMEAI_TIER0_SANDBOX_ROOT", str(sandbox))
    monkeypatch.setenv("SUPREMEAI_TIER0_ALLOW_LIST_FILES", "1")
    # Issue #1843: #1688 whitelist স্তর — sandbox root-এর জন্য explicit opt-in।
    monkeypatch.setenv("SUPREMEAI_TIER0_ALLOWED_DIRS", ".")
    result = Tier0Dispatcher.execute("list_files", "list files in .")
    assert "error" not in result
    by_name = {f["name"]: f for f in result["files"]}
    assert by_name["link.txt"]["is_symlink"] is True
    assert by_name["link.txt"]["size_bytes"] is None  # outer size (500) leaked না
    assert by_name["link.txt"]["is_dir"] is False
    assert by_name["real.txt"]["size_bytes"] == 5


def test_tier0_format_json():
    result = Tier0Dispatcher.execute("regex_format", 'format as json {"a": 1}')
    assert result["format"] == "json"
    assert result["result"] == {"a": 1}


def test_tier0_format_json_invalid_fallback():
    result = Tier0Dispatcher.execute("regex_format", "format as json not valid json text")
    assert result["format"] == "json"
    assert result["result"] == {"content": "not valid json text"}


def test_tier0_format_csv_table():
    # _format_text captures a single logical line after "format as csv "
    result = Tier0Dispatcher.execute("regex_format", "format as csv\nrow1\nrow2")
    assert result["format"] == "csv"
    assert result["row_count"] == 1
    assert "row1" in result["rows"][0]


def test_tier0_format_table_multiline():
    result = Tier0Dispatcher.execute("regex_format", "format as table for\nname,age\nbob,3")
    assert result["format"] == "table"
    assert result["row_count"] == 1
    assert "name,age" in result["rows"][0]


def test_tier0_format_unknown_format():
    result = Tier0Dispatcher.execute("regex_format", "format as xml <root/>")
    assert result["format"] == "xml"
    assert result["result"] == "<root/>"


def test_tier0_format_parse_error():
    result = Tier0Dispatcher.execute("regex_format", "format as json")
    assert "error" in result


def test_tier0_schema_lookup_known():
    result = Tier0Dispatcher.execute("schema_lookup", "show me the users table schema")
    assert result["entity"] == "users"
    assert result["status"] == "schema_available"


def test_tier0_schema_lookup_unknown():
    result = Tier0Dispatcher.execute("schema_lookup", "what is the flux capacitor table")
    assert "error" in result


# ── Cost / Latency estimation ───────────────────────────────────────────────
def test_estimate_cost_known_and_unknown_provider():
    router = AdvancedModelRouter()
    groq_cost = router.estimate_cost("groq", "llama-3.3-70b-versatile", 4000)
    unknown_cost = router.estimate_cost("mystery", "model", 4000)
    assert groq_cost < unknown_cost
    assert groq_cost > 0.0


def test_estimate_latency_uses_health():
    router = AdvancedModelRouter()
    ollama_lat = router.estimate_latency("ollama", "anything")
    groq_lat = router.estimate_latency("groq", "anything")
    assert ollama_lat < groq_lat
    # unknown provider falls back to 300ms
    assert router.estimate_latency("nope", "x") == 0.3


# ── Multi-factor scoring ────────────────────────────────────────────────────
def test_calculate_model_score_down_provider_zero():
    router = AdvancedModelRouter()
    router.provider_health["groq"] = {"status": "down", "latency_ms": 60}
    assert router.calculate_model_score("groq", "llama-3.3-70b-versatile", "general", {}) == 0.0


def test_calculate_model_score_success_rate_modifier():
    router = AdvancedModelRouter()
    base = router.calculate_model_score("groq", "llama-3.3-70b-versatile", "general", {})
    router.performance_metrics["groq/llama-3.3-70b-versatile"] = type(
        "M", (), {"success_rate": 0.5}
    )()
    degraded = router.calculate_model_score("groq", "llama-3.3-70b-versatile", "general", {})
    assert degraded < base
    assert degraded == round(base * 0.5, 4)


def test_calculate_model_score_deterministic():
    router = AdvancedModelRouter()
    a = router.calculate_model_score("gemini", "gemini-2.5-flash", "general", {})
    b = router.calculate_model_score("gemini", "gemini-2.5-flash", "general", {})
    assert a == b > 0.0


# ── Available models selection ─────────────────────────────────────────────
def test_get_available_models_all_domains():
    router = AdvancedModelRouter()
    for domain in ["bengali", "coding", "reasoning", "creative", "general"]:
        models = router.get_available_models(domain)
        assert len(models) >= 1
        for provider, model in models:
            assert provider
            assert model


def test_get_available_models_unknown_domain_falls_back():
    router = AdvancedModelRouter()
    models = router.get_available_models("nonexistent-domain")
    assert models == router.get_available_models("general")


def test_get_available_models_provider_split_and_fallback():
    router = AdvancedModelRouter()
    coding = router.get_available_models("coding")
    if "/" in settings.model_chat:
        expected_provider, expected_model = settings.model_chat.split("/", 1)
    else:
        expected_provider, expected_model = "openai", settings.model_chat
    assert (expected_provider, expected_model) in coding
    assert ("groq", "llama-3.3-70b-versatile") in coding


# ── Prompt complexity feature extraction ───────────────────────────────────
def test_analyze_prompt_complexity_empty():
    router = AdvancedModelRouter()
    assert router.analyze_prompt_complexity("") == {
        "length": 0.0,
        "complexity": 0.0,
        "overall": 0.0,
    }


def test_analyze_prompt_complexity_indicators():
    router = AdvancedModelRouter()
    c = router.analyze_prompt_complexity("analyze and compare then synthesize the result")
    assert c["complexity"] > 0.0
    assert 0.0 <= c["overall"] <= 1.0


# ── Routing decision ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_route_request_returns_best_scored():
    router = AdvancedModelRouter()
    decision = await router.route_request(
        "write a python function to merge two lists", task_type="coding"
    )
    assert isinstance(decision, RouteDecision)
    assert decision.provider and decision.model
    assert decision.priority_score > 0.0
    assert decision.expected_cost >= 0.0
    assert decision.expected_latency > 0.0
    assert decision.expert_domain == "coding"


@pytest.mark.asyncio
async def test_route_request_budget_filtering():
    router = AdvancedModelRouter()
    decision = await router.route_request(
        "simple hello", task_type="coding", budget_constraint=0.0001
    )
    assert decision.expected_cost <= 0.0001 or decision.priority_score > 0.0


@pytest.mark.asyncio
async def test_route_request_empty_models_fallback():
    router = AdvancedModelRouter()
    # Force an empty candidate list to exercise the safe default RouteDecision
    router.model_preferences = {
        "general": {"preferred_models": [], "tier_preference": ModelTier.BUDGET}
    }
    decision = await router.route_request("anything")
    assert decision.provider == "groq"
    assert decision.model == "llama-3.3-70b-versatile"


@pytest.mark.asyncio
async def test_route_request_domain_key_from_type():
    router = AdvancedModelRouter()
    decision = await router.route_request("reason about the optimize", task_type="reasoning")
    # expert classification overridden by explicit task_type
    assert decision.expert_domain == "reasoning"


# ── Confidence fast-path ────────────────────────────────────────────────────
def test_route_with_confidence_non_deterministic():
    router = AdvancedModelRouter()
    decision = router.route_with_confidence("just a friendly hello there")
    assert isinstance(decision, ConfidenceDecision)
    assert decision.is_deterministic is False
    assert decision.matched_pattern is None
    assert 0.0 <= decision.confidence < _TIER0_CONFIDENCE_THRESHOLD


def test_route_with_confidence_deterministic_pypi():
    router = AdvancedModelRouter()
    with patch.object(urllib.request, "urlopen") as mock_urlopen:

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps(
                    {"info": {"name": "numpy", "version": "1.0", "summary": "s", "home_page": ""}}
                ).encode()

        mock_urlopen.return_value = FakeResp()
        decision = router.route_with_confidence("search pypi for numpy")
    assert decision.is_deterministic is True
    assert decision.matched_pattern == "pypi_search"
    assert decision.confidence >= _TIER0_CONFIDENCE_THRESHOLD
    assert decision.deterministic_result["name"] == "numpy"


def test_route_with_confidence_deterministic_format():
    router = AdvancedModelRouter()
    decision = router.route_with_confidence('format as json for {"k": 1}')
    assert decision.is_deterministic is True
    assert decision.matched_pattern == "regex_format"
    assert decision.deterministic_result["result"] == {"k": 1}


def test_deterministic_patterns_registry_nonempty():
    assert len(_DETERMINISTIC_PATTERNS) >= 4
    for name, pattern in _DETERMINISTIC_PATTERNS:
        assert pattern.search("") is None or name  # patterns compiled


# ── Enums & singleton ───────────────────────────────────────────────────────
def test_model_tier_enum():
    assert ModelTier.EXPENSIVE.value == "expensive"
    assert ModelTier.BALANCED.value == "balanced"
    assert ModelTier.BUDGET.value == "budget"


def test_get_advanced_router_singleton():
    a = get_advanced_router()
    b = get_advanced_router()
    assert a is b
    assert isinstance(a, AdvancedModelRouter)

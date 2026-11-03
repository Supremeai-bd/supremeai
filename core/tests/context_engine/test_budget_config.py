"""M07 P-E + P-F — estimator unification + config/kill-switch চুক্তি-টেস্ট।

বাংলা: এস্টিমেটর এক ও মালিক এক (M19 bengali_text → token_budget → engine);
section-caps ও default budget env-চালিত (zero-hardcode, ডিফল্ট = আজকের
আচরণ); kill-switch SUPREMEAI_CONTEXT_ENGINE=off → raw-prompt পথ; অজানা-মান
fail-closed (নীরব সক্রিয় নয়)।
"""

from __future__ import annotations

import pytest

from context_engine import ContextBlock, ContextEngine, Section
from context_engine.budget import (
    DEFAULT_INPUT_BUDGET,
    SECTION_CAPS,
    context_engine_enabled,
    estimate_tokens,
    resolve_input_budget,
    resolve_section_caps,
)

# ---------------------------------------------------------------------------
# P-E: এক estimator
# ---------------------------------------------------------------------------


def test_estimate_tokens_delegates_to_single_owner():
    from core.i18n.bengali_text import estimate_tokens_bengali_aware
    from core.llm.token_budget import estimate_tokens as canonical

    for text in ("", "Hello, world!", "বাংলা প্রম্পট টোকেন সত্য", "x" * 100):
        assert estimate_tokens(text) == canonical(text)
        assert estimate_tokens(text) == estimate_tokens_bengali_aware(text)


def test_bengali_no_longer_undercounted_vs_legacy_heuristic():
    # বাংলা: পুরনো chars÷4 heuristic বাংলায় ~২ গুণ under-count করত —
    # ঐক্যবদ্ধ মালিকের blended ওজন সেটি বন্ধ করে (quota-সত্য)।
    bengali = "এটি একটি বাংলা প্রম্পট যা বাজেট পরীক্ষার জন্য ব্যবহৃত হচ্ছে।"
    legacy = max(1, int(len(bengali) / 4) + 1)
    assert estimate_tokens(bengali) > legacy


# ---------------------------------------------------------------------------
# P-F: config ও kill-switch
# ---------------------------------------------------------------------------


def test_section_caps_default_matches_legacy(monkeypatch: pytest.MonkeyPatch):
    for name in (
        "CONTEXT_ENGINE_SYSTEM_CAP",
        "CONTEXT_ENGINE_MEMORY_CAP",
        "CONTEXT_ENGINE_KNOWLEDGE_CAP",
        "CONTEXT_ENGINE_HISTORY_CAP",
    ):
        monkeypatch.delenv(name, raising=False)
    assert resolve_section_caps() == SECTION_CAPS


def test_section_caps_env_override_and_invalid_loud_fallback(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CONTEXT_ENGINE_SYSTEM_CAP", "0.5")
    monkeypatch.setenv("CONTEXT_ENGINE_HISTORY_CAP", "not-a-float")
    monkeypatch.setenv("CONTEXT_ENGINE_MEMORY_CAP", "1.5")  # সীমাবহির্ভূত
    caps = resolve_section_caps()
    assert caps["system"] == 0.5
    assert caps["history"] == SECTION_CAPS["history"]  # লাউড-ফলব্যাক
    assert caps["memory"] == SECTION_CAPS["memory"]  # সীমাবহির্ভূত → ডিফল্ট


def test_resolve_input_budget_env_and_invalid(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CONTEXT_ENGINE_DEFAULT_INPUT_BUDGET", raising=False)
    assert resolve_input_budget() == DEFAULT_INPUT_BUDGET

    monkeypatch.setenv("CONTEXT_ENGINE_DEFAULT_INPUT_BUDGET", "1200")
    assert resolve_input_budget() == 1200

    monkeypatch.setenv("CONTEXT_ENGINE_DEFAULT_INPUT_BUDGET", "-3")
    assert resolve_input_budget() == DEFAULT_INPUT_BUDGET


def test_engine_assemble_honors_section_cap_override(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SUPREMEAI_CONTEXT_ENGINE", raising=False)
    monkeypatch.setenv("CONTEXT_ENGINE_SYSTEM_CAP", "0.1")
    # বাংলা: এস্টিমেটর-সচেতন নির্মাণ — block-এর token প্রথমে মেপে cap-অতিক্রমী
    # করে তৈরি করা হয় (1000 বাজেটে 0.1 cap = 100 tokens)।
    big_text = "S" * 800
    assert estimate_tokens(big_text) > 100
    blocks = [
        ContextBlock(section=Section.SYSTEM, text=big_text, priority=0, block_id="sys"),
        ContextBlock(section=Section.USER, text="hello", priority=0, block_id="user"),
    ]
    report = ContextEngine().assemble(blocks, max_input_tokens=1000).report
    # বাংলা: P-G সততা-চুক্তি — অতিরিক্ত system block drop হয় না, cap-এ
    # কেটে যায় এবং truncated_sections-এ স্পষ্ট রিপোর্ট হয় (নীরব নয়)।
    assert "system" in report.truncated_sections
    assert "sys" not in report.dropped


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("off", False), ("on", True), ("true", True), ("", True)],
)
def test_context_engine_kill_switch_values(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
):
    monkeypatch.setenv("SUPREMEAI_CONTEXT_ENGINE", raw)
    assert context_engine_enabled() is expected


def test_context_engine_unknown_value_fails_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPREMEAI_CONTEXT_ENGINE", "maybe")
    assert context_engine_enabled() is False


def test_engine_disabled_raw_passthrough_contract(monkeypatch: pytest.MonkeyPatch):
    # বাংলা: gate বন্ধ থাকলে route-স্তর raw prompt পাঠায় — engine নিজে
    # কোনো ভান করে না; এই টেস্ট gate-ফাংশনের চুক্তিই ধরে রাখে।
    monkeypatch.setenv("SUPREMEAI_CONTEXT_ENGINE", "off")
    assert context_engine_enabled() is False
    monkeypatch.setenv("SUPREMEAI_CONTEXT_ENGINE", "on")
    assert context_engine_enabled() is True

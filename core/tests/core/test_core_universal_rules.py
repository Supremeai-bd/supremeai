# tests/test_core_universal_rules.py
"""Tests for the core Universal Rules Engine (constitutional rules)."""

import pytest

from core.universal_rules import UniversalRulesEngine


@pytest.fixture
def engine(tmp_path):
    rules_file = tmp_path / "admin_rules.json"
    return UniversalRulesEngine(rules_path=str(rules_file))


def test_mandatory_rules_non_empty(engine):
    rules = engine.validate_critical_rules()
    assert isinstance(rules, list)
    assert "CORE-001" in rules
    assert "CINE_MANDATORY_RULES" not in rules


def test_default_rules_loaded(engine):
    assert engine.rules["cost_management"]["monthly_budget"] == 30.00
    assert engine.rules["language_policy"]["bangla_comments"] is True


def test_check_token_budget(engine):
    assert engine.check_token_budget(100) is True
    assert engine.check_token_budget(5000) is False


def test_check_hallucination_policy(engine):
    assert engine.check_hallucination_policy("see <source>abc</source>") is True
    assert engine.check_hallucination_policy("I don't know the answer") is True
    assert engine.check_hallucination_policy("The capital is definitely X with no doubt") is False


def test_check_production_ready(engine):
    assert engine.check_production_ready(False) is True
    assert engine.check_production_ready(True) is False


def test_check_pii_in_prompt(engine):
    assert engine.check_pii_in_prompt("My phone is 01712345678") is False
    assert engine.check_pii_in_prompt("email me at a@b.com") is False
    assert engine.check_pii_in_prompt("Tell me about quantum physics") is True


def test_check_language_match(engine):
    bangla_in = "আপনি কেমন আছেন"
    assert engine.check_language_match(bangla_in, "আমি ভালো আছি") is True
    assert engine.check_language_match(bangla_in, "I am fine") is False
    assert engine.check_language_match("how are you", "I am fine") is True


def test_check_code_completeness(engine):
    assert engine.check_code_completeness("x = 1\nprint(x)") is True
    assert engine.check_code_completeness("def f():\n    # TODO implement\n    pass") is False


def test_get_provider_for_task(engine):
    assert engine.get_provider_for_task("bn", "chat") == "moonshot"
    assert engine.get_provider_for_task("en", "code") == "deepseek"
    assert engine.get_provider_for_task("en", "private") == "ollama"
    assert engine.get_provider_for_task("en", "chat") == "together_ai"


def test_classify_task(engine):
    assert engine.classify_task("আপনি কেমন আছেন") == "BANGLA_SPECIFIC"
    assert engine.classify_task("fix the python error in my code") == "TECHNICAL"
    assert engine.classify_task("I need help, my issue is not working") == "SUPPORT"
    assert engine.classify_task("explain how does gravity work") == "RESEARCH"
    assert engine.classify_task("analyze this data report") == "ANALYTICAL"
    assert engine.classify_task("write a creative story") == "CREATIVE"
    assert engine.classify_task("hello there") == "CONVERSATIONAL"


def test_get_rule_by_id_missing(engine):
    assert engine.get_rule_by_id("DOES-NOT-EXIST-XYZ") is None


def test_apply_blocks_harmful_request(engine):
    ctx = {"is_harmful_request": True}
    out = engine.apply(ctx)
    assert out["blocked"] is True


def test_apply_pii_warning(engine):
    ctx = {"prompt": "call me at 01712345678"}
    out = engine.apply(ctx)
    assert out.get("pii_warning") is True


def test_apply_direction_override(engine):
    ctx = {"direction": "North"}
    out = engine.apply(ctx)
    assert out["direction_count"] == 5
    assert out["direction_override_applied"] is True


def test_apply_recommends_provider(engine):
    ctx = {"task_lang": "bn", "task_type": "chat"}
    out = engine.apply(ctx)
    assert out["recommended_provider"] == "moonshot"


def test_apply_blocks_incomplete_code(engine):
    ctx = {"generated_code": "def f():\n    # TODO\n    pass"}
    out = engine.apply(ctx)
    assert out["blocked"] is True


def test_save_rules_roundtrip(engine):
    new_rules = {"custom": {"value": 42}}
    assert engine.save_rules(new_rules) is True
    reloaded = UniversalRulesEngine(rules_path=engine.rules_path)
    assert reloaded.rules["custom"]["value"] == 42

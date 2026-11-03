"""Extended tests for UniversalRulesEngine - Business rules deep coverage.

This module tests extended functionality:
- Provider selection intelligence
- Task classification
- PII detection in prompts
- Language match checking
- Code completeness validation
- Token budget enforcement
- Production ready checks
- Rule loading from file
- Agent rules integration
"""

import json
import os
import tempfile

from core.universal_rules import UniversalRulesEngine


class TestProviderSelection:
    """Tests for provider selection intelligence."""

    def test_get_provider_bangla(self):
        """Test provider selection for Bangla tasks."""
        engine = UniversalRulesEngine()

        result = engine.get_provider_for_task(task_lang="bn", task_type="chat")

        assert result == "moonshot"

    def test_get_provider_code(self):
        """Test provider selection for code tasks."""
        engine = UniversalRulesEngine()

        result = engine.get_provider_for_task(task_lang="en", task_type="code")

        assert result == "deepseek"

    def test_get_provider_private(self):
        """Test provider selection for private tasks."""
        engine = UniversalRulesEngine()

        result = engine.get_provider_for_task(task_lang="en", task_type="private")

        assert result == "ollama"

    def test_get_provider_reasoning(self):
        """Test provider selection for reasoning tasks."""
        engine = UniversalRulesEngine()

        result = engine.get_provider_for_task(task_lang="en", task_type="reasoning")

        assert result == "moonshot"

    def test_get_provider_default_fallback(self):
        """Test provider selection defaults to Together AI."""
        engine = UniversalRulesEngine()

        result = engine.get_provider_for_task(task_lang="en", task_type="chat")

        assert result == "together_ai"


class TestTaskClassification:
    """Tests for task classification logic."""

    def test_classify_bangla(self):
        """Test classification detects Bangla text."""
        engine = UniversalRulesEngine()

        result = engine.classify_task("আমি কেমন আছি?")

        assert result == "BANGLA_SPECIFIC"

    def test_classify_technical(self):
        """Test classification detects technical queries."""
        engine = UniversalRulesEngine()

        result = engine.classify_task("I need help with Python code error")

        assert result == "TECHNICAL"

    def test_classify_support(self):
        """Test classification detects support queries."""
        engine = UniversalRulesEngine()

        result = engine.classify_task("I have a problem with my account")

        assert result == "SUPPORT"

    def test_classify_research(self):
        """Test classification detects research queries."""
        engine = UniversalRulesEngine()

        result = engine.classify_task("What is quantum computing?")

        assert result == "RESEARCH"

    def test_classify_analytical(self):
        """Test classification detects analytical queries."""
        engine = UniversalRulesEngine()

        result = engine.classify_task("Analyze the sales data report")

        assert result == "ANALYTICAL"

    def test_classify_creative(self):
        """Test classification detects creative requests."""
        engine = UniversalRulesEngine()

        result = engine.classify_task("Write a creative story about AI")

        assert result == "CREATIVE"

    def test_classify_conversational(self):
        """Test classification defaults to conversational."""
        engine = UniversalRulesEngine()

        result = engine.classify_task("Hello, how are you?")

        assert result == "CONVERSATIONAL"


class TestPiiDetection:
    """Tests for PII detection in prompts."""

    def test_pii_bd_phone(self):
        """Test detection of Bangladesh phone numbers."""
        engine = UniversalRulesEngine()

        result = engine.check_pii_in_prompt("Call me at 01712345678")

        assert result is False  # PII found

    def test_pii_email(self):
        """Test detection of email addresses."""
        engine = UniversalRulesEngine()

        result = engine.check_pii_in_prompt("Contact me at test@example.com")

        assert result is False  # PII found

    def test_pii_password(self):
        """Test detection of password patterns."""
        engine = UniversalRulesEngine()

        result = engine.check_pii_in_prompt("password=secret123")

        assert result is False  # PII found

    def test_pii_clean(self):
        """Test clean prompt passes PII check."""
        engine = UniversalRulesEngine()

        result = engine.check_pii_in_prompt("What is the weather today?")

        assert result is True  # Safe

    def test_pii_nid_card(self):
        """Test detection of NID/card numbers."""
        engine = UniversalRulesEngine()

        result = engine.check_pii_in_prompt("My ID is 123456789012")

        assert result is False  # PII found


class TestLanguageMatch:
    """Tests for language match checking."""

    def test_bangla_input_bangla_output(self):
        """Test match when both are Bangla."""
        engine = UniversalRulesEngine()

        result = engine.check_language_match("আপনি কেমন আছেন?", "আমি ভালো আছি")

        assert result is True

    def test_bangla_input_english_output(self):
        """Test mismatch when input Bangla but output English."""
        engine = UniversalRulesEngine()

        result = engine.check_language_match("আপনি কেমন আছেন?", "I am fine")

        assert result is False

    def test_english_input_english_output(self):
        """Test match when both are English."""
        engine = UniversalRulesEngine()

        result = engine.check_language_match("How are you?", "I am fine")

        assert result is True

    def test_empty_input(self):
        """Test with empty input."""
        engine = UniversalRulesEngine()

        result = engine.check_language_match("", "Response")

        assert result is True


class TestCodeCompleteness:
    """Tests for code completeness validation."""

    def test_complete_code(self):
        """Test complete code passes validation."""
        engine = UniversalRulesEngine()

        code = """
def hello():
    print("Hello, World!")
    return True
"""
        result = engine.check_code_completeness(code)

        assert result is True

    def test_todo_in_code(self):
        """Test TODO comments flagged as incomplete."""
        engine = UniversalRulesEngine()

        code = "def hello():  # TODO: implement this"

        result = engine.check_code_completeness(code)

        assert result is False

    def test_fixme_in_code(self):
        """Test FIXME comments flagged as incomplete."""
        engine = UniversalRulesEngine()

        code = "# FIXME: fix this later"

        result = engine.check_code_completeness(code)

        assert result is False

    def test_not_implemented(self):
        """Test NotImplemented flagged as incomplete."""
        engine = UniversalRulesEngine()

        code = "raise NotImplementedError()"

        result = engine.check_code_completeness(code)

        assert result is False

    def test_pass_with_comment(self):
        """Test pass with implementation comment flagged."""
        engine = UniversalRulesEngine()

        code = "pass  # implement later"

        result = engine.check_code_completeness(code)

        assert result is False


class TestTokenBudget:
    """Tests for token budget enforcement."""

    def test_within_budget(self):
        """Test tokens within budget pass."""
        engine = UniversalRulesEngine()

        result = engine.check_token_budget(2000)

        assert result is True

    def test_exceeds_budget(self):
        """Test tokens exceeding budget fail."""
        engine = UniversalRulesEngine()

        result = engine.check_token_budget(5000)

        assert result is False

    def test_zero_tokens(self):
        """Test zero tokens pass."""
        engine = UniversalRulesEngine()

        result = engine.check_token_budget(0)

        assert result is True


class TestProductionReady:
    """Tests for production ready checks."""

    def test_no_mocks(self):
        """Test clean code passes production check."""
        engine = UniversalRulesEngine()

        result = engine.check_production_ready(code_contains_mocks=False)

        assert result is True

    def test_with_mocks(self):
        """Test code with mocks fails production check."""
        engine = UniversalRulesEngine()

        result = engine.check_production_ready(code_contains_mocks=True)

        assert result is False


class TestApplyExtendedRules:
    """Tests for apply() method with extended rules."""

    def test_apply_task_classification(self):
        """Test apply injects task classification."""
        engine = UniversalRulesEngine()

        context = {"prompt": "Search history of AI"}
        result = engine.apply(context)

        assert "task_class" in result
        assert result["task_class"] in ["RESEARCH", "CONVERSATIONAL"]

    def test_apply_provider_selection(self):
        """Test apply injects provider selection."""
        engine = UniversalRulesEngine()

        context = {"task_type": "code"}
        result = engine.apply(context)

        assert "recommended_provider" in result

    def test_apply_pii_warning(self):
        """Test apply adds PII warning when detected."""
        engine = UniversalRulesEngine()

        context = {"prompt": "My email is test@example.com"}
        result = engine.apply(context)

        assert result.get("pii_warning") is True

    def test_apply_language_match(self):
        """Test apply validates language match."""
        engine = UniversalRulesEngine()

        context = {"input_text": "আপনি কেমন আছেন?", "output_text": "I am fine"}
        result = engine.apply(context)

        assert result.get("language_match_ok") is False

    def test_apply_code_completeness(self):
        """Test apply blocks incomplete code."""
        engine = UniversalRulesEngine()

        context = {"generated_code": "# TODO: implement"}
        result = engine.apply(context)

        assert result.get("blocked") is True

    def test_apply_escalation(self):
        """Test apply escalates after multiple failures."""
        engine = UniversalRulesEngine()

        context = {"consecutive_failures": 5}
        result = engine.apply(context)

        assert result.get("escalate_to_human") is True

    def test_apply_harmful_request(self):
        """Test apply blocks harmful requests."""
        engine = UniversalRulesEngine()

        context = {"is_harmful_request": True}
        result = engine.apply(context)

        assert result.get("blocked") is True

    def test_apply_quality_gates(self):
        """Test apply includes quality gates config."""
        engine = UniversalRulesEngine()

        context = {}
        result = engine.apply(context)

        assert "quality_gates_config" in result


class TestRuleLoading:
    """Tests for rule loading from file."""

    def test_load_rules_from_custom_path(self):
        """Test loading rules from custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_path = os.path.join(tmpdir, "custom_rules.json")

            custom = {
                "cost_management": {
                    "monthly_budget": 50.00,
                },
            }

            with open(rules_path, "w", encoding="utf-8") as f:
                json.dump(custom, f)

            engine = UniversalRulesEngine(rules_path=rules_path)

            assert engine.rules["cost_management"]["monthly_budget"] == 50.00

    def test_load_rules_merge(self):
        """Test rules merge from file with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_path = os.path.join(tmpdir, "admin_rules.json")

            custom = {
                "cost_management": {
                    "monthly_budget": 100.00,
                },
            }

            with open(rules_path, "w", encoding="utf-8") as f:
                json.dump(custom, f)

            engine = UniversalRulesEngine(rules_path=rules_path)

            # Custom value should override
            assert engine.rules["cost_management"]["monthly_budget"] == 100.00
            # Other defaults should remain
            assert engine.rules["directions"]["count"] == 5


class TestGetRuleById:
    """Tests for get_rule_by_id method."""

    def test_no_agent_rules(self):
        """Test get_rule_by_id returns None when no agent rules loaded."""
        engine = UniversalRulesEngine()
        engine.agent_rules = []

        result = engine.get_rule_by_id("CORE-001")

        assert result is None

    def test_rule_not_found(self):
        """Test get_rule_by_id returns None for missing rule."""
        engine = UniversalRulesEngine()

        result = engine.get_rule_by_id("NONEXISTENT-RULE")

        assert result is None


class TestValidateCriticalRules:
    """Tests for critical rules validation."""

    def test_returns_mandatory_rules(self):
        """Test validate_critical_rules returns the mandatory rules list."""
        engine = UniversalRulesEngine()

        result = engine.validate_critical_rules()

        assert "CORE-001" in result
        assert "ZERO-108" in result
        assert "AGENT-101" in result
        assert len(result) > 0


class TestDefaultRulesPath:
    """Tests for default rules path."""

    def test_default_path_exists(self):
        """Test that default rules path is correctly set."""
        engine = UniversalRulesEngine()

        # The default path is backend_root / data / admin_rules.json
        expected = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data",
            "admin_rules.json",
        )

        assert engine.rules_path == expected

import os
import sys

import pytest

# Ensure supremeai root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.code_validator import CodeValidator
from core.errors.error_pattern_db import ErrorPatternDB
from core.factual_verifier import FactualVerifier
from core.generation_monitor import GenerationMonitor
from core.output_validator import OutputValidator
from core.security.input_sanitizer import InputSanitizer


def test_input_sanitizer():
    sanitizer = InputSanitizer()
    res = sanitizer.sanitize("predict lottery numbers")
    assert res["is_valid"] is False
    assert "lottery" in res["reason"]

    res2 = sanitizer.sanitize("Write something interesting")
    assert res2["is_valid"] is True
    assert res2["is_ambiguous"] is True

    # Test PII Stripping
    cleaned = sanitizer.strip_pii(
        "Contact me at test@example.com or call +1-555-123-4567. My server is 192.168.1.1."
    )
    assert "[EMAIL]" in cleaned
    assert "[PHONE_NUMBER]" in cleaned
    assert "[IP_ADDRESS]" in cleaned


def test_generation_monitor():
    monitor = GenerationMonitor()
    claims = monitor.flag_factual_claims("Paris is the capital of France.")
    assert len(claims) > 0

    sources = monitor.require_source_attribution("Paris is the capital. [Source: Wiki]")
    assert sources["must_add_sources"] is False


@pytest.mark.anyio
async def test_factual_verifier():
    class _FakeDDGS:
        """Deterministic search boundary — no live network in CI."""

        def text(self, query, max_results=3):
            return iter([{"href": "https://en.wikipedia.org/wiki/Paris"}])

    verifier = FactualVerifier()
    # Inject the fake search provider so the ddgs code path is exercised
    # deterministically instead of hitting the live network.
    verifier._ddgs = _FakeDDGS()
    res = await verifier.verify_with_web_search("The capital of France is Paris")
    assert res["is_verified"] is True

    math_res = verifier.verify_math("2 + 2", "4")
    assert math_res["is_verified"] is True

    math_res2 = verifier.verify_math("2 + 2", "5")
    assert math_res2["is_verified"] is False

    # Test symbolic equation verification with Sympy.
    # sympy is an OPTIONAL dependency (core/factual_verifier.py module
    # docstring): when absent, verify_math honestly degrades to the numeric
    # safe-eval fallback, which cannot validate symbolic identities and must
    # return is_verified=False. Assert the symbolic contract only when the
    # capability is installed (issue #1068: CI poetry env does not ship sympy).
    import importlib.util

    _has_sympy = importlib.util.find_spec("sympy") is not None
    symbolic_res = verifier.verify_math("x + x", "2*x")
    if _has_sympy:
        assert symbolic_res["is_verified"] is True
        assert symbolic_res.get("expression_sympy") == "2*x"
    else:
        # Honest degradation: fallback must NOT claim verification of a
        # symbolic identity it could not evaluate.
        assert symbolic_res["is_verified"] is False


def test_code_validator():
    validator = CodeValidator()
    res = validator.validate_syntax("def foo():\n    pass", "python")
    assert res["is_valid"] is True

    res2 = validator.validate_syntax("def foo(\n    pass", "python")
    assert res2["is_valid"] is False

    # Check indentation check
    bad_indent = "def foo():\n  pass\n    return 1"
    res3 = validator.validate_syntax(bad_indent, "python")
    assert res3["is_valid"] is False

    # Check undefined variables
    undefined_var = "def foo():\n    return x"
    res4 = validator.validate_syntax(undefined_var, "python")
    assert res4["is_valid"] is False

    url_res = validator.validate_url("https://github.com/nadim9/supremeai.git")
    assert url_res["is_valid"] is False


def test_output_validator():
    validator = OutputValidator()
    res = validator.validate("Repository: https://github.com/nadim9/supremeai.git")
    assert res["is_valid"] is False
    assert res["confidence"]["badge"] == "LOW_CONFIDENCE"

    # MultiAICodeGenerator test — task must be passed as a keyword argument;
    # the first three positional slots are the per-provider code candidates.
    consensus_res = validator.multi_generator.generate_with_consensus(
        "def foo():\n    return 1",
        "def foo():\n    return 1",
        "def foo():\n    return 2",
        task="Generate a simple function",
    )
    assert "foo" in consensus_res["code"]

    # HumanReviewPolicy test
    assert validator.human_policy.requires_human_review("python_code", {"overall": 0.9}) is True
    assert validator.human_policy.requires_human_review("text", {"overall": 0.6}) is True


def test_error_pattern_db():
    db = ErrorPatternDB("test_patterns.db")
    db.log_error("nadim9/supremeai", "hallucination", "paykaribazaronline/supremeai")
    pattern = db.check_pattern("This is a repo: nadim9/supremeai")
    assert pattern["should_prevent"] is True

    db.log_ai_mistake(
        {
            "model": "Kimi",
            "type": "indentation",
            "task": "writing validator",
            "original": "def x():\n  pass",
            "correct": "def x():\n    pass",
            "root_cause": "nested block",
            "prevention": "run ast validation",
        }
    )
    strategy = db.get_prevention_strategy("Kimi", "writing validator")
    assert strategy == "run ast validation"

    # Cleanup test db
    if os.path.exists("test_patterns.db"):
        os.remove("test_patterns.db")

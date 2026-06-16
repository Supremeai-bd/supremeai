import pytest
import os
import sys

# Ensure supremeai root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.input_sanitizer import InputSanitizer
from core.generation_monitor import GenerationMonitor
from core.factual_verifier import FactualVerifier
from core.code_validator import CodeValidator
from core.output_validator import OutputValidator
from core.error_pattern_db import ErrorPatternDB

def test_input_sanitizer():
    sanitizer = InputSanitizer()
    res = sanitizer.sanitize("predict lottery numbers")
    assert res["is_valid"] is False
    assert "lottery" in res["reason"]

    res2 = sanitizer.sanitize("Write something interesting")
    assert res2["is_valid"] is True
    assert res2["is_ambiguous"] is True

def test_generation_monitor():
    monitor = GenerationMonitor()
    claims = monitor.flag_factual_claims("Paris is the capital of France.")
    assert len(claims) > 0

    sources = monitor.require_source_attribution("Paris is the capital. [Source: Wiki]")
    assert sources["must_add_sources"] is False

def test_factual_verifier():
    verifier = FactualVerifier()
    res = verifier.verify_with_web_search("The capital of France is Paris")
    assert res["is_verified"] is True

    math_res = verifier.verify_math("2 + 2", "4")
    assert math_res["is_verified"] is True

    math_res2 = verifier.verify_math("2 + 2", "5")
    assert math_res2["is_verified"] is False

    # Test symbolic equation verification with Sympy
    symbolic_res = verifier.verify_math("x + x", "2*x")
    assert symbolic_res["is_verified"] is True
    assert symbolic_res.get("expression_sympy") == "2*x"

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

    # MultiAICodeGenerator test
    consensus_res = validator.multi_generator.generate_with_consensus(
        "Generate a simple function",
        "def foo():\n    return 1",
        "def foo():\n    return 1",
        "def foo():\n    return 2"
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

    db.log_ai_mistake({
        "model": "Kimi",
        "type": "indentation",
        "task": "writing validator",
        "original": "def x():\n  pass",
        "correct": "def x():\n    pass",
        "root_cause": "nested block",
        "prevention": "run ast validation"
    })
    strategy = db.get_prevention_strategy("Kimi", "writing validator")
    assert strategy == "run ast validation"
    
    # Cleanup test db
    if os.path.exists("test_patterns.db"):
        os.remove("test_patterns.db")


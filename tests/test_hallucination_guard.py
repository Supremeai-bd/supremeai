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

def test_code_validator():
    validator = CodeValidator()
    res = validator.validate_syntax("def foo():\n    pass", "python")
    assert res["is_valid"] is True

    res2 = validator.validate_syntax("def foo(\n    pass", "python")
    assert res2["is_valid"] is False

    url_res = validator.validate_url("https://github.com/nadim9/supremeai.git")
    assert url_res["is_valid"] is False

def test_output_validator():
    validator = OutputValidator()
    res = validator.validate("Repository: https://github.com/nadim9/supremeai.git")
    assert res["is_valid"] is False
    assert res["confidence"]["badge"] == "LOW_CONFIDENCE"

def test_error_pattern_db():
    db = ErrorPatternDB("test_patterns.db")
    db.log_error("nadim9/supremeai", "hallucination", "paykaribazaronline/supremeai")
    pattern = db.check_pattern("This is a repo: nadim9/supremeai")
    assert pattern["should_prevent"] is True
    
    # Cleanup test db
    if os.path.exists("test_patterns.db"):
        os.remove("test_patterns.db")

"""Tests for Intelligent Decision Engine modules (issue #1018).

Tests the 3 new modules:
  - intent_extractor.py (Phase 2)
  - fixability_scorer.py (Phase 3)
  - auto_fix_engine.py (Phase 4)

And the failure taxonomy in delta_analysis.py (Phase 1).
"""

import json
import sys
from pathlib import Path

import pytest

# Add scripts to path — file is at backend/tests/ci/pr_helper/, so repo root
# is parents[4] (pr_helper → ci → tests → backend → repo root).
SCRIPTS_DIR = Path(__file__).resolve().parents[4] / ".github" / "scripts" / "pr_helper"
sys.path.insert(0, str(SCRIPTS_DIR))

from delta_analysis import _classify_failure_type, _enrich_failure
from fixability_scorer import score_failure
from intent_extractor import extract_intention


class TestFailureTaxonomy:
    """Phase 1: _classify_failure_type correctly identifies failure types."""

    def test_import_error(self):
        ftype = _classify_failure_type("ModuleNotFoundError: No module named 'xyz'", "")
        assert ftype == "import_error"

    def test_import_error_cannot_import(self):
        ftype = _classify_failure_type("", "ImportError: cannot import name 'X' from 'core.y'")
        assert ftype == "import_error"

    def test_assertion_mismatch(self):
        ftype = _classify_failure_type("AssertionError: assert result == 'strict_fail'", "")
        assert ftype == "assertion_mismatch"

    def test_type_error(self):
        ftype = _classify_failure_type("TypeError: got an unexpected keyword argument 'X'", "")
        assert ftype == "type_error"

    def test_key_error(self):
        ftype = _classify_failure_type("KeyError: 'format'", "")
        assert ftype == "key_error"

    def test_connection_error(self):
        ftype = _classify_failure_type("ConnectionRefusedError: connection refused", "")
        assert ftype == "connection_error"

    def test_syntax_error(self):
        ftype = _classify_failure_type("SyntaxError: invalid syntax", "")
        assert ftype == "syntax_error"

    def test_unknown(self):
        ftype = _classify_failure_type("Some random error message", "")
        assert ftype == "unknown"

    def test_enrich_adds_type(self):
        failure = {"snippet": "ImportError: cannot import name 'X'", "message": ""}
        enriched = _enrich_failure(failure)
        assert enriched["failure_type"] == "import_error"
        assert enriched["beneficial_probability"] == 0.85
        assert enriched["auto_fix_strategy"] == "update_test_import_path"


class TestIntentExtractor:
    """Phase 2: extract_intention correctly identifies PR intention."""

    def test_secret_handling(self):
        result = extract_intention(
            pr_title="fix(core): DATABASE_URL graceful degradation",
            changed_files="backend/core/security/secret_vault.py,backend/core/config_secrets.py",
        )
        assert result["intention"] == "change_secret_handling"
        assert result["confidence"] > 0

    def test_add_feature(self):
        result = extract_intention(
            pr_title="feat(api): add user settings endpoint",
            changed_files="backend/api/routes/settings.py",
        )
        assert result["intention"] == "add_feature"

    def test_fix_bug(self):
        result = extract_intention(
            pr_title="fix(core): circuit breaker timeout",
            changed_files="backend/core/resilience/circuit_breaker.py",
        )
        assert result["intention"] == "fix_bug"

    def test_refactor(self):
        result = extract_intention(
            pr_title="refactor(core): move LLM gateway imports",
            changed_files="backend/core/llm/llm_gateway/__init__.py",
        )
        assert result["intention"] == "refactor"

    def test_docs_only(self):
        result = extract_intention(
            pr_title="docs: update README",
            changed_files="README.md,docs/plans/plan.md",
        )
        assert result["intention"] == "docs_only"

    def test_unknown_intention(self):
        result = extract_intention(
            pr_title="wip: experimenting",
            changed_files="experimental.py",
        )
        assert result["intention"] in ("unknown", "ci_improvement", "refactor")


class TestFixabilityScorer:
    """Phase 3: score_failure correctly calculates fixability."""

    def test_import_error_high_score(self):
        failure = {
            "id": "tests.test_x::test_y",
            "class": "test_x",
            "test": "test_y",
            "kind": "error",
            "message": "ImportError: cannot import name 'X' from 'core.y'",
            "snippet": "ModuleNotFoundError: No module named 'core.y'",
            "failure_type": "import_error",
            "beneficial_probability": 0.85,
            "auto_fix_strategy": "update_test_import_path",
        }
        intention = {"intention": "refactor", "confidence": 0.8}
        rec = score_failure(
            failure,
            intention,
            ["backend/tests/test_x.py", "backend/core/y.py"],
            "refactor: move imports",
        )
        assert rec["score"] >= 70
        assert rec["verdict"] == "auto_fix"

    def test_syntax_error_low_score(self):
        failure = {
            "id": "tests.test_x::test_z",
            "class": "tests.test_x",
            "test": "test_z",
            "kind": "failure",
            "message": "SyntaxError: invalid syntax",
            "snippet": "SyntaxError: invalid syntax",
            "failure_type": "syntax_error",
            "beneficial_probability": 0.05,
            "auto_fix_strategy": None,
        }
        intention = {"intention": "unknown", "confidence": 0.0}
        rec = score_failure(failure, intention, [], "")
        assert rec["score"] <= 10
        assert rec["verdict"] == "block"

    def test_assertion_with_intention_match(self):
        failure = {
            "id": "tests.test_vault::test_fail_closed",
            "class": "test_vault",
            "test": "test_fail_closed",
            "kind": "failure",
            "message": "AssertionError: assert 'strict_fail' == 'graceful_degradation'",
            "snippet": "assert result == 'strict_fail'",
            "failure_type": "assertion_mismatch",
            "beneficial_probability": 0.50,
            "auto_fix_strategy": "compare_expected_vs_actual_semantically",
        }
        intention = {"intention": "change_secret_handling", "confidence": 0.9}
        rec = score_failure(
            failure,
            intention,
            ["backend/tests/test_vault.py", "backend/core/security/secret_vault.py"],
            "fix(core): graceful degradation",
        )
        assert rec["score"] >= 70
        assert rec["verdict"] == "auto_fix"
        assert rec["intention_match"] is True

    def test_connection_error_auto_skip(self):
        failure = {
            "id": "tests.test_x::test_conn",
            "class": "tests.test_x",
            "test": "test_conn",
            "kind": "error",
            "message": "ConnectionRefusedError",
            "snippet": "Connection refused",
            "failure_type": "connection_error",
            "beneficial_probability": 0.90,
            "auto_fix_strategy": "skip_as_env_issue",
        }
        intention = {"intention": "unknown", "confidence": 0.0}
        rec = score_failure(failure, intention, [], "")
        assert rec["score"] >= 30  # 0.90 * 40 = 36, but other factors may reduce
        assert rec["verdict"] in ("auto_fix", "human_review", "block")

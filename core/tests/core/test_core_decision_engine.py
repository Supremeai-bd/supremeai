# tests/test_core_decision_engine.py
"""Tests for the core DecisionEngine (autonomous operation routing)."""

import os
from unittest.mock import patch

import pytest

from core.decision_engine import DecisionEngine


def test_init_default_min_confidence():
    with patch.dict(os.environ, {}, clear=True):
        eng = DecisionEngine()
        assert eng._min_confidence == 0.6


def test_init_min_confidence_from_env():
    with patch.dict(os.environ, {"DECISION_MIN_CONFIDENCE": "0.8"}):
        eng = DecisionEngine()
        assert eng._min_confidence == 0.8


async def test_decide_block_on_sandbox_failure():
    eng = DecisionEngine()
    decision = await eng.decide({"sandbox_passed": False})
    assert decision["action"] == "block"
    assert decision["confidence"] == 1.0
    assert decision["reason"] == "sandbox_failed"


async def test_decide_review_on_risk_flags():
    eng = DecisionEngine()
    decision = await eng.decide({"risk_flags": ["sql_injection"]})
    assert decision["action"] == "review"
    assert decision["confidence"] == 0.5
    assert decision["reason"] == "risk_flags"


async def test_decide_review_on_low_confidence():
    eng = DecisionEngine()
    decision = await eng.decide({"recent_error_rate": 0.9})
    assert decision["action"] == "review"
    assert decision["confidence"] == pytest.approx(0.1)


async def test_decide_proceed_when_confident():
    eng = DecisionEngine()
    decision = await eng.decide({"recent_error_rate": 0.0})
    assert decision["action"] == "proceed"
    assert decision["confidence"] == pytest.approx(1.0)


async def test_decide_caches_and_avoids_duplicate_history():
    eng = DecisionEngine()
    context = {"recent_error_rate": 0.0, "sandbox_passed": True}
    first = await eng.decide(context)
    second = await eng.decide(context)
    assert first["action"] == second["action"] == "proceed"
    # Cached decision should not append a second history entry.
    assert len(eng.decision_history) == 1


async def test_decide_combines_risk_flags_over_error_rate():
    eng = DecisionEngine()
    decision = await eng.decide({"risk_flags": ["x"], "recent_error_rate": 0.0})
    # Risk flags take precedence over error-rate confidence path.
    assert decision["action"] == "review"

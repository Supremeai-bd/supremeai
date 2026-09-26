"""Dynamic healing stats & predictions — acceptance tests for #1617.

Guarantees:
- zero hardcoded metric values (no fake 0.95 success_rate, no always-empty
  predictions) — every number derives from AutoHealer state
- endpoints reflect injected history / circuit-breaker state immediately
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.healing_stats import router
from services.auto_healer import (
    AutoHealer,
    FixResult,
    Issue,
    IssueCategory,
    Severity,
    get_healer,
)

import services.auto_healer as auto_healer_module


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def fresh_healer():
    """Route-এর ব্যবহৃত একই module identity-তে singleton swap — deterministic state।"""
    original = auto_healer_module._healer_instance
    auto_healer_module._healer_instance = AutoHealer()
    try:
        yield get_healer()
    finally:
        auto_healer_module._healer_instance = original


def _issue(category: IssueCategory, resolved: bool = False) -> Issue:
    return Issue(
        id=f"issue-{category.value}-{resolved}",
        category=category,
        severity=Severity.HIGH,
        title=f"synthetic {category.value} issue",
        description="created by healing-stats tests",
        source="tests",
        timestamp=datetime.now(),
        resolved=resolved,
    )


def test_stats_empty_history_is_dynamic_not_hardcoded(client, fresh_healer):
    resp = client.get("/healing/stats")
    assert resp.status_code == 200
    data = resp.json()
    # আগে এখানে ভুয়া 0.95 ছিল — এখন data না থাকলে None
    assert data["remedies_applied"] == 0
    assert data["success_rate"] is None
    assert data["success_rate"] != 0.95
    assert data["issues_detected"] == 0
    assert data["recent_issues"] == []


def test_stats_computed_from_real_fix_history(client, fresh_healer):
    healer = get_healer()
    healer.fix_history.extend(
        [
            FixResult(success=True, issue_id="i1", fix_applied="retry", message="ok"),
            FixResult(success=True, issue_id="i2", fix_applied="restart", message="ok"),
            FixResult(
                success=False, issue_id="i3", fix_applied="patch", message="failed"
            ),
        ]
    )
    resp = client.get("/healing/stats")
    data = resp.json()
    assert data["remedies_applied"] == 3
    assert data["successful_remedies"] == 2
    assert data["success_rate"] == round(2 / 3, 4)


def test_predictions_empty_when_no_signal(client, fresh_healer):
    resp = client.get("/health/predictions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["predictions"] == []
    assert data["status"] == "idle"


def test_predictions_from_unresolved_issue_categories(client, fresh_healer):
    healer = get_healer()
    healer.issue_history.extend(
        [
            _issue(IssueCategory.TIMEOUT),
            _issue(IssueCategory.TIMEOUT),
            _issue(IssueCategory.DATABASE),  # resolved নয় কিন্তু ভিন্ন category
        ]
    )
    resp = client.get("/health/predictions")
    data = resp.json()
    assert data["status"] == "active"
    rec = {p["risk"]: p for p in data["predictions"] if p["type"] == "issue_recurrence"}
    assert rec[IssueCategory.TIMEOUT.value]["probability"] == round(2 / 3, 4)
    assert "2 unresolved" in rec[IssueCategory.TIMEOUT.value]["basis"]


def test_predictions_from_open_circuit_breaker(client, fresh_healer):
    from core.resilience.circuit_breaker import CircuitBreakerState

    healer = get_healer()
    cb = healer.get_circuit_breaker("openai_api")
    cb.failure_count = cb.failure_threshold  # force OPEN condition
    cb.state = CircuitBreakerState.OPEN

    resp = client.get("/health/predictions")
    data = resp.json()
    cb_preds = [p for p in data["predictions"] if p["type"] == "circuit_breaker"]
    assert len(cb_preds) == 1
    assert cb_preds[0]["risk"] == "openai_api"
    assert "open" in cb_preds[0]["basis"]

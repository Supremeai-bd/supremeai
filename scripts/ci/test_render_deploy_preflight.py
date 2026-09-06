import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from render_deploy_preflight import account_config, usage_minutes


def test_usage_minutes_counts_current_month_deploys():
    now = datetime.now(timezone.utc)
    finished = now.isoformat().replace("+00:00", "Z")
    created = (now - timedelta(minutes=12)).isoformat().replace("+00:00", "Z")
    assert round(usage_minutes([{"deploy": {"createdAt": created, "finishedAt": finished}}]), 2) == 12.0


def test_usage_minutes_ignores_unfinished_deploys():
    assert usage_minutes([{"deploy": {"createdAt": "2026-01-01T00:00:00Z"}}]) == 0


def test_account_config_requires_explicit_json(monkeypatch):
    monkeypatch.setenv("RENDER_ACCOUNTS_JSON", '[{"role":"free","plan":"free"}]')
    assert account_config()[0]["plan"] == "free"


def test_account_config_rejects_invalid_json(monkeypatch):
    monkeypatch.setenv("RENDER_ACCOUNTS_JSON", "not-json")
    try:
        account_config()
    except RuntimeError as error:
        assert "invalid" in str(error)
    else:
        raise AssertionError("invalid account configuration must fail closed")


def test_account_config_handles_empty_or_unset_gracefully(monkeypatch):
    monkeypatch.setenv("RENDER_ACCOUNTS_JSON", "")
    monkeypatch.delenv("RENDER_PRIMARY_SVC_ID", raising=False)
    monkeypatch.delenv("RENDER_WORKER_SVC_ID", raising=False)
    monkeypatch.delenv("RENDER_SCRAPER_SVC_ID", raising=False)
    monkeypatch.delenv("RENDER_MCP_SVC_ID", raising=False)
    # When empty string and no svc IDs configured, returns empty list without crashing
    assert account_config() == []

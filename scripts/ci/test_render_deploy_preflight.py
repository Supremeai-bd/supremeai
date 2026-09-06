from datetime import datetime, timedelta, timezone

from render_deploy_preflight import account_config, usage_minutes


def test_usage_minutes_counts_current_month_deploys():
    now = datetime.now(timezone.utc)
    created = now.replace(hour=1, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
    finished = (now + timedelta(minutes=12)).isoformat().replace("+00:00", "Z")
    assert usage_minutes([{"deploy": {"createdAt": created, "finishedAt": finished}}]) == 12


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

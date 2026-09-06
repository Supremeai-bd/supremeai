from datetime import datetime, timedelta, timezone

from render_deploy_preflight import usage_minutes


def test_usage_minutes_counts_current_month_deploys():
    now = datetime.now(timezone.utc)
    created = now.replace(hour=1, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
    finished = (now + timedelta(minutes=12)).isoformat().replace("+00:00", "Z")
    assert usage_minutes([{"deploy": {"createdAt": created, "finishedAt": finished}}]) == 12


def test_usage_minutes_ignores_unfinished_deploys():
    assert usage_minutes([{"deploy": {"createdAt": "2026-01-01T00:00:00Z"}}]) == 0

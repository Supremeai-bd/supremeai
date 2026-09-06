import json
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


def test_main_allows_build_when_unconfigured_and_no_roles_required(monkeypatch, tmp_path):
    monkeypatch.setenv("RENDER_ACCOUNTS_JSON", "")
    monkeypatch.delenv("RENDER_PREFLIGHT_URL", raising=False)
    monkeypatch.delenv("RENDER_PRIMARY_SVC_ID", raising=False)
    monkeypatch.delenv("RENDER_WORKER_SVC_ID", raising=False)
    monkeypatch.delenv("RENDER_SCRAPER_SVC_ID", raising=False)
    monkeypatch.delenv("RENDER_MCP_SVC_ID", raising=False)
    monkeypatch.delenv("RENDER_REQUIRED_ROLES", raising=False)

    out_file = tmp_path / "github_output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))

    from render_deploy_preflight import main
    exit_code = main()
    assert exit_code == 0
    content = out_file.read_text(encoding="utf-8")
    assert "build_allowed=true" in content


def test_preflight_writes_structured_evidence(monkeypatch, tmp_path):
    inventory = tmp_path / "route_inventory.json"
    inventory.write_text(json.dumps({"route_count": 3, "source_sha256": "abc"}), encoding="utf-8")
    evidence = tmp_path / "evidence.json"
    monkeypatch.setenv("RENDER_ACCOUNTS_JSON", "")
    monkeypatch.delenv("RENDER_REQUIRED_ROLES", raising=False)
    monkeypatch.setenv("ROUTE_INVENTORY_PATH", str(inventory))
    monkeypatch.setenv("PREFLIGHT_EVIDENCE_PATH", str(evidence))
    monkeypatch.delenv("RENDER_PREFLIGHT_URL", raising=False)

    from render_deploy_preflight import main
    assert main() == 0
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["status"] == "ready"
    assert payload["route_inventory"]["status"] == "valid"
    assert payload["route_inventory"]["route_count"] == 3


def test_main_blocks_when_roles_required_but_no_accounts(monkeypatch, tmp_path):
    monkeypatch.setenv("RENDER_ACCOUNTS_JSON", "")
    monkeypatch.delenv("RENDER_PREFLIGHT_URL", raising=False)
    monkeypatch.delenv("RENDER_PRIMARY_SVC_ID", raising=False)
    monkeypatch.delenv("RENDER_WORKER_SVC_ID", raising=False)
    monkeypatch.delenv("RENDER_SCRAPER_SVC_ID", raising=False)
    monkeypatch.delenv("RENDER_MCP_SVC_ID", raising=False)
    monkeypatch.setenv("RENDER_REQUIRED_ROLES", "core,worker")

    out_file = tmp_path / "github_output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))

    from render_deploy_preflight import main
    exit_code = main()
    assert exit_code == 1
    content = out_file.read_text(encoding="utf-8")
    assert "build_allowed=false" in content


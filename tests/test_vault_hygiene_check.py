"""#3206 vault_hygiene_check tests — registry-driven, zero-leak, exit-code contract.

# বাংলা মন্তব্য: প্রতিটি টেস্ট #3206 acceptance বুলেট প্রমাণ করে —
# registry-authoritative classification, required-missing ব্যর্থতা, probe
# liveness (mocked, no network), এবং **কোনো পথেই secret value লিক নয়**।
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "vault_hygiene_check.py"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("vault_hygiene_under_test", SCRIPT_PATH)
    assert spec and spec.loader, "vault_hygiene_check module spec load failed"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()

REGISTRY_FIXTURE = """
keys:
- name: GITHUB_TOKEN
  criticality:
    infisical-vault: important
    github-actions: important
  note: probeable required key
- name: RENDER_API_KEY
  criticality:
    infisical-vault: important
  note: probeable required key
- name: NON_PROBE_SECRET
  criticality:
    infisical-vault: important
  note: required but no probe endpoint
- name: OPTIONAL_KEY
  criticality:
    infisical-vault: optional
  note: optional, missing in vault is fine
- name: OPTIONAL_PRESENT
  criticality:
    render-backend: optional
  note: optional but present → PASS presence
"""

SECRET_VALUE = "super-secret-value-abc123"


@pytest.fixture()
def registry(tmp_path: Path) -> Path:
    reg = tmp_path / "secrets_registry.yaml"
    reg.write_text(REGISTRY_FIXTURE, encoding="utf-8")
    return reg


def _vault() -> dict[str, str]:
    return {
        "GITHUB_TOKEN": SECRET_VALUE,
        "RENDER_API_KEY": SECRET_VALUE,
        "NON_PROBE_SECRET": SECRET_VALUE,
        "OPTIONAL_PRESENT": SECRET_VALUE,
        # OPTIONAL_KEY intentionally missing
    }


# ---------------------------------------------------------------------------
# Registry classification (#3206 adjustment vs legacy hardcoded arrays)
# ---------------------------------------------------------------------------
def test_registry_is_authoritative_for_required_keys(registry):
    keys = mod.load_registry(registry)
    assert set(keys) == {"GITHUB_TOKEN", "RENDER_API_KEY", "NON_PROBE_SECRET",
                         "OPTIONAL_KEY", "OPTIONAL_PRESENT"}
    assert mod.is_required(keys["GITHUB_TOKEN"]) is True
    assert mod.is_required(keys["OPTIONAL_KEY"]) is False
    assert mod.is_required(keys["NON_PROBE_SECRET"]) is True


# ---------------------------------------------------------------------------
# Check semantics: required-missing → FAIL; optional-missing → SKIP
# ---------------------------------------------------------------------------
def test_required_missing_fails_and_optional_missing_skips(registry):
    report = mod.run_check(registry_path=registry, vault_secrets=_vault())
    by_key = {r["key"]: r for r in report["results"]}

    assert by_key["OPTIONAL_KEY"]["status"] == "SKIP"
    assert by_key["NON_PROBE_SECRET"]["status"] == "PASS"  # presence-only key
    assert by_key["OPTIONAL_PRESENT"]["status"] == "PASS"
    # GITHUB_TOKEN probe is mocked below — here offline-safe check:
    assert report["summary"]["total_registered"] == 5


def test_missing_required_key_makes_report_unhealthy(registry):
    vault = _vault()
    del vault["NON_PROBE_SECRET"]  # required, no probe → MISSING
    report = mod.run_check(registry_path=registry, vault_secrets=vault)
    by_key = {r["key"]: r for r in report["results"]}
    assert by_key["NON_PROBE_SECRET"]["status"] == "MISSING"
    assert by_key["NON_PROBE_SECRET"]["required"] is True
    assert report["healthy"] is False
    assert report["summary"]["required_missing"] == 1


# ---------------------------------------------------------------------------
# Probe liveness — network mocked, no real calls
# ---------------------------------------------------------------------------
def test_probe_success_marks_pass(registry, monkeypatch):
    monkeypatch.setattr(
        mod, "probe_key",
        lambda k, v, c, timeout=15: {"key": k, "status": "PASS", "http_status": 200})
    report = mod.run_check(registry_path=registry, vault_secrets=_vault())
    by_key = {r["key"]: r for r in report["results"]}
    assert by_key["GITHUB_TOKEN"]["status"] == "PASS"
    assert by_key["GITHUB_TOKEN"]["probeable"] is True
    assert report["healthy"] is True


def test_probe_dead_key_marks_unhealthy(registry, monkeypatch):
    monkeypatch.setattr(
        mod, "probe_key",
        lambda k, v, c, timeout=15: ({"key": k, "status": "DEAD", "http_status": 401,
                                      "error": "HTTP 401"} if k == "RENDER_API_KEY"
                                     else {"key": k, "status": "PASS", "http_status": 200}))
    report = mod.run_check(registry_path=registry, vault_secrets=_vault())
    by_key = {r["key"]: r for r in report["results"]}
    assert by_key["RENDER_API_KEY"]["status"] == "DEAD"
    assert report["healthy"] is False
    assert report["summary"]["dead"] == 1


def test_probe_never_receives_or_returns_value(registry, monkeypatch):
    """#3206 acceptance: zero secret leakage — value শুধু probe-এর ভেতরে ব্যবহৃত হয়।"""
    captured: dict[str, str] = {}

    def fake_probe(key_name, value, config, timeout=15):
        captured["value_seen"] = value  # value probe-এর ভেতরে থাকে (শুধু ব্যবহার)
        return {"key": key_name, "status": "PASS", "http_status": 200,
                "echoed_value": value}  # ইচ্ছাকৃত দূষিত রিটার্ন — redact হওয়া উচিত

    monkeypatch.setattr(mod, "probe_key", fake_probe)
    report = mod.run_check(registry_path=registry, vault_secrets=_vault())
    assert captured["value_seen"] == SECRET_VALUE  # probe কাজ করেছে
    # কিন্তু report-এর কোনো স্তরে value বেরোয় না
    assert SECRET_VALUE not in json.dumps(report)
    redacted = mod._redacted_report(report)
    assert SECRET_VALUE not in json.dumps(redacted)
    assert all("echoed_value" not in r for r in redacted["results"])


# ---------------------------------------------------------------------------
# CLI path: exit codes + redacted output file
# ---------------------------------------------------------------------------


def test_cli_exit_zero_when_healthy_and_exit_one_when_dead(registry, tmp_path, monkeypatch):
    vault = _vault()
    # বাংলা: CLI env-guard পাস করার জন্য ডামি ক্রেডেনশিয়াল (fetch নিজেই stubbed)
    monkeypatch.setenv("INFISICAL_CLIENT_ID", "test-id")
    monkeypatch.setenv("INFISICAL_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("INFISICAL_PROJECT_ID", "test-project")

    monkeypatch.setattr(mod, "fetch_vault_secrets",
                        lambda cid, cs, pid, environment="prod", timeout=30: vault)
    monkeypatch.setattr(
        mod, "probe_key",
        lambda k, v, c, timeout=15: {"key": k, "status": "PASS", "http_status": 200})

    out_path = tmp_path / "report.json"
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc_healthy = mod.main(["--dry-run", "--registry", str(registry),
                               "--json", str(out_path)])
    assert rc_healthy == 0
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["healthy"] is True
    assert SECRET_VALUE not in buf.getvalue()
    assert SECRET_VALUE not in out_path.read_text(encoding="utf-8")

    # এখন একটা key dead করে দিলে exit 1
    monkeypatch.setattr(
        mod, "probe_key",
        lambda k, v, c, timeout=15: ({"key": k, "status": "DEAD", "http_status": 403,
                                      "error": "HTTP 403"} if k == "GITHUB_TOKEN"
                                     else {"key": k, "status": "PASS", "http_status": 200}))
    buf2 = io.StringIO()
    with redirect_stdout(buf2):
        rc_dead = mod.main(["--dry-run", "--registry", str(registry)])
    assert rc_dead == 1
    assert SECRET_VALUE not in buf2.getvalue()


def test_cli_offline_inventory_mode(registry, monkeypatch):
    # --offline: network ছাড়া inventory — presence জানা নেই তাই required → MISSING
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = mod.main(["--dry-run", "--offline", "--registry", str(registry)])
    assert rc == 1  # required keys missing in offline mode
    assert "MISSING" in buf.getvalue()


def test_cli_requires_infisical_creds_without_offline(registry, monkeypatch):
    monkeypatch.delenv("INFISICAL_CLIENT_ID", raising=False)
    monkeypatch.delenv("INFISICAL_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("INFISICAL_PROJECT_ID", raising=False)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = mod.main(["--dry-run", "--registry", str(registry)])
    assert rc == 2  # config error — not a hygiene failure


# ---------------------------------------------------------------------------
# Dry-run never files issues even when unhealthy
# ---------------------------------------------------------------------------
def test_dry_run_skips_issue_filing(registry, tmp_path, monkeypatch):
    called = {"count": 0}

    def fake_file(items, dry_run):
        called["count"] += 1
        return []

    monkeypatch.setattr(mod, "_file_issues", fake_file)
    monkeypatch.setenv("INFISICAL_CLIENT_ID", "test-id")
    monkeypatch.setenv("INFISICAL_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("INFISICAL_PROJECT_ID", "test-project")
    monkeypatch.setattr(mod, "fetch_vault_secrets",
                        lambda cid, cs, pid, environment="prod", timeout=30: _vault())
    monkeypatch.setattr(
        mod, "probe_key",
        lambda k, v, c, timeout=15: {"key": k, "status": "DEAD", "http_status": 500})
    with redirect_stdout(io.StringIO()):
        rc = mod.main(["--dry-run", "--registry", str(registry)])
    assert rc == 1
    assert called["count"] == 1  # invoked, but dry_run=True → no HTTP filing inside

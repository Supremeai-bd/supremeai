#!/usr/bin/env python3
"""The edge proxy must serve the Studio origin the registry declares.

Two bugs are pinned here, both found on 2026-11-20 while migrating off the
archived Vercel build:

1. `ORIGIN_HOST` in `wrangler.toml` was **never read** by

      infrastructure/cloudflare-studio-proxy/src/index.js

   The module used a hardcoded constant instead. Changing the var in the
   dashboard or in the toml therefore looked like a migration and did nothing —
   traffic kept going to `supremeai-studio.vercel.app`.

2. `config/service_registry.yaml` declared `frontend.production_url` as
   `https://studio.supremeai.lat`, which no longer resolves (DNS:
   getaddrinfo failed). Because `repo_paths.service_endpoint("frontend")` is
   what the CORS floor and the proxy read, the self-declared "canonical" origin
   was the one origin that could not answer.

These tests compare the three declaration points against each other, so no
single one can drift silently.
"""
from __future__ import annotations
import pytest

import sys
import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

PROXY_DIR = REPO_ROOT / "infrastructure" / "cloudflare-studio-proxy"
PROXY_SRC = PROXY_DIR / "src" / "index.js"
WRANGLER = PROXY_DIR / "wrangler.toml"

#: The retired host. It stays in the guard by name: this is a denylist of a
#: host that is known-dead, not a deployment pin.
DEAD_STUDIO_HOST = "studio.supremeai.lat"


def _registry_frontend_url() -> str:
    from repo_paths import service_endpoint

    return (service_endpoint("frontend", with_path=False) or "").rstrip("/")


def _wrangler_origin_host() -> str:
    return tomllib.loads(WRANGLER.read_text(encoding="utf-8"))["vars"]["ORIGIN_HOST"]


def test_registry_frontend_is_not_the_dead_host():
    """The whole point: the declaration must name a surface that resolves."""
    url = _registry_frontend_url()
    assert url, "registry declares no frontend origin"
    assert DEAD_STUDIO_HOST not in url, (
        f"frontend.production_url still points at the dead host {DEAD_STUDIO_HOST}: {url}"
    )


def test_edge_proxy_origin_matches_the_registry():
    """wrangler.toml and the registry must name the same Studio origin."""
    var = _wrangler_origin_host()
    url = _registry_frontend_url()
    assert url == f"https://{var}", (
        f"edge proxy serves {var!r} but the registry declares {url!r}"
    )


def test_proxy_default_origin_matches_the_registry():
    """The code fallback must agree too, or a var-less deploy drifts."""
    src = PROXY_SRC.read_text(encoding="utf-8")
    url = _registry_frontend_url()
    assert f'DEFAULT_ORIGIN = "{url}"' in src, (
        f"index.js fallback origin is not the registry origin {url!r}"
    )


def test_proxy_actually_reads_the_configured_var():
    """Regression: the var was declared but never read, so it did nothing."""
    src = PROXY_SRC.read_text(encoding="utf-8")
    assert "env?.ORIGIN_HOST" in src, "index.js no longer reads ORIGIN_HOST"

    # Check each handler on its own: a single ">= 2 occurrences" count passes
    # even when one of them stopped resolving, which is exactly the failure
    # being pinned (a partially dead var still looks wired).
    for name, marker in (
        ("fetch", "async fetch(request, env, ctx) {"),
        ("scheduled", "async scheduled(event, env, ctx) {"),
    ):
        assert marker in src, f"{name} handler is gone"
        body = src.split(marker, 1)[1][:400]
        assert "resolveOrigin(env)" in body, (
            f"{name}() does not resolve ORIGIN_HOST — it will use the fallback origin "
            "while the var quietly does nothing"
        )


def test_registry_file_still_parses():
    doc = yaml.safe_load(
        (REPO_ROOT / "config" / "service_registry.yaml").read_text(encoding="utf-8")
    )
    assert doc["services"]["frontend"]["production_url"]


def _health_module():
    """Load scripts/ops/master_health_check.py (dataclasses need sys.modules)."""
    import importlib.util

    path = REPO_ROOT / "scripts" / "ops" / "master_health_check.py"
    spec = importlib.util.spec_from_file_location("mhc_probe", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["mhc_probe"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_edge_dns_probe_is_derived_from_the_registry():
    """The DNS probe used to test two literals, and missed the live surface.

    `("supremeai.live", "studio.supremeai.lat")` were both DNS-dead on
    2026-11-20 while `supremeai-studio.pages.dev` — the origin actually serving
    the SPA — was never probed. A hardcoded probe list can only test yesterday's
    deployment.
    """
    module = _health_module()
    domains = module._edge_domains()

    frontend_host = _registry_frontend_url().split("://", 1)[-1].split("/", 1)[0]
    assert frontend_host in domains, (
        f"the live Studio host {frontend_host} is not DNS-probed; probe covers {domains}"
    )
    assert all("://" not in d for d in domains), f"expected bare hostnames, got {domains}"


def test_edge_dns_probe_list_is_not_hardcoded():
    src = (REPO_ROOT / "scripts" / "ops" / "master_health_check.py").read_text(encoding="utf-8")
    assert 'for domain in ("supremeai.live", "studio.supremeai.lat")' not in src, (
        "the hardcoded edge-domain tuple is back"
    )


def test_pipeline_health_snapshot_uses_contracts_and_sanitizes_evidence(monkeypatch, tmp_path):
    import json

    module = _health_module()
    base = "https://example.invalid"
    registry = {
        "api": {"production_url": base, "health_path": "/live", "readiness_path": "/ready"},
        "mcp": {"production_url": base, "health_path": "/health"},
        "new-service": {"production_url": base, "health_path": "/new"},
        "missing": {}, "inactive": {"status": "retired", "production_url": base},
    }
    checked = "2026-11-20T10:00:00Z"
    payloads = {
        "/ready": (False, 503, 6, None, "private error"),
        "/health": (True, 200, 1, {"status": "ok", "stale": True}, None),
        "/new": (True, 200, 3, {"status": "healthy", "debug": "private data"}, None),
        "/health/summary": (True, 200, 1, {"services": [
            {"provider": "redis", "status": "degraded", "checkedAt": checked, "token": "private token"}
        ]}, None),
    }
    monkeypatch.setattr(module, "_registry_services", lambda: registry)
    monkeypatch.setattr(module, "probe_http_endpoint", lambda url, timeout: payloads[url.removeprefix(base)])
    monkeypatch.setattr(module, "_get_gh_token", lambda: pytest.fail("snapshot must not request credentials"))
    output = tmp_path / "report.json"
    assert module.main(["--pipeline-snapshot", str(output)]) == 0
    report = json.loads(output.read_text())
    assert {r["service"]: r["status"] for r in report["services"]} == {
        "api": "HTTP failure", "mcp": "stale", "new-service": "healthy",
        "missing": "not configured", "inactive": "retired",
    }
    assert report["providers"] == [{"provider": "redis", "reported_status": "degraded",
                                    "checked_at": "2026-11-20T10:00:00+00:00"}]
    assert "private" not in output.read_text()
    assert "1/3 probed endpoints reported healthy" in module.pipeline_markdown(report)


def test_pipeline_snapshot_never_turns_no_evidence_green(monkeypatch):
    module = _health_module()
    monkeypatch.setattr(module, "_registry_services", lambda: {})
    with pytest.raises(ValueError, match="no health evidence"):
        module.pipeline_snapshot(1)
    monkeypatch.setattr(module, "_registry_services", lambda: {
        "mcp": {"production_url": "https://example.invalid", "health_path": "/health"}})
    monkeypatch.setattr(module, "probe_http_endpoint", lambda url, timeout: (True, 200, 1, None, None))
    report = module.pipeline_snapshot(1)
    assert report["services"][0]["status"] == report["tower_summary"] == "unknown response"
    assert report["providers"] == []


def test_quick_liveness_only_calls_the_two_cheap_routes(monkeypatch, capsys):
    module = _health_module()
    registry = module._registry_services()
    responses = {
        registry['api']['production_url'] + '/healthz': (False, 503, 2, None, None),
        registry['mcp']['production_url'] + '/health/live': (True, 200, 1, {'status': 'ok'}, None),
    }
    monkeypatch.setattr(module, 'probe_http_endpoint', lambda url, timeout: responses.pop(url))
    assert module.main(['--quick-liveness']) == 0  # advisory, not a release gate
    assert not responses
    summary = capsys.readouterr().out
    assert '1/2 probed endpoints reported healthy' in summary and '503' in summary
    assert '### Provider dependencies' not in summary


def test_full_health_belongs_to_the_daily_arm_not_unified():
    workflows = REPO_ROOT / '.github/workflows'
    daily = yaml.safe_load((workflows / 'ops-maintenance.yml').read_text())['jobs']['daily-10am-bdt-health-report']
    quick = yaml.safe_load((workflows / 'unified-pipeline.yml').read_text())['jobs']['service-health']
    assert "github.event.schedule == '0 3 * * *'" in daily['if']
    assert any('--pipeline-snapshot' in step.get('run', '') for step in daily['steps'])
    assert any('--quick-liveness' in step.get('run', '') for step in quick['steps'])
    assert not any('--pipeline-snapshot' in step.get('run', '') for step in quick['steps'])

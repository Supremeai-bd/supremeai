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

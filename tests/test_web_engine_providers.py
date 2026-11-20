"""The pool and the relay must agree about web-engine provider names.

The defect these tests exist for (found 2026-11-19): the dual-pool router has
always declared web models whose keys are cookies and webhook URLs
(`claude_web`, `chatgpt_web`, `gemini_v0_web`), and `browser/server.py` has
always served them on `/v1/chat/completions`. But those provider names were
absent from `PROVIDER_CONFIGS`, so every such request ended in
`400 Unknown provider`, and absent from `FederationSquad.PREFIX_MAP`, so the
serving arbiter never discovered their credential slots. Declared capacity was
unreachable, and nothing failed loudly — the models simply never appeared.

Properties pinned here:

* every provider the pool mentions resolves in the adapter (the regression);
* web engines are *fallback-only* — ranked after every keyed provider;
* the relay URL normalizes from any operator spelling to a base the adapter can
  append `/chat/completions` to;
* **approval is untouched**: a web engine with no signed route yields no
  candidates. Wiring a surface must never be the same thing as approving it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from gateway.service.pool import PROVIDER_BASELINE_LATENCY_MS, FederationSquad
from gateway.service.providers import web_engines
from gateway.service.providers.adapters import (
    PROVIDER_CONFIGS,
    eligible_chat_models,
)

ROUTER_SOURCE = REPO_ROOT / "gateway" / "dual_pool_priority_router.py"


def _providers_declared_by_the_router() -> set[str]:
    """Provider names the dual pool builds, read from source (no import)."""
    return set(re.findall(r'provider="([a-z0-9_]+)"', ROUTER_SOURCE.read_text(encoding="utf-8")))


def test_the_router_declares_web_providers_at_all():
    declared = _providers_declared_by_the_router()
    assert {"claude_web", "chatgpt_web", "gemini_v0_web"} <= declared, (
        "if the router stopped declaring web models, this suite's premise changed"
    )


def test_every_provider_the_router_declares_resolves_in_the_adapter():
    """The regression: a declared provider that the adapter does not know.

    Two names are exempt because they describe a *combination* of providers
    ("groq or cerebras"), not an API — see `TELEMETRY_ONLY_PROVIDERS`. The set is
    asserted exactly, so a third exemption cannot be smuggled in silently.
    """
    unresolved = sorted(
        name
        for name in _providers_declared_by_the_router()
        if name not in PROVIDER_CONFIGS and name not in web_engines.TELEMETRY_ONLY_PROVIDERS
    )
    assert not unresolved, (
        f"{unresolved} are declared by the dual-pool router but missing from "
        "PROVIDER_CONFIGS, so forward_chat_completion answers 400 Unknown provider "
        "for them. Register them in gateway/service/providers/web_engines.py."
    )


def test_telemetry_only_providers_are_recorded_and_never_routable():
    assert web_engines.TELEMETRY_ONLY_PROVIDERS == {"groq_cerebras", "openrouter_kilo"}, (
        "a new telemetry-only alias means a pool entry that can never be "
        "dispatched; add it here deliberately with a reason"
    )
    for name in web_engines.TELEMETRY_ONLY_PROVIDERS:
        assert name not in FederationSquad.PREFIX_MAP, (
            f"{name} is a provider combination, not an API — discovering keys for "
            "it would let the arbiter dispatch to a name the adapter cannot resolve"
        )


def test_every_web_engine_has_an_adapter_config_and_a_credential_source():
    for engine in web_engines.WEB_ENGINES:
        config = PROVIDER_CONFIGS.get(engine.provider)
        assert config, f"{engine.provider} missing from PROVIDER_CONFIGS"
        assert config["base_url"].startswith(("http://", "https://"))
        assert config["default_model"] == engine.default_model
        assert FederationSquad.PREFIX_MAP.get(engine.provider), (
            f"{engine.provider} has no credential env names, so the arbiter's "
            "discovery pass can never produce a slot for it"
        )


def test_web_engines_are_discovered_but_ranked_last():
    order = list(FederationSquad.DEFAULT_PROVIDER_ORDER)
    web_names = [engine.provider for engine in web_engines.WEB_ENGINES]
    for name in web_names:
        assert name in order, f"{name} is not in the discovery set"
    first_web = min(order.index(name) for name in web_names)
    keyed_after = [p for p in order[first_web:] if p not in web_names]
    assert not keyed_after, (
        f"keyed providers {keyed_after} rank after web engines; a web engine costs "
        "a relay hop and a session that can expire, so it must only win when keyed "
        "capacity is gone"
    )


def test_every_discovered_provider_has_a_baseline_latency():
    missing = sorted(p for p in FederationSquad.PREFIX_MAP if p not in PROVIDER_BASELINE_LATENCY_MS)
    assert not missing, (
        f"{missing} fall back to the 500ms default, which silently out-ranks real "
        "providers on latency instead of failing honestly"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://127.0.0.1:8788", "http://127.0.0.1:8788"),
        ("http://127.0.0.1:8788/", "http://127.0.0.1:8788"),
        ("https://relay.example.com/v1", "https://relay.example.com/v1"),
        ("https://relay.example.com/v1/chat/completions", "https://relay.example.com"),
        ("https://relay.example.com/chat/completions", "https://relay.example.com"),
        ('"https://relay.example.com"', "https://relay.example.com"),
        ("https://https://relay.example.com", "https://relay.example.com"),
        ("relay.example.com", "https://relay.example.com"),
        ("localhost:8788", "http://localhost:8788"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_relay_url_normalization(raw, expected):
    assert web_engines.normalize_web_base_url(raw) == expected


def test_relay_url_prefers_the_registry_alias_then_localhost():
    assert web_engines.relay_base_url({"STEALTH_WEBHOOK_URL": "https://relay.example.com/v1"}) == (
        "https://relay.example.com/v1"
    )
    assert web_engines.relay_base_url({}) == web_engines.DEFAULT_RELAY_BASE_URL


def test_wiring_a_web_engine_does_not_approve_it(monkeypatch):
    """No signed route ⇒ no candidates, exactly like any other provider."""
    monkeypatch.delenv("SUPREMEAI_FREE_ROUTE_POLICY", raising=False)
    for engine in web_engines.WEB_ENGINES:
        assert eligible_chat_models(engine.provider, "cookie-or-webhook") == ()


def test_cookie_backed_engines_are_named_for_the_health_probe():
    """Session-liveness work needs to know which surfaces can die silently."""
    assert set(web_engines.engines_requiring_cookie()) == {
        "gemini_v0_web",
        "ghost_gemini",
    }


# --- B6: the transport must name itself ------------------------------------
# `relay_base_url()` walked a five-name precedence list and returned the first
# value that looked non-empty. Nothing could distinguish a deliberate
# `STEALTH_WEBHOOK_URL` from the localhost default, and an env var pointing at
# `/health` (a copy-paste accident that answers 200 on a curl) resolved happily
# and then 404'd every chat request. The tests below pin the replacement: every
# resolution names its env var, and values that cannot be a base URL are
# rejected *with a reason* instead of being used.


def test_the_transport_names_the_env_var_it_came_from():
    transport = web_engines.transport_for("claude_web", {"STEALTH_WEBHOOK_URL": "relay.example.com"})
    assert transport is not None
    assert transport.kind == web_engines.TRANSPORT_RELAY
    assert transport.base_url == "https://relay.example.com"
    assert transport.source_env == "STEALTH_WEBHOOK_URL"
    assert transport.configured is True


def test_precedence_is_first_configured_and_says_which():
    transport, rejected = web_engines.resolve_transport(
        {"WEB_SESSION_URL": "https://session.example.com", "STEALTH_WEBHOOK_URL": "https://relay.example.com"}
    )
    assert transport.source_env == "WEB_SESSION_URL"
    assert rejected == {}, "a usable value must not be reported as rejected"


def test_nothing_configured_is_named_as_the_localhost_default():
    transport, rejected = web_engines.resolve_transport({})
    assert transport.base_url == web_engines.DEFAULT_RELAY_BASE_URL
    assert transport.source_env == ""
    assert transport.configured is False, "a localhost default must not look configured"
    assert rejected == {}


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("https://relay.example.com/health", "/health endpoint"),
        ("https://relay.example.com/models/", "/models endpoint"),
        ("ftp://relay.example.com", "scheme must be http or https"),
    ],
)
def test_an_unusable_env_is_rejected_with_a_reason_and_skipped(raw, reason):
    """The bad value must not win, and the operator must be told why it lost."""
    transport, rejected = web_engines.resolve_transport(
        {"GHOST_TOWER_URL": raw, "STEALTH_WEBHOOK_URL": "https://good.example.com"}
    )
    assert transport.base_url == "https://good.example.com", "a broken high-priority env won"
    assert transport.source_env == "STEALTH_WEBHOOK_URL"
    assert reason in rejected["GHOST_TOWER_URL"]


def test_a_rejected_env_with_no_fallback_still_names_itself():
    transport, rejected = web_engines.resolve_transport({"GHOST_TOWER_URL": "https://relay.example.com/health"})
    assert transport.base_url == web_engines.DEFAULT_RELAY_BASE_URL
    assert transport.configured is False
    assert "GHOST_TOWER_URL" in rejected


def test_transport_report_lists_every_engine_and_its_providers():
    report = web_engines.transport_report({"STEALTH_WEBHOOK_URL": "https://relay.example.com"})
    assert report["source_env"] == "STEALTH_WEBHOOK_URL"
    assert report["configured"] is True
    assert report["rejected_envs"] == {}
    assert set(report["engines"]) == {engine.engine for engine in web_engines.WEB_ENGINES}
    assert report["engines"]["duck"]["providers"] == ["claude_web", "chatgpt_web"]
    assert report["engines"]["gemini-web"]["requires_cookie"] is True
    assert report["engines"]["duck"]["requires_cookie"] is False


def test_every_web_provider_resolves_through_the_same_transport():
    """One answer, not two: `provider_config` may not compute its own base URL."""
    env = {"SUPREMEAI_WEB_RELAY_URL": "https://relay.example.com"}
    expected = web_engines.transport_for("chatgpt_web", env).base_url
    for engine in web_engines.WEB_ENGINES:
        assert web_engines.provider_config(engine.provider, env)["base_url"] == expected


def test_a_provider_that_is_not_a_web_engine_has_no_transport():
    assert web_engines.transport_for("openrouter", {}) is None
    assert web_engines.transport_for("openrouter_kilo", {}) is None

"""Web-engine providers: the pool's cookie/webhook slots, resolved to the relay.

Why this module exists
----------------------
Two halves of one feature were built years apart and never met:

* `gateway/dual_pool_priority_router.py` declares web models (`claude_web`,
  `chatgpt_web`, `gemini_v0_web`) whose `KeySlot`s are cookies and webhook URLs
  — its own docstring calls a slot "single API key **or webhook** credential".
* `browser/server.py` serves exactly those routes: `POST /v1/chat/completions`
  on port 8788, with `/health` and `/models` (per-engine live latency).

Neither half knew the other's names. The provider names were absent from
`PROVIDER_CONFIGS`, so `forward_chat_completion` answered `400 Unknown
provider` for every web slot, and they were absent from
`FederationSquad.PREFIX_MAP`, so the serving arbiter never discovered their
credential slots at all. The declared capacity was unreachable.

This module is the single mapping between the two. Anything that needs to know
a web engine's provider name, relay URL, default model or credential env names
reads it here — never a second copy, because a second copy is exactly how the
names drifted apart in the first place.

Deliberately stdlib-only: it is imported by the provider adapter layer, which
must stay importable in tests that install nothing beyond httpx.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

# Relay location, in priority order. `STEALTH_WEBHOOK_URL` is the name the
# service registry already publishes as a URL alias for the browser service
# (config/service_registry.yaml: url_aliases), so an operator who set only that
# still gets a working relay instead of a silent localhost fallback.
RELAY_BASE_URL_ENVS: tuple[str, ...] = (
    "GHOST_TOWER_URL",
    "WEB_SESSION_URL",
    "SUPREMEAI_WEB_RELAY_URL",
    "STEALTH_WEBHOOK_URL",
    "UPSTREAM_WEBHOOK_URL",
)
DEFAULT_RELAY_BASE_URL = "http://127.0.0.1:8788"

# Endpoint suffixes an operator may have pasted into the env var. The adapter
# appends `/chat/completions` itself, so a full endpoint must be reduced to its
# base or the request becomes `/chat/completions/chat/completions`.
# `/v1` is deliberately NOT stripped: the relay serves `/v1/chat/completions`,
# so a base that already ends in `/v1` must keep it, or the appended path lands
# on `/chat/completions` and 404s.
_ENDPOINT_SUFFIXES: tuple[str, ...] = (
    "/v1/chat/completions",
    "/chat/completions",
)

# Shared cookie bundle: renewing this one secret refreshes every cookie-backed
# web engine (same SSOT the dual pool reads through `_scan_web_keys`).
_FLEET_BUNDLE = "AI_FLEET_COOKIES_GZIP_B64"
# The relay URL doubles as a credential slot: a slot's mere presence means "this
# relay is configured", which is what the pool needs to have a candidate at all.
_RELAY_CREDENTIAL_ENVS: tuple[str, ...] = ("STEALTH_WEBHOOK_URL", "SUPREMEAI_WEB_RELAY_URL")


@dataclass(frozen=True)
class WebEngine:
    """One provider name the pool may route to, and the relay engine behind it.

    `engine` is the model id `browser/server.py` understands (`/models` reports
    `duck` and `gemini-web`); `default_model` is the slug sent upstream.
    """

    provider: str
    engine: str
    default_model: str
    capabilities: tuple[str, ...]
    requires_cookie: bool
    # Env names that make this provider routable at all, in priority order.
    credential_envs: tuple[str, ...]


WEB_ENGINES: tuple[WebEngine, ...] = (
    # Duck.ai is a keyless, cookieless hop. It is the safest web surface we
    # have: no account session to expire, so a failure is a plain upstream
    # error instead of a silently dead credential.
    WebEngine(
        provider="claude_web",
        engine="duck",
        default_model="duck-claude",
        capabilities=("reasoning", "general"),
        requires_cookie=False,
        credential_envs=_RELAY_CREDENTIAL_ENVS,
    ),
    WebEngine(
        provider="chatgpt_web",
        engine="duck",
        default_model="duck-gpt",
        capabilities=("general", "reasoning"),
        requires_cookie=False,
        credential_envs=_RELAY_CREDENTIAL_ENVS,
    ),
    # Cookie-backed engines: the relay restores the session from the vault.
    WebEngine(
        provider="gemini_v0_web",
        engine="gemini-web",
        default_model="gemini-web",
        capabilities=("general", "design"),
        requires_cookie=True,
        credential_envs=(_FLEET_BUNDLE, "SUPREMEAI_GEMINI_COOKIES", *_RELAY_CREDENTIAL_ENVS),
    ),
    # Pre-existing names, kept so their env overrides and approvals stay valid.
    WebEngine(
        provider="ghost_gemini",
        engine="gemini-web",
        default_model="gemini-web",
        capabilities=("general", "design"),
        requires_cookie=True,
        credential_envs=(_FLEET_BUNDLE, "SUPREMEAI_GEMINI_COOKIES", *_RELAY_CREDENTIAL_ENVS),
    ),
    WebEngine(
        provider="web_session",
        engine="gemini-web",
        default_model="web-session-auto",
        capabilities=("general",),
        requires_cookie=False,
        credential_envs=_RELAY_CREDENTIAL_ENVS,
    ),
)

WEB_ENGINES_BY_PROVIDER: dict[str, WebEngine] = {engine.provider: engine for engine in WEB_ENGINES}

# Names the telemetry router uses to describe a *combination* of providers:
# "groq or cerebras" and "openrouter or kilo". They are not APIs, so there is no
# base URL to resolve them to and nothing should ever dispatch to them — the
# dashboard ranks them, then the squad picks the concrete provider. Recorded
# here so the "every declared provider resolves" guard can stay strict: any new
# unresolvable name fails the suite instead of hiding in this set.
TELEMETRY_ONLY_PROVIDERS: frozenset[str] = frozenset({"groq_cerebras", "openrouter_kilo"})


def normalize_web_base_url(raw: str) -> str:
    """Reduce any operator spelling of the relay URL to a base the adapter can use.

    Accepts a bare host, a quoted env accident, a base with `/v1`, or a full
    `/v1/chat/completions` endpoint, and returns scheme + host + optional path
    with no trailing endpoint. Returns "" when nothing usable is configured, so
    callers can fall back explicitly rather than posting to a malformed URL.
    """
    value = (raw or "").strip()
    while len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
        value = value[1:-1].strip()
    value = "".join(value.split())
    if not value:
        return ""
    for doubled in ("https://https://", "https://http://", "http://https://", "http://http://"):
        if value.lower().startswith(doubled):
            value = value.split("://", 1)[1]
            break
    if "://" not in value:
        value = "https://" + value if not value.startswith("localhost") else "http://" + value
    base = value.split("?", 1)[0].rstrip("/")
    for suffix in _ENDPOINT_SUFFIXES:
        if base.lower().endswith(suffix):
            base = base[: -len(suffix)].rstrip("/")
            break
    return base


def relay_base_url(env: Mapping[str, str] | None = None) -> str:
    """First configured relay URL, normalized; localhost default only as a last resort."""
    source = os.environ if env is None else env
    for name in RELAY_BASE_URL_ENVS:
        candidate = normalize_web_base_url(source.get(name, ""))
        if candidate:
            return candidate
    return DEFAULT_RELAY_BASE_URL


def provider_config(provider: str, env: Mapping[str, str] | None = None) -> dict[str, str] | None:
    """`PROVIDER_CONFIGS`-shaped entry for a web engine, or None if unknown.

    The relay base URL is resolved once per call so an operator rotating
    `STEALTH_WEBHOOK_URL` between deployments does not need a code change.
    """
    engine = WEB_ENGINES_BY_PROVIDER.get(provider)
    if engine is None:
        return None
    return {"base_url": relay_base_url(env), "default_model": engine.default_model}


def provider_configs(env: Mapping[str, str] | None = None) -> dict[str, dict[str, str]]:
    """Every web engine as a `PROVIDER_CONFIGS` fragment (merged by the adapter)."""
    return {
        engine.provider: {
            "base_url": relay_base_url(env),
            "default_model": engine.default_model,
        }
        for engine in WEB_ENGINES
    }


def is_web_engine(provider: str) -> bool:
    return provider in WEB_ENGINES_BY_PROVIDER


def engines_requiring_cookie() -> tuple[str, ...]:
    """Providers whose failure mode is a dead session rather than an HTTP error."""
    return tuple(engine.provider for engine in WEB_ENGINES if engine.requires_cookie)

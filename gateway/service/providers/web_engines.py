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
from urllib.parse import urlsplit

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

# How a web engine is actually reached. One kind today; the shape exists so a
# second transport (a Chrome-extension bridge, say) is an added kind instead of
# a reshaped report that every dashboard has to relearn.
TRANSPORT_RELAY = "relay"

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
    return resolve_transport(env)[0].base_url


@dataclass(frozen=True)
class Transport:
    """Where a web engine's requests go — and which env var decided that.

    `source_env` being empty is the important case: it means nothing was
    configured and the built-in localhost default was used, which works on a
    developer laptop and fails everywhere else. Before this, nothing could tell
    a deliberate `STEALTH_WEBHOOK_URL` from that fallback, so a deploy with a
    misspelled env var looked identical to a working one right up until traffic.
    """

    kind: str
    base_url: str
    source_env: str

    @property
    def configured(self) -> bool:
        return bool(self.source_env)

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "base_url": self.base_url,
            "source_env": self.source_env,
            "configured": self.configured,
        }


def _unusable_reason(base: str) -> str:
    """Why a normalized base cannot carry requests ('' when it can)."""
    target = urlsplit(base)
    if target.scheme not in ("http", "https"):
        return f"scheme must be http or https, not {target.scheme or '<none>'}"
    if not target.hostname:
        return "no host"
    # A pasted read-only endpoint is the most common copy-paste accident: it
    # resolves, answers 200 on a curl, and then every chat request 404s.
    path = (target.path or "").rstrip("/").lower()
    for endpoint in ("/health", "/models"):
        if path.endswith(endpoint):
            return f"points at the {endpoint} endpoint, not the base URL"
    return ""


def resolve_transport(
    env: Mapping[str, str] | None = None,
) -> tuple[Transport, dict[str, str]]:
    """Resolve the relay transport, and report every env var that was rejected.

    The second half is the point. `relay_base_url()` silently walked the
    precedence list, so `GHOST_TOWER_URL=https://relay.example.com/health`
    (wrong path), `STEALTH_WEBHOOK_URL=relay.example.com:8788` (no scheme) or a
    leftover placeholder all resolved to *something* — usually the next env var
    down or localhost — and the resulting 404/DNS failure read as "the pool is
    broken" instead of "one env var is wrong". A rejected value is skipped (so
    a stale `GHOST_TOWER_URL` cannot beat a correct `STEALTH_WEBHOOK_URL`) but
    is now named with a reason, and `transport_report()` publishes it.
    """
    source = os.environ if env is None else env
    rejected: dict[str, str] = {}
    for name in RELAY_BASE_URL_ENVS:
        raw = (source.get(name) or "").strip()
        if not raw:
            continue
        candidate = normalize_web_base_url(raw)
        if not candidate:
            rejected[name] = "empty after normalization"
            continue
        reason = _unusable_reason(candidate)
        if reason:
            rejected[name] = reason
            continue
        return Transport(TRANSPORT_RELAY, candidate, name), rejected
    return Transport(TRANSPORT_RELAY, DEFAULT_RELAY_BASE_URL, ""), rejected


def transport_for(provider: str, env: Mapping[str, str] | None = None) -> Transport | None:
    """The transport a web provider dispatches over, or None if it is not one.

    Every caller that needs a web engine's base URL goes through here, so the
    answer always carries the env var it came from and no code path can resolve
    a base URL that nothing is willing to explain.
    """
    if provider not in WEB_ENGINES_BY_PROVIDER:
        return None
    return resolve_transport(env)[0]


def transport_report(env: Mapping[str, str] | None = None) -> dict[str, object]:
    """Operator-facing view: chosen transport, engines reached through it, rejects."""
    transport, rejected = resolve_transport(env)
    engines: dict[str, dict[str, object]] = {}
    for engine in WEB_ENGINES:
        row = engines.setdefault(
            engine.engine,
            {"engine": engine.engine, "providers": [], "requires_cookie": False},
        )
        row["providers"].append(engine.provider)  # type: ignore[union-attr]
        row["requires_cookie"] = bool(row["requires_cookie"] or engine.requires_cookie)
    return {**transport.as_dict(), "engines": engines, "rejected_envs": rejected}


def provider_config(provider: str, env: Mapping[str, str] | None = None) -> dict[str, str] | None:
    """`PROVIDER_CONFIGS`-shaped entry for a web engine, or None if unknown.

    The relay base URL is resolved once per call so an operator rotating
    `STEALTH_WEBHOOK_URL` between deployments does not need a code change.
    """
    engine = WEB_ENGINES_BY_PROVIDER.get(provider)
    transport = transport_for(provider, env)
    if engine is None or transport is None:
        return None
    return {"base_url": transport.base_url, "default_model": engine.default_model}


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

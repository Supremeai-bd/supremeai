"""SupremeAI Gateway — fail-closed configuration (issue #336).

Layer-2 unified provider gateway per api-schemas/gateway.openapi.yaml:
- One SUPREMEAI_API_KEY consumer credential (X-SupremeAI-Key header);
  provider credentials never leave the server side (OpenAPI §security).
- Routing policy is config-driven (``routing_policy.json``), validated
  fail-closed at startup: closed provider enum (the 7-provider SSOT from
  api-schemas/task-router.schema.json / provider-registry.schema.json),
  non-empty ordered chains, positive rate-limit numbers. Unknown providers,
  empty chains, or negative limits REJECT the config — the gateway refuses
  to boot on drift (fail-closed doctrine, mirrors #330's config gate).

Reference routing_policy.json format (documented, deterministic)::

    {
      "schema_version": "gateway-routing/1",
      "chains": {
        "auto":   [{"provider": "groq", "model": "llama-3.1-8b-instant"}, ...],
        "custom": [...]
      },
      "default_chain": "auto",
      "rate_limit": {"window_seconds": 60, "max_requests": 30},
      "api_keys": {
        "supremeai-key-...": {"owner": "dev", "scopes": ["chat", "models"]},
        "supremeai-key-...": {
          "owner": "client-1",
          "scopes": ["chat"],
          "env": "SUPREMEAI_API_KEY_CLIENT_1",        # optional: per-key secret
          "rate_limit": {"max_requests": 120}         # optional: per-key budget
        }
      }
    }

Secrets: api_keys values are loaded from the environment in production. The
variable name is ``env`` when declared, else ``SUPREMEAI_API_KEY_<OWNER>``; a
name claimed by two entries is a hard config error (the second key would
otherwise never load). This module never logs key material, and the JSON may
never carry a secret value — only the variable name.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Provider SSOT — closed enum byte-matched to api-schemas/task-router.schema.json
# (providerId pattern SSOT'd in provider-registry.schema.json), plus `web` for the
# cookie-relay provider that provider_chain has a real transport for.
# `perplexity`/`manus` were removed: they had no transport in provider_chain, so a
# chain could validate and then fail at request time (drift caught by
# gateway/tests/test_streaming_gateway.py::test_config_provider_enum_matches_task_router_ssot).
ALLOWED_PROVIDERS: frozenset[str] = frozenset(
    {
        "openai",
        "anthropic",
        "gemini",
        "groq",
        "openrouter",
        "mistral",
        "deepseek",
        "cerebras",
        "sambanova",
        "kilo",
        "cohere",
        "web",
    }
)

ALLOWED_SCOPES: frozenset[str] = frozenset({"chat", "models"})
CONFIG_SCHEMA_VERSION = "gateway-routing/1"


class ConfigError(ValueError):
    """Fail-closed config drift — the gateway refuses to boot."""


@dataclass(frozen=True, slots=True)
class Endpoint:
    """One routable model endpoint (mirrors task-router.schema.json ModelEndpoint)."""

    provider: str
    model: str


@dataclass(frozen=True, slots=True)
class ApiKeyRecord:
    """One client credential: who it is, what it may do, how much it may spend.

    `env` is the environment variable that carries the secret. Before it
    existed the name was derived from `owner` alone, so two keys with the same
    owner could never hold different secrets — which is exactly why a
    "give every client its own key" plan could not be expressed. `max_requests`
    / `window_seconds` override the global budget for this key's owner; `None`
    means "use the global rate_limit".
    """

    owner: str
    scopes: frozenset[str]
    env: str | None = None
    max_requests: int | None = None
    window_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class GatewayConfig:
    """Validated, immutable gateway configuration."""

    chains: dict[str, tuple[Endpoint, ...]]
    default_chain: str
    rate_limit_window_s: int
    rate_limit_max_requests: int
    api_keys: dict[str, ApiKeyRecord] = field(default_factory=dict)

    def chain_for(self, model: str) -> tuple[Endpoint, ...]:
        """Resolve the ordered chain for a requested model id.

        ``auto`` (OpenAPI default) resolves the configured default chain.
        A bare model name (e.g. ``gpt-4o-mini``) resolves to the first
        configured chain that contains an endpoint with that model, so
        clients can request a specific model without a dedicated chain name.
        Unknown model names are rejected here — routing never invents chains
        (fail-closed default per task-router doctrine).
        """
        if model == "auto":
            name = self.default_chain
        else:
            name = model if model in self.chains else None
            if name is None:
                # Resolve a bare model name to a chain prioritising that model.
                for endpoints in self.chains.values():
                    for idx, ep in enumerate(endpoints):
                        ep_bare = ep.model.split("/", 1)[-1] if "/" in ep.model else ep.model
                        if ep.model == model or ep_bare == model:
                            # Reorder: requested model first, then the rest.
                            reordered = (ep,) + endpoints[:idx] + endpoints[idx + 1 :]
                            return reordered
            if name is None:
                raise ConfigError(f"no routing chain configured for model '{model}'")
        chain = self.chains.get(name)
        if chain is None:
            raise ConfigError(f"no routing chain configured for model '{model}'")
        return chain


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def _parse_endpoint(raw: Any, where: str) -> Endpoint:
    _require(isinstance(raw, dict), f"{where}: endpoint must be an object")
    _require(
        set(raw) == {"provider", "model"},
        f"{where}: endpoint must have exactly provider+model",
    )
    provider, model = raw["provider"], raw["model"]
    _require(
        isinstance(provider, str) and provider in ALLOWED_PROVIDERS,
        f"{where}: provider '{provider}' not in closed enum {sorted(ALLOWED_PROVIDERS)}",
    )
    _require(
        isinstance(model, str)
        and 0 < len(model) <= 128
        and not any(c in model for c in " \t\r\n"),
        f"{where}: invalid model name",
    )
    return Endpoint(provider=provider, model=model)


def parse_routing_policy(
    raw: Any, *, env: dict[str, str] | None = None
) -> GatewayConfig:
    """Validate a routing policy dict fail-closed; returns the frozen config."""
    _require(isinstance(raw, dict), "routing policy must be a JSON object")
    _require(
        raw.get("schema_version") == CONFIG_SCHEMA_VERSION,
        f"schema_version must be exactly '{CONFIG_SCHEMA_VERSION}' (got {raw.get('schema_version')!r})",
    )

    chains_raw = raw.get("chains")
    _require(
        isinstance(chains_raw, dict) and chains_raw, "chains: non-empty object required"
    )
    chains: dict[str, tuple[Endpoint, ...]] = {}
    for name, chain_raw in chains_raw.items():
        _require(
            isinstance(name, str) and 0 < len(name) <= 64,
            f"chains: invalid chain name {name!r}",
        )
        _require(
            isinstance(chain_raw, list) and chain_raw,
            f"chains.{name}: non-empty ordered list required",
        )
        endpoints = tuple(
            _parse_endpoint(e, f"chains.{name}[{i}]") for i, e in enumerate(chain_raw)
        )
        chains[name] = endpoints

    default_chain = raw.get("default_chain", "auto")
    _require(
        isinstance(default_chain, str) and default_chain in chains,
        f"default_chain '{default_chain}' has no configured chain",
    )

    rl = raw.get("rate_limit", {"window_seconds": 60, "max_requests": 30})
    _require(isinstance(rl, dict), "rate_limit must be an object")
    window, max_req = rl.get("window_seconds"), rl.get("max_requests")
    _require(
        isinstance(window, int)
        and not isinstance(window, bool)
        and 0 < window <= 86400,
        "rate_limit.window_seconds must be an integer in (0, 86400]",
    )
    _require(
        isinstance(max_req, int)
        and not isinstance(max_req, bool)
        and 0 < max_req <= 100_000,
        "rate_limit.max_requests must be an integer in (0, 100000]",
    )

    api_keys_raw = raw.get("api_keys", {})
    _require(isinstance(api_keys_raw, dict), "api_keys must be an object")
    env = env if env is not None else dict(os.environ)
    api_keys: dict[str, ApiKeyRecord] = {}
    seen_env: dict[str, str] = {}
    for key_id, meta in api_keys_raw.items():
        # NOTE: ids deliberately avoid OpenAI/GitHub-shaped credential prefixes
        # bridge secret scan never mistakes reference ids for live credentials.
        _require(
            isinstance(key_id, str)
            and key_id.startswith("supremeai-key-")
            and len(key_id) >= 20,
            "api_keys: key ids must look like supremeai-key-<id> (>=20 chars)",
        )
        _require(
            isinstance(meta, dict) and {"owner", "scopes"} <= set(meta)
            and set(meta) <= {"owner", "scopes", "env", "rate_limit"},
            f"api_keys entry {key_id[:14]}…: allowed fields are "
            "owner, scopes, and optional env / rate_limit",
        )
        scopes_raw = meta["scopes"]
        _require(
            isinstance(scopes_raw, list)
            and scopes_raw
            and set(scopes_raw) <= set(ALLOWED_SCOPES),
            f"api_keys entry {key_id[:14]}…: scopes must be a non-empty subset of {sorted(ALLOWED_SCOPES)}",
        )
        rate_limit_meta = meta.get("rate_limit")
        key_max: int | None = None
        key_window: int | None = None
        if rate_limit_meta is not None:
            _require(
                isinstance(rate_limit_meta, dict)
                and set(rate_limit_meta) <= {"max_requests", "window_seconds"}
                and rate_limit_meta,
                f"api_keys entry {key_id[:14]}…: rate_limit takes max_requests "
                "and/or window_seconds",
            )
            for field_name in ("max_requests", "window_seconds"):
                value = rate_limit_meta.get(field_name)
                if value is None:
                    continue
                _require(
                    isinstance(value, int) and not isinstance(value, bool)
                    and 0 < value <= 100000,
                    f"api_keys entry {key_id[:14]}…: rate_limit.{field_name} must "
                    "be an integer in (0, 100000]",
                )
            key_max = rate_limit_meta.get("max_requests")
            key_window = rate_limit_meta.get("window_seconds")

        # Secret material: in production the VALUE rides the environment; a
        # literal value field in the JSON is rejected (never commit secrets).
        env_name = meta.get("env") or f"SUPREMEAI_API_KEY_{str(meta['owner']).upper().replace('-', '_')}"
        _require(
            isinstance(env_name, str)
            and re.fullmatch(r"SUPREMEAI_API_KEY_[A-Z0-9_]+", env_name) is not None,
            f"api_keys entry {key_id[:14]}…: env must look like SUPREMEAI_API_KEY_<NAME>",
        )
        if env_name in seen_env:
            raise ConfigError(
                f"api_keys: {env_name} is claimed by two entries "
                f"({seen_env[env_name][:14]}… and {key_id[:14]}…) — give each key "
                "its own `env`, otherwise the second one silently never loads"
            )
        seen_env[env_name] = key_id
        if env.get(env_name) is None:
            # Missing key material: skip entry; gateway runs guest-only.
            continue
        api_keys[key_id] = ApiKeyRecord(
            owner=str(meta["owner"]),
            scopes=frozenset(scopes_raw),
            env=env_name,
            max_requests=key_max,
            window_seconds=key_window,
        )

    return GatewayConfig(
        chains=chains,
        default_chain=default_chain,
        rate_limit_window_s=window,
        rate_limit_max_requests=max_req,
        api_keys=api_keys,
    )


def load_config(
    path: str | Path | None = None, *, env: dict[str, str] | None = None
) -> GatewayConfig:
    """Load + validate routing_policy.json (default path: gateway/routing_policy.json)."""
    p = Path(path) if path else Path(__file__).resolve().parent / "routing_policy.json"
    _require(p.is_file(), f"routing policy file not found: {p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"routing policy is not valid JSON: {exc}") from exc
    return parse_routing_policy(raw, env=env)


def canonical_fixture() -> dict:
    """The deterministic reference policy used by tests and the smoke suite."""
    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "chains": {
            "auto": [
                {"provider": "groq", "model": "llama-3.1-8b-instant"},
                {"provider": "openai", "model": "gpt-4o-mini"},
                {"provider": "anthropic", "model": "claude-sonnet-4-5"},
            ],
        },
        "default_chain": "auto",
        "rate_limit": {"window_seconds": 60, "max_requests": 4},
        "api_keys": {
            "supremeai-key-test-0000000001": {
                "owner": "pytest",
                "scopes": ["chat", "models"],
            },
            "supremeai-key-test-0000000002": {
                "owner": "readonly",
                "scopes": ["models"],
            },
        },
    }


def utc_ts() -> int:
    """Wall-clock seconds (rate-limit reset math only — never for digests)."""
    return int(time.time())

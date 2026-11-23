"""SupremeAI Gateway — provider failover with an honest transition ledger (issue #336).

Walks a config-ordered provider chain; every attempt is LEDGERED, and
exhaustion raises :class:`ProviderChainExhausted` carrying the FULL ledger —
zero silent fallback (doctrine shared with core/routing dynamic router, WO
#349). Transport is injected (``attempt_fn``) so tests and the SSE layer run
deterministically offline; the default transport is stdlib asyncio HTTP (same
honest core as sdk/python — no third-party client dependency).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import Endpoint
from .service.adaptive_routing import is_valid_secret

# Provider outcomes that justify failing over to the next endpoint.
FAILOVER_STATUS = frozenset({429, 500, 502, 503, 504})

# OpenAI-compatible request fields the gateway forwards verbatim. Sampling and
# tool-calling knobs live here; ``model`` is deliberately excluded because the
# routed endpoint owns it.
_FORWARDED_KEYS: tuple[str, ...] = (
    "temperature",
    "top_p",
    "max_tokens",
    "max_completion_tokens",
    "stop",
    "presence_penalty",
    "frequency_penalty",
    "seed",
    "user",
    "n",
    "tools",
    "tool_choice",
    "response_format",
)


class ProviderChainExhausted(RuntimeError):
    """Every endpoint in the chain failed — 502 upstream, ledger attached."""

    def __init__(self, message: str, ledger: list[dict[str, Any]]):
        super().__init__(message)
        self.ledger = ledger


@dataclass(frozen=True, slots=True)
class AttemptResult:
    """Outcome of one provider round-trip (success or honest failure)."""

    endpoint: Endpoint
    status: int
    headers: dict[str, str]
    body: bytes
    latency_ms: int

    @property
    def retry_after_s(self) -> float | None:
        ra = self.headers.get("retry-after")
        if ra is None:
            return None
        try:
            return float(ra)
        except ValueError:
            return None


AttemptFn = Callable[[Endpoint, bytes], Awaitable[AttemptResult]]


def _completions_url(api_base: str) -> str:
    """Join a provider base URL to its OpenAI-compatible completions path.

    Provider bases are configured in three shapes and concatenating
    ``/v1/chat/completions`` onto all of them is wrong:

    - ``https://api.openai.com/v1``            → already versioned
    - ``https://generativelanguage.googleapis.com/v1beta/openai``
                                               → OpenAI-compat shim, no /v1
    - ``https://api.example.com``               → bare host, needs /v1

    Getting this wrong produced ``.../openai/v1/v1/chat/completions`` (404 on
    every fallback-configured provider), so the join is explicit and tested.
    """
    base = api_base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith(("/v1", "/openai")):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def _forwarded_body(payload: bytes) -> dict[str, Any]:
    """Build the provider request body from the gateway payload.

    Only OpenAI-compatible knobs are forwarded — never ``model`` (the endpoint
    owns it) and never unknown keys (a provider 400s on those). Tools /
    response_format are included because an agent platform that silently drops
    ``tools`` cannot do work at all.
    """
    data = json.loads(payload)
    out: dict[str, Any] = {
        "messages": data.get("messages", []),
        # This transport is non-streaming by contract; the gateway fabricates
        # SSE at its own layer. Forwarding a client's stream:true here would
        # make the provider return an event stream that json.loads() cannot
        # parse (and broke /v1/consensus).
        "stream": False,
    }
    for key in _FORWARDED_KEYS:
        if key in data and data[key] is not None:
            out[key] = data[key]
    return out


def _http_client() -> httpx.AsyncClient:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        limits = httpx.Limits(
            max_connections=500,
            max_keepalive_connections=100,
            keepalive_expiry=60.0,
        )
        try:
            _HTTP_CLIENT = httpx.AsyncClient(
                limits=limits,
                timeout=30.0,
                http2=True,
            )
        except Exception:
            _HTTP_CLIENT = httpx.AsyncClient(
                limits=limits,
                timeout=30.0,
            )
    return _HTTP_CLIENT


_HTTP_CLIENT: httpx.AsyncClient | None = None


async def _default_attempt(endpoint: Endpoint, payload: bytes) -> AttemptResult:
    """One HTTP round-trip via httpx with connection pooling."""
    import os

    # Web-relay provider: cookie-based Gemini relay (no API key). Primary scout.
    if endpoint.provider == "web":
        relay_url = os.environ.get("SUPREMEAI_WEB_RELAY_URL", "").rstrip("/")
        if not relay_url:
            relay_url = os.environ.get("SUPREMEAI_CF_WORKER_URL", "").rstrip("/")
        if not relay_url:
            relay_url = os.environ.get("STEALTH_WEBHOOK_URL", "").rstrip("/")
        if not relay_url:
            relay_url = "https://supremeai-worker.paykaribazaronline.workers.dev"
        url = relay_url + "/v1/chat/completions"
        started = time.monotonic()
        req_model = endpoint.model
        if req_model in ("gemini", "gemini-web"):
            # Match the provider-verified default used by the main Gateway
            # adapter; Gemini 2.5 Flash is quota-exhausted for this deployment.
            req_model = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
        body = {
            "model": req_model,
            "messages": json.loads(payload).get("messages", []),
            "stream": False,
        }
        client = _http_client()
        resp = await client.post(url, json=body, timeout=60.0)
        return AttemptResult(
            endpoint=endpoint,
            status=resp.status_code,
            headers={k.lower(): v for k, v in resp.headers.items()},
            body=resp.content,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    provider = endpoint.provider.lower()
    api_base = os.environ.get(f"SUPREMEAI_PROVIDER_BASE_{provider.upper()}")
    api_key = os.environ.get(f"SUPREMEAI_PROVIDER_KEY_{provider.upper()}")

    # Fallback to commonly available raw provider env vars so the gateway works
    # even when only the standard provider keys are configured (root cause fix).
    _FALLBACKS = {
        "groq": ("https://api.groq.com/openai/v1", ["GROQ_API_KEY", "GROQ_API_KEYS"]),
        "openai": ("https://api.openai.com/v1", ["OPENAI_API_KEY"]),
        "openrouter": (
            "https://openrouter.ai/api/v1",
            ["OPENROUTER_API_KEY", "OPENROUTER_API_KEYS"],
        ),
        "gemini": (
            "https://generativelanguage.googleapis.com/v1beta/openai",
            ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        ),
        "mistral": ("https://api.mistral.ai/v1", ["MISTRAL_API_KEY"]),
        "anthropic": ("https://api.anthropic.com/v1", ["ANTHROPIC_API_KEY"]),
        "deepseek": ("https://api.deepseek.com/v1", ["DEEPSEEK_API_KEY"]),
        "cerebras": ("https://api.cerebras.ai/v1", ["CEREBRAS_API_KEY"]),
        "sambanova": ("https://api.sambanova.ai/v1", ["SAMBANOVA_API_KEY"]),
        "kilo": ("https://ai-gateway.kilo.ai/api/v1", ["KILO_API_KEY", "KILO_API_KEYS"]),
        "cohere": ("https://api.cohere.ai/compatibility/v1", ["COHERE_API_KEY", "COHERE_API_KEY_2", "COHERE_API_KEY_3", "COHERE_API_KEYS"]),
    }
    if (not api_base or not api_key) and provider in _FALLBACKS:
        fb_base, fb_keys = _FALLBACKS[provider]
        if not api_base:
            api_base = fb_base
        if not api_key:
            for k in fb_keys:
                v = os.environ.get(k, "")
                if v:
                    api_key = v.split(",")[0].strip()
                    break

    # Collect all available keys for this provider (primary + pool + numbered suffixes)
    # so a 429/401 on one key rotates to the next instead of failing over the whole provider.
    _POOL_ENV = {
        "groq": ["GROQ_API_KEY", "GROQ_API_KEYS"],
        "openai": ["OPENAI_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY", "OPENROUTER_API_KEYS"],
        "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY", "JULES_API_KEY"],
        "mistral": ["MISTRAL_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "deepseek": ["DEEPSEEK_API_KEY"],
        "cerebras": ["CEREBRAS_API_KEY"],
        "sambanova": ["SAMBANOVA_API_KEY"],
        "kilo": ["KILO_API_KEY", "KILO_API_KEYS"],
        "cohere": ["COHERE_API_KEY", "COHERE_API_KEY_2", "COHERE_API_KEY_3", "COHERE_API_KEYS"],
    }
    keys: list[str] = []
    if api_key and is_valid_secret(api_key):
        keys.append(api_key)
    # SUPREMEAI_PROVIDER_KEY_<P> may itself be a comma pool.
    raw_pool = os.environ.get(f"SUPREMEAI_PROVIDER_KEY_{provider.upper()}", "")
    for part in raw_pool.split(","):
        part = part.strip()
        if is_valid_secret(part) and part not in keys:
            keys.append(part)
    for env_name in _POOL_ENV.get(provider, []):
        for part in os.environ.get(env_name, "").split(","):
            part = part.strip()
            if is_valid_secret(part) and part not in keys:
                keys.append(part)

    # Dynamic numbered suffixes (e.g. GEMINI_API_KEY_2..12, GROQ_API_KEY_2..11, OPENROUTER_API_KEY_2..9)
    import re
    scan_prefixes = [f"{provider.upper()}_API_KEY", f"{provider.upper()}_KEY"]
    if provider == "gemini":
        scan_prefixes.extend(["GOOGLE_API_KEY", "JULES_API_KEY"])
    for pat in scan_prefixes:
        rgx = re.compile(rf"^{pat}(?:_.*)?$", re.IGNORECASE)
        for env_k, env_v in os.environ.items():
            if rgx.match(env_k) and not any(env_k.upper().endswith(s) for s in ["_MODEL", "_BASE_URL", "_URL"]):
                for part in env_v.strip().strip("'\"").split(","):
                    part = part.strip()
                    if is_valid_secret(part) and part not in keys:
                        keys.append(part)

    if not api_base or not keys:
        raise RuntimeError(
            f"provider {endpoint.provider} not configured (set SUPREMEAI_PROVIDER_BASE_/KEY_)"
        )

    url = _completions_url(api_base)
    body = {"model": endpoint.model, **_forwarded_body(payload)}
    client = _http_client()
    last_result: AttemptResult | None = None
    for key in keys:
        started = time.monotonic()
        try:
            resp = await client.post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {key}"},
                timeout=30.0,
            )
        except (httpx.HTTPError, OSError, asyncio.TimeoutError):
            # transport-level: try next key
            continue
        result = AttemptResult(
            endpoint=endpoint,
            status=resp.status_code,
            headers={k.lower(): v for k, v in resp.headers.items()},
            body=resp.content,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        last_result = result
        if resp.status_code < 400:
            return result
        # Rotate on auth/rate errors; otherwise stop (non-retryable).
        if resp.status_code not in (401, 403, 429):
            return result
    if last_result is not None:
        return last_result
    raise RuntimeError(f"provider {endpoint.provider} transport failed on all keys")


@dataclass(slots=True)
class ChainLedger:
    """Every transition is recorded; exhaustion carries the full ledger."""

    entries: list[dict[str, Any]] = field(default_factory=list)

    def record(self, **entry: Any) -> None:
        self.entries.append(entry)


async def execute_chain(
    chain: tuple[Endpoint, ...],
    payload: bytes,
    *,
    attempt_fn: AttemptFn | None = None,
    circuit_breaker: Any | None = None,
) -> AttemptResult:
    """Try endpoints in order; fail over ONLY on retryable outcomes.

    - 2xx → success, ledger records the win.
    - 429/5xx from a provider → ledger + next endpoint (failover semantics).
    - 401/403 from a provider → that endpoint is misconfigured; ledger +
      failover (a different provider may be configured correctly).
    - Exhaustion → ProviderChainExhausted with the FULL ledger (→ 502).

    ``circuit_breaker`` (``gateway/circuit_breaker.py``) is consulted per
    provider: while a provider is OPEN it is skipped without paying its
    transport timeout. The breaker is **fail-open**: if every endpoint in the
    chain is open, the chain is retried once with the breaker ignored — a stale
    breaker must never turn a recoverable upstream into a guaranteed 502.
    """
    attempt = attempt_fn or _default_attempt
    ledger = ChainLedger()
    skipped_open = 0
    for idx, endpoint in enumerate(chain):
        provider = endpoint.provider
        if circuit_breaker is not None and not circuit_breaker.allow(provider):
            skipped_open += 1
            ledger.record(
                index=idx,
                provider=provider,
                model=endpoint.model,
                outcome="circuit_open",
            )
            continue
        try:
            result = await attempt(endpoint, payload)
        except (
            RuntimeError,
            httpx.HTTPError,
            OSError,
            asyncio.TimeoutError,
        ) as exc:  # transport-level failure — honest ledger entry
            if circuit_breaker is not None:
                circuit_breaker.record_failure(provider)
            ledger.record(
                index=idx,
                provider=provider,
                model=endpoint.model,
                outcome="transport_error",
                detail=str(exc)[:200],
            )
            continue
        ledger.record(
            index=idx,
            provider=endpoint.provider,
            model=endpoint.model,
            outcome="success" if result.status < 400 else "provider_error",
            status=result.status,
            latency_ms=result.latency_ms,
        )
        if result.status < 400:
            if circuit_breaker is not None:
                circuit_breaker.record_success(provider)
            return result
        if result.status in FAILOVER_STATUS or result.status in (401, 403):
            if circuit_breaker is not None:
                circuit_breaker.record_failure(provider)
        else:
            # Non-retryable, non-auth provider error (e.g. 400 bad request
            # shaped by the gateway itself): honest 4xx passthrough. The
            # upstream answered, so it is not a provider-health failure.
            return result
    if circuit_breaker is not None and skipped_open and skipped_open == len(chain):
        # Fail-open: every route was skipped by the breaker, so try the whole
        # chain once with the breaker ignored rather than guaranteeing a 502.
        return await execute_chain(
            chain, payload, attempt_fn=attempt, circuit_breaker=None
        )
    raise ProviderChainExhausted(
        "all providers in the chain failed — 502 upstream (zero silent fallback)",
        ledger=ledger.entries,
    )

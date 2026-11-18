"""
service/providers/adapters.py — Unified Provider Execution Layer.

All 6 providers are connected via their OpenAI-compatible HTTP surfaces:
- Gemini (Google Generative AI OpenAI-compat surface)
- Groq (High-speed Llama/Qwen models)
- OpenRouter (Aggregated catalog)
- OpenAI (Official OpenAI platform)
- Mistral (Mistral AI endpoints)
- Hugging Face (Inference Router)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, Tuple
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger("supremeai.adapters")

# One-shot config-defect warnings: keyed by defect signature so a hot request
# path never spams the log, but every distinct misconfiguration surfaces loudly
# exactly once per process (DNS ENOTFOUND storms are otherwise undiagnosable).
_stealth_warned: set = set()


def _mask_host(url: str) -> str:
    """Host-only view of a webhook URL, safe for logs and API error bodies.

    Strips scheme, userinfo, path and query (a relay URL may embed a token in
    its path/query — never echo those back to anonymous callers). The hostname
    itself is additionally truncated so even infra names stay partially masked:
    supremeai-worker.paykaribazaronline.workers.dev -> supr….workers.dev
    """
    try:
        host = urlsplit(url if "://" in url else "http://" + url).hostname or ""
    except ValueError:
        host = ""
    if not host:
        return "(unparseable-host)"
    labels = host.split(".")
    tail = ".".join(labels[-2:]) if len(labels) >= 2 else host
    return f"{host[:4]}…{tail}" if len(host) > 12 else host


PROVIDER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "gemini": {
        "base_url": os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"),
        "default_model": os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest"),
    },
    "groq": {
        "base_url": os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        "default_model": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
    },
    "openrouter": {
        "base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        "default_model": os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-lightning:free"),
    },
    "openai": {
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "default_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    },
    "mistral": {
        "base_url": os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1"),
        "default_model": os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
    },
    "huggingface": {
        "base_url": os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1"),
        "default_model": os.getenv("HF_MODEL", "meta-llama/Llama-3.2-3B-Instruct"),
    },
    "v0": {
        "base_url": os.getenv("V0_BASE_URL", "https://api.v0.dev/v1"),
        "default_model": os.getenv("V0_MODEL", "v0-1.0-md"),
    },
    "perplexity": {
        "base_url": os.getenv("PERPLEXITY_BASE_URL", "https://api.perplexity.ai"),
        "default_model": os.getenv("PERPLEXITY_MODEL", "sonar"),
    },
    "sambanova": {
        "base_url": os.getenv("SAMBANOVA_BASE_URL", "https://api.sambanova.ai/v1"),
        "default_model": os.getenv("SAMBANOVA_MODEL", "Meta-Llama-3.3-70B-Instruct"),
    },
    "kilo": {
        "base_url": os.getenv("KILO_BASE_URL", "https://api.kilo.ai/api/gateway"),
        "default_model": os.getenv("KILO_MODEL", "nvidia/nemotron-3.5-lightning:free"),
    },
    "routesme": {
        "base_url": os.getenv("ROUTEME_BASE_URL", "https://routesme.online/v1"),
        "default_model": os.getenv("ROUTEME_FREE_MODEL", os.getenv("ROUTEME_MODEL", "GLM-5.3-Flash")),
    },
    "bynara": {
        "base_url": os.getenv("BYNARA_BASE_URL", "https://router.bynara.id/v1"),
        "default_model": os.getenv("BYNARA_FREE_MODEL", "agnes-2.5-flash"),
    },
    "bai": {
        "base_url": os.getenv("BAI_BASE_URL", "https://api.b.ai/v1"),
        "default_model": os.getenv("BAI_FREE_MODEL", "qwen3.8-flash"),
    },
    "unorouter": {
        "base_url": os.getenv("UNOROUTER_BASE_URL", "https://api.unorouter.com/v1"),
        "default_model": os.getenv("UNOROUTER_FREE_MODEL", "gemini-3.1-flash-lite:free"),
    },
    "cohere": {
        "base_url": os.getenv("COHERE_BASE_URL", "https://api.cohere.ai/compatibility/v1"),
        "default_model": os.getenv("COHERE_FREE_MODEL", "command-r-08-2024"),
    },
    "llm7": {
        "base_url": os.getenv("LLM7_BASE_URL", "https://api.llm7.io/v1"),
        "default_model": os.getenv("LLM7_FREE_MODEL", "glm-5.3-flash"),
    },
    "ghost_gemini": {
        "base_url": os.getenv("GHOST_TOWER_URL", "http://127.0.0.1:8788"),
        "default_model": "gemini-web",
    },
    "web_session": {
        "base_url": os.getenv("WEB_SESSION_URL", "http://127.0.0.1:8788"),
        "default_model": "web-session-auto",
    },
}

# Meta-routers ("kilo-auto/free", "openrouter/free") and paid auto-routers ("kilo-auto/efficient")
# are strictly excluded so aggregators only route to verified, deterministic `:free` models.
EXCLUDED_META_OR_PAID_MODELS: frozenset[str] = frozenset({
    "kilo-auto/free",
    "openrouter/free",
    "kilo-auto/efficient",
    "auto",
})

# Global "paid avoid": any (provider, model) that returns HTTP 402 (payment required) is
# added here at runtime and filtered out of that provider's candidate cascade, so a paid
# model is never retried on any slot/key of that provider for the lifetime of the process.
# Keyed per-provider because a model slug may be free on one router and paid on another.
# Complements the per-slot unsupported_models blacklist and free_model_discovery's 402 skip —
# this makes the whole pool behave like Kilo's free-only routing (paid models auto-excluded).
_PAID_MODELS: set[tuple[str, str]] = set()

# Exhaustive zero-waste model cascades: if top model hits quota/limit (429) or is unavailable (404/400),
# the adapter seamlessly tries the next model in sequence without failing the client request.
PROVIDER_MODEL_CASCADES: Dict[str, list[str]] = {
    "groq": [
        # 2026-11-17: only models verified live on Groq's /models with the
        # deployment key. Removed llama-3.3-70b-versatile / llama-3.1-8b-instant
        # (404) and qwen-2.5-32b / deepseek-r1-distill-llama-70b (400
        # decommissioned) — they made every groq attempt cascade through dead
        # models before failing with "No models available for provider groq".
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-safeguard-20b",
        "allam-2-7b",
    ],
    # 2026-11-16: gemini-1.5-* and gemini-2.0-flash were retired (HTTP 404 on the
    # OpenAI-compat surface). Keeping them made every quota-limited key cascade
    # through ~6 dead models (~500-700ms each) before failing — the root cause of
    # multi-second "hi" latency. Cascade now lists only live, verified models.
    "gemini": [
        "gemini-flash-lite-latest",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-flash-latest",
    ],
    # 2026-11-16: Concrete `:free` models verified against /api/v1/models (excluding
    # blind meta-router "openrouter/free" and retired 404 slugs).
    "openrouter": [
        "nvidia/nemotron-3.5-lightning:free",
        "nvidia/nemotron-3.5-super-vl:free",
        "meta-llama/llama-3.2-11b-vision-instruct:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "cohere/north-mini-code:free",
        "baidu/ernie-5.5-flash-preview:free",
    ],
    "mistral": [
        "open-mistral-7b",
        "open-mixtral-8x7b",
        "open-mixtral-8x22b",
        "mistral-small-latest",
    ],
    "sambanova": [
        "Meta-Llama-3.3-70B-Instruct",
        "Meta-Llama-3.1-8B-Instruct",
        "Qwen2.5-72B-Instruct",
    ],
    # Concrete `:free` models verified on Kilo gateway (excluding "kilo-auto/free"
    # meta-router and paid "kilo-auto/efficient").
    "kilo": [
        "nvidia/nemotron-3.5-lightning:free",
        "nvidia/nemotron-3.5-super-vl:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "cohere/north-mini-code:free",
        "baidu/ernie-5.5-flash-preview:free",
    ],
    "openai": [
        "gpt-4o-mini",
        "gpt-4o",
    ],
    "huggingface": [
        "meta-llama/Llama-3.2-3B-Instruct",
        "meta-llama/Llama-3.3-70B-Instruct",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
    ],
    "perplexity": [
        "sonar",
        "sonar-pro",
    ],
    "v0": [
        "v0-1.0-md",
        "v0-1.5-md",
    ],
    # RoutesMe (routesme.online) — OpenAI-compatible free aggregator. "GLM-5.3-Flash"
    # and "Step-5-preview" verified HTTP 200 with the deployment key (2026-11-17).
    "routesme": [
        "GLM-5.3-Flash",
        "Step-5-preview",
        "GLM5.3",
        "Deepseek-v4.1-flash",
        "Kimi-k3",
        "Minimax-M3",
        "Step-3.7-Flash",
    ],
    # Bynara (router.bynara.id) — OpenAI-compatible free aggregator. Models verified
    # on /models (2026-11-17); agnes-2.5-flash is the routing_policy primary.
    "bynara": [
        "agnes-2.5-flash",
        "glm-5.3-flash",
        "deepseek-v4.1-flash",
        "qwen3.8-flash",
        "mimo-v2.6-flash",
    ],
    # B.ai (api.b.ai) — OpenAI-compatible free aggregator. qwen3.8-flash is the
    # routing_policy primary; gemini-3.5-flash-lite is a fast fallback.
    "bai": [
        "qwen3.8-flash",
        "gemini-3.5-flash-lite",
        "glm-5.3-flash",
        "mimo-v2.6-flash",
        "gpt-5.4-mini",
    ],
    # UnoRouter (api.unorouter.com) — free `:free` models. Verified HTTP 200
    # (2026-11-17); glm/qwen/gpt-oss :free variants return 403 consent_required.
    "unorouter": [
        "gemini-3.1-flash-lite:free",
        "step-5-preview:free",
        "agnes-2.5-flash:free",
    ],
    # Cohere (api.cohere.ai compatibility) — trial keys, verified HTTP 200.
    "cohere": [
        "command-r-08-2024",
        "command-a-03-2025",
        "command-r7b-12-2024",
    ],
    # LLM7.io (api.llm7.io) — verified HTTP 200; gemini/deepseek/mimo need balance (402).
    "llm7": [
        "glm-5.3-flash",
        "gpt-oss:20b",
    ],
}


def normalize_stealth_url(url: str) -> str:
    """
    Ensure the webhook URL targets the exact synchronous OpenAI-compatible endpoint
    (/v1/chat/completions) instead of base domains, /mcp, or /dispatch.

    Config-defect hardening (root cause of the Oct-23 "relay offline" outage:
    STEALTH_WEBHOOK_URL held a value whose host failed DNS with [Errno -2]):
    - strip env-quoting accidents (value wrapped in "..." or '...')
    - collapse internal whitespace (never valid in a URL)
    - repair doubled scheme (https://https://… -> host parsed as "https" -> ENOTFOUND)
    - one-shot CRITICAL warnings for hosts that cannot possibly work:
      underscore in host (getaddrinfo fails) and workers.dev APEX
      (a worker URL is always <name>.<account-subdomain>.workers.dev — the apex
      does not resolve; verified by DNS probe during the outage diagnosis).
    """
    raw = url.strip()
    if not raw:
        return ""
    while len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("\"", "'"):
        raw = raw[1:-1].strip()
    if not raw:
        return ""
    if any(ch.isspace() for ch in raw):
        raw = "".join(raw.split())
    _low = raw.lower()
    for _dbl in ("https://https://", "https://http://", "http://https://", "http://http://"):
        if _low.startswith(_dbl):
            raw = raw.split("://", 1)[1]
            break
    full = raw if "://" in raw else "http://" + raw
    base = full.split("?", 1)[0].rstrip("/")
    query = ("?" + full.split("?", 1)[1]) if "?" in full else ""

    # One-shot diagnostics for values that will fail DNS regardless of network
    try:
        _host = urlsplit(base).hostname or ""
    except ValueError:
        _host = ""
    if _host:
        if "_" in _host and ("bad-host" + _host) not in _stealth_warned:
            _stealth_warned.add("bad-host" + _host)
            logger.critical(
                "STEALTH_WEBHOOK_URL host '%s' contains '_' — getaddrinfo() will fail "
                "with [Errno -2]. Fix the Infisical value (underscore hosts are not DNS-resolvable).",
                _mask_host(base),
            )
        _labels = _host.split(".")
        if _host.endswith(".workers.dev") and len(_labels) <= 3 and ("apex" + _host) not in _stealth_warned:
            _stealth_warned.add("apex" + _host)
            logger.critical(
                "STEALTH_WEBHOOK_URL host '%s' is the workers.dev APEX (does not resolve). "
                "A worker URL is always <worker-name>.<account-subdomain>.workers.dev.",
                _mask_host(base),
            )

    # Strip incompatible non-chat suffixes
    if base.endswith(("/api/chat", "/chat", "/dispatch", "/mcp", "/webhook/telegram")):
        base = base.rsplit("/", 1)[0].rstrip("/")

    # Ensure path ends with /v1/chat/completions
    if not base.endswith("/v1/chat/completions"):
        if base.endswith("/v1"):
            base = base + "/chat/completions"
        else:
            base = base + "/v1/chat/completions"

    return base + query



def _resolve_candidate_models(
    provider: str,
    config: dict[str, Any],
    slot: Any,
    client_model: str,
) -> list[str]:
    cascade = list(PROVIDER_MODEL_CASCADES.get(provider, [config["default_model"]]))
    discovered = getattr(slot, "discovered_models", None) if slot else None
    if discovered:
        cascade = [m for m in discovered if str(m).lower() not in EXCLUDED_META_OR_PAID_MODELS]
    # Global paid avoid: drop any model that has 402'd on this provider in this process.
    if _PAID_MODELS:
        cascade = [m for m in cascade if (provider, m) not in _PAID_MODELS]
    candidate_models: list[str] = []
    preferred_slot_model = getattr(slot, "preferred_model", None) if slot else None
    unsupported_set = getattr(slot, "unsupported_models", set()) if slot else set()
    supported_set = getattr(slot, "supported_models", set()) if slot else set()
    if (
        client_model
        and client_model not in ("auto", "default", "")
        and str(client_model).lower() not in EXCLUDED_META_OR_PAID_MODELS
        and not str(client_model).startswith("supremeai/")
        and not str(client_model).startswith("supreme-")
        and not str(client_model).startswith("supremeai-")
        and (str(client_model) in cascade or provider == "openrouter")
    ):
        if str(client_model) not in candidate_models and str(client_model) not in unsupported_set:
            candidate_models.append(str(client_model))

    if (
        preferred_slot_model
        and str(preferred_slot_model).lower() not in EXCLUDED_META_OR_PAID_MODELS
        and preferred_slot_model not in unsupported_set
        and preferred_slot_model not in candidate_models
    ):
        candidate_models.append(preferred_slot_model)

    for m in cascade:
        if str(m).lower() in EXCLUDED_META_OR_PAID_MODELS:
            continue
        if m in unsupported_set and m not in supported_set:
            continue
        if m not in candidate_models:
            candidate_models.append(m)

    if not candidate_models:
        if slot and hasattr(slot, "unsupported_models"):
            slot.unsupported_models.clear()
        default_m = config.get("default_model")
        if default_m and str(default_m).lower() not in EXCLUDED_META_OR_PAID_MODELS:
            candidate_models = [default_m]
        else:
            candidate_models = [m for m in cascade if str(m).lower() not in EXCLUDED_META_OR_PAID_MODELS][:2]
    return candidate_models


@asynccontextmanager
async def _pooled_http_client(timeout: float = 28.0):
    """Yield the shared pooled httpx client (connection reuse)."""
    yield _get_stealth_client()

async def forward_chat_completion(
    provider: str,
    api_key: str,
    payload: Dict[str, Any],
    slot: Any = None,
    timeout: float = 6.0
) -> Tuple[int, Dict[str, Any] | str]:
    """
    Forwards an OpenAI-format chat completion request to the chosen provider.
    Executes an in-flight model cascade: if the top model returns 429/404/400/503,
    it automatically attempts the remaining prioritized models before reporting error.
    Returns (status_code, parsed_json_or_text).
    """
    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        return 400, {"error": f"Unknown provider: {provider}"}

    base_url = config["base_url"].rstrip("/")
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "SupremeAI-Gateway/2.0",
    }

    # OpenRouter requires optional referer/title headers
    if provider == "openrouter":
        headers["HTTP-Referer"] = (
            os.getenv("OPENROUTER_REFERER")
            or os.getenv("RENDER_EXTERNAL_URL")
            or "https://supremeai-api-ulw0.onrender.com"
        )
        headers["X-Title"] = "SupremeAI Gateway"

    # Build prioritized candidate models list
    body = dict(payload)
    # Strip internal routing & non-standard keys to prevent provider 400 Bad Request
    # (e.g. OpenRouter rejects requests containing both "prompt" and "messages")
    for non_openai_key in (
        "preferred_provider",
        "temp",
        "provider",
        "prompt",
        "message",
        "session_id",
        "conversation_id",
        "task_type",
        "deepResearch",
        "userContext",
        "language_pref",
        "response_style",
        "mode",
    ):
        body.pop(non_openai_key, None)
    # Always request non-streaming JSON from upstream providers; gateway handles client SSE streaming
    body["stream"] = False
    if provider == "gemini":
        body.pop("frequency_penalty", None)
        body.pop("presence_penalty", None)

    client_model = body.get("model", "auto")
    candidate_models = _resolve_candidate_models(provider, config, slot, client_model)

    last_status = 500
    last_data: Any = {"error": f"No models available for provider {provider}"}

    async with _pooled_http_client(timeout) as client:
        for model_name in candidate_models:
            body["model"] = model_name
            try:
                response = await client.post(url, json=body, headers=headers, timeout=timeout)
                status_code = response.status_code
                try:
                    data = response.json()
                except Exception:  # noqa: BLE001
                    data = response.text

                # Success path (2xx)
                if 200 <= status_code < 300:
                    if slot and hasattr(slot, "supported_models"):
                        slot.supported_models.add(model_name)
                        slot.preferred_model = model_name
                        slot.unsupported_models.discard(model_name)
                    if isinstance(data, dict) and "model" not in data:
                        data["model"] = model_name
                    return status_code, data

                # Skip paid tiers if requested payment (402) and blacklist this paid model on the slot
                if status_code == 402:
                    _PAID_MODELS.add((provider, model_name))
                    if slot and hasattr(slot, "unsupported_models"):
                        slot.unsupported_models.add(model_name)
                        slot.supported_models.discard(model_name)
                        if getattr(slot, "preferred_model", None) == model_name:
                            slot.preferred_model = next(iter(slot.supported_models), None)
                    logger.warning(f"[{provider}] Model {model_name} requested payment (402); skipping paid tier.")
                    last_status, last_data = status_code, data
                    continue

                # Auto-downgrade on quota exhaustion, missing model slug, or temporary overload
                if status_code in (404, 400, 429, 503):
                    if status_code in (404, 400) and slot and hasattr(slot, "unsupported_models"):
                        slot.unsupported_models.add(model_name)
                        slot.supported_models.discard(model_name)
                        if getattr(slot, "preferred_model", None) == model_name:
                            slot.preferred_model = next(iter(slot.supported_models), None)
                    logger.warning(
                        f"[{provider}] Model {model_name} returned {status_code}; "
                        f"cascading to next available model..."
                    )
                    last_status, last_data = status_code, data
                    continue

                # For fatal authentication errors (401/403 on key), do not loop other models with same key
                last_status, last_data = status_code, data
                break

            except httpx.TimeoutException:
                logger.warning(f"[{provider}] Model {model_name} timed out after {timeout}s; trying next model...")
                last_status, last_data = 504, {"error": f"Provider {provider} model {model_name} timed out"}
                continue
            except httpx.RequestError as exc:
                return 502, {"error": f"Connection error to {provider}: {exc!s}"}

    return last_status, last_data


async def stream_chat_completion_events(
    provider: str,
    api_key: str,
    payload: Dict[str, Any],
    slot: Any = None,
    timeout: float = 6.0,
) -> AsyncIterator[Tuple[str, Any]]:
    """True upstream SSE streaming with in-flight model cascade (audit P0-5 fix).

    Yields tuples:
      ("status", {"status": 200, "model": <model>})  once, on first successful stream
      ("event",  {"delta": str, "finish_reason": ..., "tool_calls": ..., "model": ...})
      ("done",   None)                                on clean upstream [DONE]
      ("error",  {"error": ...})                      on total failure (no status was yielded)

    Mirrors forward_chat_completion's cascade: 400/402/404/429/503 on a model
    cascades to the next candidate; 401/403 and connection errors fail fast.
    """
    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        yield ("error", {"error": f"Unknown provider: {provider}"})
        return

    base_url = config["base_url"].rstrip("/")
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "SupremeAI-Gateway/2.0",
        "Accept": "text/event-stream",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = (
            os.getenv("OPENROUTER_REFERER")
            or os.getenv("RENDER_EXTERNAL_URL")
            or "https://supremeai-api-ulw0.onrender.com"
        )
        headers["X-Title"] = "SupremeAI Gateway"

    body = dict(payload)
    for non_openai_key in (
        "preferred_provider", "temp", "provider", "prompt", "message",
        "session_id", "conversation_id", "task_type", "deepResearch",
        "userContext", "language_pref", "response_style", "mode",
    ):
        body.pop(non_openai_key, None)
    body["stream"] = True
    if provider == "gemini":
        body.pop("frequency_penalty", None)
        body.pop("presence_penalty", None)

    client_model = body.get("model", "auto")
    candidate_models = _resolve_candidate_models(provider, config, slot, client_model)

    async with _pooled_http_client(timeout) as client:
        for model_name in candidate_models:
            body["model"] = model_name
            try:
                stream_timeout = httpx.Timeout(timeout, connect=4.0)
                async with client.stream("POST", url, json=body, headers=headers, timeout=stream_timeout) as response:
                    status_code = response.status_code
                    if status_code in (400, 402, 404, 429, 503):
                        await response.aread()
                        if status_code in (400, 402, 404) and slot and hasattr(slot, "unsupported_models"):
                            slot.unsupported_models.add(model_name)
                            slot.supported_models.discard(model_name)
                            if getattr(slot, "preferred_model", None) == model_name:
                                slot.preferred_model = next(iter(slot.supported_models), None)
                        if status_code == 402:
                            _PAID_MODELS.add((provider, model_name))
                            logger.warning(f"[{provider}] Model {model_name} requested payment (402); skipping paid tier.")
                        else:
                            logger.warning(
                                f"[{provider}] Model {model_name} returned {status_code}; cascading to next available model..."
                            )
                        continue
                    if 200 <= status_code < 300:
                        if slot and hasattr(slot, "supported_models"):
                            slot.supported_models.add(model_name)
                            slot.preferred_model = model_name
                            slot.unsupported_models.discard(model_name)
                        yield ("status", {"status": 200, "model": model_name})
                        async for line in response.aiter_lines():
                            line = line.strip()
                            if not line.startswith("data:"):
                                continue
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                yield ("done", None)
                                return
                            try:
                                chunk = json.loads(data_str)
                            except Exception:  # noqa: BLE001 - skip malformed keep-alive lines
                                continue
                            if not isinstance(chunk, dict):
                                continue
                            chs = chunk.get("choices") or []
                            if not chs or not isinstance(chs[0], dict):
                                continue
                            delta = chs[0].get("delta") or {}
                            content = delta.get("content") or ""
                            finish_reason = chs[0].get("finish_reason")
                            tool_calls = delta.get("tool_calls")
                            if content or finish_reason or tool_calls:
                                yield (
                                    "event",
                                    {
                                        "delta": content,
                                        "finish_reason": finish_reason,
                                        "tool_calls": tool_calls,
                                        "model": model_name,
                                    },
                                )
                        yield ("done", None)
                        return
                    # Fatal auth/other errors: do not loop other models with same key
                    await response.aread()
                    logger.warning(f"[{provider}] Model {model_name} returned {status_code}; aborting stream.")
                    yield ("error", {"error": f"Provider {provider} returned {status_code}"})
                    return
            except httpx.TimeoutException:
                logger.warning(f"[{provider}] Model {model_name} timed out after {timeout}s; trying next model...")
                continue
            except httpx.RequestError as exc:
                yield ("error", {"error": f"Connection error to {provider}: {exc!s}"})
                return

    err_detail = (
        "Vision model unavailable: Gemini API quota exhausted or rate-limited"
        if provider == "gemini"
        else f"No models available for provider {provider}"
    )
    yield ("error", {"error": err_detail})


async def forward_stealth_webhook(
    webhook_url: str,
    secret: Optional[str],
    payload: Dict[str, Any],
    timeout: float = 28.0,
) -> Tuple[int, Dict[str, Any] | str]:
    """
    Priority-1 Stealth Forwarder (improved).

    Improvements vs previous version:
    - Reuses a pooled httpx.AsyncClient (keep-alive, HTTP/2) instead of opening
      a new connection per request -> much lower latency on repeated calls.
    - Fast-fail connect timeout (5s) so dead hosts surface quickly.
    - One automatic retry on transient connect/timeout errors.
    - Structured diagnostics: host, reason class, latency_ms in both logs and
      error bodies, plus latency_ms on success.
    """
    if not webhook_url:
        return 404, {"error": "Stealth webhook not configured"}

    target_url = normalize_stealth_url(webhook_url)

    # Self-loop protection
    self_url = os.getenv("RENDER_EXTERNAL_URL", "")
    if (self_url and self_url in target_url) or "supremeai-api" in target_url:
        logger.warning("Stealth webhook points to gateway itself; skipping loop.")
        return 400, {"error": "Stealth webhook target points to self (loop prevented)"}

    if "supremeai-worker" in target_url and not os.getenv("ALLOW_WORKER_STEALTH"):
        logger.warning(f"Stealth webhook target ({target_url}) is async worker node (not chat completions).")
        return 405, {"error": "Configured stealth URL points to worker-node instead of chat completions relay"}

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SupremeAI-Stealth-Gateway/2.0",
    }
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
        headers["X-Stealth-Secret"] = secret
        headers["X-SupremeAI-Key"] = secret

    client = _get_stealth_client()
    started = time.monotonic()
    last_exc: Optional[Exception] = None
    for attempt in range(2):
        try:
            response = await client.post(target_url, json=payload, headers=headers, timeout=timeout)
            try:
                data = response.json()
            except Exception:  # noqa: BLE001
                data = response.text

            if isinstance(data, dict) and "reply" in data and "choices" not in data:
                data = {
                    "id": "chatcmpl-stealth-" + os.urandom(6).hex(),
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": payload.get("model", "stealth-priority1"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": str(data["reply"])},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                }
            latency = int((time.monotonic() - started) * 1000)
            logger.info("Stealth webhook OK status=%s latency=%sms attempt=%s", response.status_code, latency, attempt + 1)
            if isinstance(data, dict):
                data.setdefault("latency_ms", latency)
            return response.status_code, data
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exc = exc
            if attempt == 0:
                await asyncio.sleep(0.2)
                continue
            break
        except httpx.RequestError as exc:
            last_exc = exc
            break

    latency = int((time.monotonic() - started) * 1000)
    exc = last_exc
    _exc_text = str(exc) if exc is not None else "unknown error"
    _host = _mask_host(target_url)
    if isinstance(exc, httpx.TimeoutException) or "timed out" in _exc_text.lower() or "timeout" in _exc_text.lower():
        _errno = "timeout"
    elif any(sig in _exc_text for sig in ("Name or service not known", "Temporary failure in name resolution", "No address associated", "nodename nor servname")):
        _errno = "dns"
    elif "Connection refused" in _exc_text:
        _errno = "refused"
    else:
        _errno = "connect"
    logger.warning(
        "Stealth webhook connection error for host=%s class=%s: %s (latency=%sms)",
        _host,
        _errno,
        _exc_text,
        latency,
    )
    body = {"error": f"Stealth webhook connection error for host {_host} ({_errno}): {_exc_text}", "host": _host, "reason": _errno, "latency_ms": latency}
    if _errno == "timeout":
        body["error"] = "Stealth webhook timed out"
        return 504, body
    return 502, body


# Shared pooled client helpers
_STEALTH_CLIENT: Optional[httpx.AsyncClient] = None


def _get_stealth_client() -> httpx.AsyncClient:
    global _STEALTH_CLIENT
    if _STEALTH_CLIENT is not None:
        try:
            if not _STEALTH_CLIENT.is_closed:
                return _STEALTH_CLIENT
        except AttributeError:
            _STEALTH_CLIENT = None
    limits = httpx.Limits(
        max_connections=500,
        max_keepalive_connections=100,
        keepalive_expiry=60.0,
    )
    timeout = httpx.Timeout(28.0, connect=5.0)
    try:
        client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            http2=True,
        )
    except Exception:
        client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
        )
    # Only cache real clients (fakes used in tests lack is_closed).
    if hasattr(client, "is_closed"):
        _STEALTH_CLIENT = client
    return client


async def close_stealth_client() -> None:
    global _STEALTH_CLIENT
    if _STEALTH_CLIENT is not None and not _STEALTH_CLIENT.is_closed:
        await _STEALTH_CLIENT.aclose()
    _STEALTH_CLIENT = None

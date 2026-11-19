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
import hashlib
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, Tuple
from urllib.parse import urlsplit

import httpx

from ..free_route_policy import CATALOG_REQUIRED, approved_models

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

# Global "paid avoid": any (provider, model) that returns HTTP 402 (payment required) is
# added here at runtime and filtered out of that provider's candidate cascade, so a paid
# model is never retried on any slot/key of that provider for the lifetime of the process.
# Keyed per-provider because a model slug may be free on one router and paid on another.
# This cannot replace the approval check: a paid request may succeed without HTTP 402.
_PAID_MODELS: set[tuple[str, str]] = set()

# Candidate slugs and their order come from the verified operator approval.


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


def eligible_chat_models(provider: str, api_key: str, slot: Any = None, *, vision: bool = False) -> tuple[str, ...]:
    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        return ()
    base_url = config["base_url"].rstrip("/")
    approved = approved_models(provider, base_url, api_key, vision=vision)
    if not approved:
        return ()
    if provider in CATALOG_REQUIRED:
        identity = (base_url, hashlib.sha256(api_key.encode()).hexdigest())
        if (
            not slot
            or getattr(slot, "catalog_identity", None) != identity
            or getattr(slot, "catalog_valid_until", 0.0) <= time.monotonic()
        ):
            return ()
        approved = tuple(model for model in approved if model in slot.discovered_models)
    unsupported = getattr(slot, "unsupported_models", ())
    return tuple(model for model in approved if (provider, model) not in _PAID_MODELS and model not in unsupported)


def has_image_input(payload: dict) -> bool:
    return any(
        isinstance(part, dict) and "image" in str(part.get("type", "")).lower()
        for message in (payload.get("messages") or [])
        if isinstance(message, dict) and isinstance(message.get("content"), list)
        for part in message["content"]
    )


def _resolve_candidate_models(
    provider: str, api_key: str, slot: Any, client_model: str, *, vision: bool = False
) -> list[str]:
    eligible = eligible_chat_models(provider, api_key, slot, vision=vision)
    order = (client_model, getattr(slot, "preferred_model", None), *eligible)
    return list(dict.fromkeys(model for model in order if model in eligible))


# Only standard text/chat controls go upstream. Vendor options such as
# alternate models, plugins, native tools and paid service tiers are not
# part of the approved model route.
_CHAT_FIELDS = frozenset({
    "messages", "model", "temperature", "top_p", "max_tokens", "max_completion_tokens",
    "stop", "seed", "presence_penalty", "frequency_penalty", "response_format",
    "tools", "tool_choice", "parallel_tool_calls", "stream_options", "reasoning_effort",
})


def _provider_payload(payload: dict, provider: str, *, stream: bool) -> dict:
    body = {key: value for key, value in payload.items() if key in _CHAT_FIELDS}
    body["stream"] = stream
    if not stream:
        body.pop("stream_options", None)
    if provider == "gemini":
        body.pop("frequency_penalty", None)
        body.pop("presence_penalty", None)
    tools = body.get("tools")
    if isinstance(tools, list):
        body["tools"] = [
            {"type": "function", "function": tool["function"]}
            for tool in tools
            if isinstance(tool, dict) and tool.get("type") == "function" and isinstance(tool.get("function"), dict)
        ]
    else:
        body.pop("tools", None)
    if not body.get("tools"):
        body.pop("tool_choice", None)
        body.pop("parallel_tool_calls", None)
    return body


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

    body = _provider_payload(payload, provider, stream=False)
    vision = has_image_input(body)
    candidate_models = _resolve_candidate_models(provider, api_key, slot, body.get("model", "auto"), vision=vision)
    if not candidate_models:
        return 503, {"error": "No approved free model available"}

    last_status = 503
    last_data: Any = {"error": "No approved free model available"}

    async with _pooled_http_client(timeout) as client:
        for model_name in candidate_models:
            # Another request may have withdrawn the model or approval may
            # have expired while earlier candidates were being attempted.
            if model_name not in eligible_chat_models(provider, api_key, slot, vision=vision):
                continue
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
      ("status", {"status": 200, "model": <model>})  on upstream 2xx headers
      ("event",  {"delta": str, "finish_reason": ..., "tool_calls": ..., "model": ...})
      ("done",   None)                                on [DONE] or EOF after a finish reason
      ("error",  {"error": ...})                      if the stream fails before or after output

    Model fallback is allowed only before the first text/tool delta.
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

    body = _provider_payload(payload, provider, stream=True)
    vision = has_image_input(body)
    candidate_models = _resolve_candidate_models(provider, api_key, slot, body.get("model", "auto"), vision=vision)
    if not candidate_models:
        yield ("error", {"error": "No approved free model available", "status": 503})
        return

    async with _pooled_http_client(timeout) as client:
        for model_name in candidate_models:
            # Another request may have withdrawn the model or approval may
            # have expired while earlier candidates were being attempted.
            if model_name not in eligible_chat_models(provider, api_key, slot, vision=vision):
                continue
            body["model"] = model_name
            committed = False
            saw_finish = False
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
                            choices = chunk.get("choices") or []
                            choice = choices[0] if choices and isinstance(choices[0], dict) else {}
                            finish_reason = choice.get("finish_reason")
                            if chunk.get("error") is not None or finish_reason == "error":
                                yield ("error", {"error": "Upstream provider returned a stream error"})
                                return
                            delta = choice.get("delta") or {}
                            content = delta.get("content") or ""
                            tool_calls = delta.get("tool_calls")
                            if content or finish_reason or tool_calls:
                                committed = committed or bool(content or tool_calls)
                                saw_finish = saw_finish or bool(finish_reason)
                                yield (
                                    "event",
                                    {
                                        "delta": content,
                                        "finish_reason": finish_reason,
                                        "tool_calls": tool_calls,
                                        "model": model_name,
                                    },
                                )
                        if saw_finish:
                            yield ("done", None)
                        else:
                            yield ("error", {"error": "Upstream stream ended before completion"})
                        return
                    # Fatal auth/other errors: do not loop other models with same key
                    await response.aread()
                    logger.warning(f"[{provider}] Model {model_name} returned {status_code}; aborting stream.")
                    yield ("error", {"error": f"Provider {provider} returned {status_code}", "status": status_code})
                    return
            except httpx.TimeoutException:
                if committed:
                    yield ("error", {"error": "Upstream stream timed out"})
                    return
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

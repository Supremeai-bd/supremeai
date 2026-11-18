"""gateway/service/free_model_discovery.py — per-key free model discovery & micro-probe.

Implements the Dynamic Active Free Model Discovery plan at root level:
- query each provider's /models endpoint with the individual key
- filter free/usable models
- micro-probe with max_tokens=1 to verify real quota and measure latency
- store verified models on the KeySlot and mark dead keys in cooldown
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
import os as _os
import time
from typing import Any, List, Tuple

import httpx

logger = logging.getLogger("supremeai.free_model_discovery")


async def _redis_get(key: str) -> Any:
    url = _os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")
    token = _os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    if not url or not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{url}/get/{key}", headers={"Authorization": f"Bearer {token}"})
            if resp.status_code != 200:
                return None
            data = resp.json()
            raw = data.get("result")
            if not raw:
                return None
            return _json.loads(raw)
    except Exception:  # noqa: BLE001
        return None


async def _redis_set(key: str, value: Any, ttl: int = 900) -> None:
    url = _os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")
    token = _os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    if not url or not token:
        return
    try:
        payload = _json.dumps(value)
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{url}/set/{key}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"value": payload, "ex": ttl},
            )
    except Exception:  # noqa: BLE001
        pass

PROVIDER_BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "mistral": "https://api.mistral.ai/v1",
    "huggingface": "https://router.huggingface.co/v1",
    "sambanova": "https://api.sambanova.ai/v1",
    "kilo": "https://api.kilo.ai/api/gateway",
    "v0": "https://api.v0.dev/v1",
    "routesme": "https://routesme.online/v1",
    "bynara": "https://router.bynara.id/v1",
    "bai": "https://api.b.ai/v1",
    "unorouter": "https://api.unorouter.com/v1",
    "cohere": "https://api.cohere.ai/compatibility/v1",
    "llm7": "https://api.llm7.io/v1",
}

# Meta-routers ("kilo-auto/free", "openrouter/free") blindly delegate model choice
# upstream (often picking slow/rate-limited models), and "kilo-auto/efficient" is paid (402).
# Always exclude them so discovery ranks concrete, deterministic `:free` models.
META_ROUTER_EXCLUDES = frozenset({
    "kilo-auto/free",
    "openrouter/free",
    "kilo-auto/efficient",
    "auto",
    "default",
})

NON_CHAT_MODEL_MARKERS = (
    "lyria",
    "whisper",
    "tts",
    "embedding",
    "moderation",
    "dall-e",
    "flux",
    "imagen",
)


def _is_zero_price(val: Any) -> bool:
    if val is None or val == "":
        return False
    try:
        return float(val) == 0.0
    except (TypeError, ValueError):
        return False


def _extract_free_aggregator_model(item: Any) -> str | None:
    """Return model ID only if it is a concrete, zero-cost chat model (never paid or meta-router)."""
    if isinstance(item, str):
        mid = item.strip()
        low = mid.lower()
        if not mid or low in META_ROUTER_EXCLUDES:
            return None
        if any(marker in low for marker in NON_CHAT_MODEL_MARKERS):
            return None
        if mid.endswith(":free") or "free" in low:
            return mid
        return None

    if not isinstance(item, dict):
        return None

    mid = str(item.get("id") or item.get("model") or item.get("name") or "").strip()
    low = mid.lower()
    if not mid or low in META_ROUTER_EXCLUDES:
        return None
    if any(marker in low for marker in NON_CHAT_MODEL_MARKERS):
        return None

    pricing = item.get("pricing")
    if isinstance(pricing, dict) and ("prompt" in pricing or "completion" in pricing):
        # Strict paid-model avoidance: if prompt or completion cost is non-zero, reject immediately.
        if not (_is_zero_price(pricing.get("prompt")) and _is_zero_price(pricing.get("completion"))):
            return None
        # Also require explicit `:free` or `free` tag so non-chat zero-priced previews don't slip in.
        if mid.endswith(":free") or "free" in low:
            return mid
        return None

    if mid.endswith(":free") or "free" in low:
        return mid
    return None


async def _fetch_model_ids(provider: str, base_url: str, api_key: str) -> List[str]:
    provider = (provider or "").lower()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                resp = await client.get(url)
            else:
                url = base_url.rstrip("/") + "/models"
                resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
            if resp.status_code != 200:
                return []
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.debug("model list fetch failed for %s: %s", provider, exc)
        return []

    ids: List[str] = []
    if provider == "gemini":
        for m in data.get("models", []) if isinstance(data, dict) else []:
            methods = m.get("supportedGenerationMethods", []) or []
            if "generateContent" in methods:
                name = str(m.get("name", "")).split("/")[-1]
                if name:
                    ids.append(name)
    elif provider in ("openrouter", "kilo"):
        raw_items = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        for m in raw_items:
            free_id = _extract_free_aggregator_model(m)
            if free_id:
                ids.append(free_id)
    else:
        for m in (data.get("data", []) if isinstance(data, dict) else []):
            mid = m.get("id")
            if mid and str(mid).strip().lower() not in META_ROUTER_EXCLUDES:
                ids.append(str(mid))

    seen = set()
    out: List[str] = []
    for mid in ids:
        if mid not in seen:
            seen.add(mid)
            out.append(mid)
    return out


async def _probe_model(provider: str, base_url: str, api_key: str, model: str) -> Tuple[bool, float, int]:
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1, "stream": False}
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=body, headers=headers)
        latency = (time.monotonic() - started) * 1000.0
        return (200 <= resp.status_code < 300), latency, resp.status_code
    except Exception:  # noqa: BLE001
        return False, (time.monotonic() - started) * 1000.0, 0


async def validate_slot(slot: Any) -> None:
    """Discover + verify free models for a single KeySlot in place."""
    provider = getattr(slot, "provider", "")
    base_url = PROVIDER_BASE_URLS.get(provider.lower())
    if not base_url:
        # fall back to adapters config if available
        try:
            from gateway.service.providers.adapters import PROVIDER_CONFIGS
            base_url = PROVIDER_CONFIGS.get(provider, {}).get("base_url", "")
        except Exception:  # noqa: BLE001
            base_url = ""
    if not base_url:
        base_url = _os.getenv(f"{provider.upper()}_BASE_URL", "") or _os.getenv(f"{provider.upper()}_API_BASE_URL", "")
    if not base_url:
        return

    api_key = getattr(slot, "key", "")
    cache_key = f"supremeai:discovery:{provider}:{getattr(slot, 'name', '')}"
    cached = await _redis_get(cache_key)
    if isinstance(cached, dict) and cached.get("models"):
        slot.discovered_models = list(cached["models"])
        slot.preferred_model = slot.discovered_models[0] if slot.discovered_models else getattr(slot, "preferred_model", None)
        try:
            slot.ewma_latency_ms = float(cached.get("latency", slot.ewma_latency_ms or 0.0))
        except (TypeError, ValueError):
            pass
        try:
            slot.supported_models.update(slot.discovered_models)
        except Exception:  # noqa: BLE001
            pass
        return

    ids = await _fetch_model_ids(provider, base_url, api_key)
    if not ids:
        # fallback to configured default
        try:
            from gateway.service.providers.adapters import PROVIDER_CONFIGS
            default_model = PROVIDER_CONFIGS.get(provider, {}).get("default_model")
            if default_model:
                ids = [default_model]
        except Exception:  # noqa: BLE001
            pass
    if not ids:
        return

    passing: List[Tuple[str, float]] = []
    dead_key = False
    # Probe explicit `:free` models first so an aggregator's paid entries (e.g. kilo's
    # "kilo-auto/efficient") or meta-routers do not shadow concrete working free models.
    def _free_rank(m: str) -> int:
        low = m.lower()
        if low.endswith(":free"):
            return 0
        if "free" in low and low not in META_ROUTER_EXCLUDES:
            return 1
        return 2

    ids = sorted(ids, key=_free_rank)
    for model in ids[:8]:
        ok, latency, status = await _probe_model(provider, base_url, api_key, model)
        if ok:
            passing.append((model, latency))
            try:
                slot.supported_models.add(model)
            except Exception:  # noqa: BLE001
                pass
        else:
            if status in (401, 403):
                dead_key = True
                break
            # 402 (payment required) means THIS model is paid, not that the key is
            # dead — aggregators like kilo expose paid + free models side by side,
            # so we skip the paid model and keep probing for a free one.
            try:
                slot.unsupported_models.add(model)
            except Exception:  # noqa: BLE001
                pass

    if dead_key:
        slot.cooldown_until = time.time() + 3600.0
        slot.consecutive_failures = (getattr(slot, "consecutive_failures", 0) or 0) + 1
        logger.info("key %s marked dead (auth/payment) for %s", getattr(slot, "name", "?"), provider)
        return

    if passing:
        passing.sort(key=lambda x: x[1])
        models = [m for m, _ in passing]
        slot.discovered_models = models
        slot.preferred_model = models[0]
        slot.ewma_latency_ms = passing[0][1]
        try:
            slot.supported_models.update(models)
        except Exception:  # noqa: BLE001
            pass
        await _redis_set(cache_key, {"models": models, "latency": passing[0][1]}, ttl=900)
        logger.info("discovered %d free models for %s/%s (best=%s, %.0fms)", len(models), provider, getattr(slot, "name", "?"), models[0], passing[0][1])
    else:
        slot.discovered_models = []
        slot.cooldown_until = time.time() + 3600.0
        slot.consecutive_failures = (getattr(slot, "consecutive_failures", 0) or 0) + 1


async def run_discovery(squad: Any) -> None:
    """Run discovery across all pools/slots with bounded concurrency."""
    if squad is None:
        return
    sem = asyncio.Semaphore(6)

    async def worker(slot: Any) -> None:
        async with sem:
            try:
                await validate_slot(slot)
            except Exception as exc:  # noqa: BLE001
                logger.debug("discovery worker error: %s", exc)

    tasks = []
    pools = getattr(squad, "pools", {}) or {}
    for pool in pools.values():
        for slot in getattr(pool, "slots", []) or []:
            tasks.append(worker(slot))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def discovery_loop(squad: Any, interval_seconds: float = 900.0) -> None:
    while True:
        try:
            await run_discovery(squad)
        except Exception as exc:  # noqa: BLE001
            logger.debug("discovery loop error: %s", exc)
        await asyncio.sleep(interval_seconds)

async def hydrate_slots_from_redis(squad: Any) -> None:
    if squad is None:
        return
    pools = getattr(squad, "pools", {}) or {}
    for pool in pools.values():
        for slot in getattr(pool, "slots", []) or []:
            provider = getattr(slot, "provider", "")
            key = "supremeai:slot:" + provider + ":" + getattr(slot, "name", "")
            state = await _redis_get(key)
            if not isinstance(state, dict):
                continue
            try:
                if "cooldown_until" in state:
                    slot.cooldown_until = float(state["cooldown_until"])
                if "consecutive_failures" in state:
                    slot.consecutive_failures = int(state["consecutive_failures"])
                if "ewma_latency_ms" in state:
                    slot.ewma_latency_ms = float(state["ewma_latency_ms"])
                if "ewma_first_token_ms" in state:
                    slot.ewma_first_token_ms = float(state["ewma_first_token_ms"])
                if "discovered_models" in state:
                    slot.discovered_models = list(state["discovered_models"])
                if "preferred_model" in state:
                    slot.preferred_model = state["preferred_model"]
                if "supported_models" in state:
                    slot.supported_models = set(state["supported_models"])
                if "unsupported_models" in state:
                    slot.unsupported_models = set(state["unsupported_models"])
            except Exception:
                continue


async def persist_slot(slot: Any) -> None:
    provider = getattr(slot, "provider", "")
    key = "supremeai:slot:" + provider + ":" + getattr(slot, "name", "")
    state = {
        "cooldown_until": getattr(slot, "cooldown_until", 0.0),
        "consecutive_failures": getattr(slot, "consecutive_failures", 0),
        "ewma_latency_ms": getattr(slot, "ewma_latency_ms", 0.0),
        "ewma_first_token_ms": getattr(slot, "ewma_first_token_ms", 0.0),
        "discovered_models": getattr(slot, "discovered_models", []),
        "preferred_model": getattr(slot, "preferred_model", None),
        "supported_models": list(getattr(slot, "supported_models", set()) or []),
        "unsupported_models": list(getattr(slot, "unsupported_models", set()) or []),
    }
    await _redis_set(key, state, ttl=86400)

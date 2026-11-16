"""gateway/service/free_model_discovery.py — per-key free model discovery & micro-probe.

Implements the Dynamic Active Free Model Discovery plan at root level:
- query each provider's /models endpoint with the individual key
- filter free/usable models
- micro-probe with max_tokens=1 to verify real quota and measure latency
- store verified models on the KeySlot and mark dead keys in cooldown
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Tuple

import httpx

import json as _json
import os as _os

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
    "huggingface": "https://router.huggingface.co/hf-inference/v1",
    "sambanova": "https://api.sambanova.ai/v1",
    "kilo": "https://api.kilo.ai/api/gateway",
}


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
    elif provider == "openrouter":
        for m in (data.get("data", []) if isinstance(data, dict) else []):
            mid = m.get("id")
            pricing = m.get("pricing") or {}
            is_free = (
                (str(pricing.get("prompt", "")) == "0" and str(pricing.get("completion", "")) == "0")
                or (isinstance(mid, str) and mid.endswith(":free"))
            )
            if mid and is_free:
                ids.append(str(mid))
    else:
        for m in (data.get("data", []) if isinstance(data, dict) else []):
            mid = m.get("id")
            if mid:
                ids.append(str(mid))
    if provider == "kilo":
        # Kilo may expose an aggregator; accept any returned model ids.
        for m in (data.get("data", []) if isinstance(data, dict) else []):
            mid = m.get("id") or m.get("model") or m.get("name")
            if mid:
                ids.append(str(mid))
        # also support list responses
        if not ids and isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    ids.append(item)
                elif isinstance(item, dict):
                    mid = item.get("id") or item.get("model") or item.get("name")
                    if mid:
                        ids.append(str(mid))
        seen = set()
        out = []
        for mid in ids:
            if mid not in seen:
                seen.add(mid)
                out.append(mid)
        return out[:8]


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
    for model in ids[:3]:
        ok, latency, status = await _probe_model(provider, base_url, api_key, model)
        if ok:
            passing.append((model, latency))
            try:
                slot.supported_models.add(model)
            except Exception:  # noqa: BLE001
                pass
        else:
            if status in (401, 402, 403):
                dead_key = True
                break
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

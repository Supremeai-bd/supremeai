"""Exact chat response cache: Redis plus a bounded worker-local session cache.

Both layers use the same verified owner, tenant, session, selected model and
complete input. Never reuse legacy, prefix or similarity matches for private
inference: those stores cannot prove the full request scope.
"""

import asyncio
import hashlib
import json
import os
import threading
import time
from typing import Any

from cachetools import TTLCache
from core.monitoring.metrics_collector import metrics_collector, record_cache_access

from core.llm.token_budget import estimate_tokens
from core.messaging.event_bus import ErrorContext, ErrorEvent, error_event_bus
from core.monitoring.logging_config import logger
from core.swarm_pubsub import swarm_streamer

# Covered by the existing admin Redis cache purge (cache:*).
_EXACT_PREFIX = "cache:chat:exact:v2:"
_MAX_RESPONSE_BYTES = 50 * 1024
_CacheKey = tuple[str | None, str, str | None, str, str]
_session_cache: TTLCache = TTLCache(maxsize=500, ttl=600)
_session_lock = threading.Lock()


def _cache_key(
    prompt: str, model_name: str, session_id: str | None, user_id: str | None, tenant_id: str | None
) -> _CacheKey | None:
    if not isinstance(user_id, str) or not user_id.strip():
        return None
    # Distinguish no workspace claim from a workspace named like the owner.
    return tenant_id or None, user_id, session_id or None, model_name, hashlib.sha256(prompt.encode()).hexdigest()


def _redis_key(key: _CacheKey) -> str:
    encoded = json.dumps(key, separators=(",", ":")).encode()
    return _EXACT_PREFIX + hashlib.sha256(encoded).hexdigest()


def _get_redis_client():
    """Lazily configure Redis; local reads remain available without it."""
    import redis.asyncio as aioredis

    from core.config import settings

    if not settings.redis_url:
        return None
    return aioredis.from_url(
        str(settings.redis_url), decode_responses=True, socket_timeout=0.5, socket_connect_timeout=0.5
    )


class MultiLayerCache:
    def __init__(self):
        self.local_cache_hits = 0
        self.local_cache_misses = 0
        self._redis_cache = None
        self.cache_stats = {
            "exact_hits": 0,
            # Kept for existing telemetry consumers; these layers are retired.
            "semantic_hits": 0,
            "prefix_hits": 0,
            "session_hits": 0,
            "misses": 0,
            "tokens_saved": 0,
        }

    def _get_redis_cache(self):
        if self._redis_cache is None:
            self._redis_cache = _get_redis_client()
        return self._redis_cache

    def _record_redis_error(self, operation: str, exc: Exception) -> None:
        logger.warning(f"L1 chat cache {operation.lower()} failed: {exc}")
        error_event_bus.emit(
            ErrorEvent(
                module="multi_layer_cache",
                error_type=f"L1_{operation}_FAILED",
                message=str(exc)[:200],
                severity="WARNING",
                structured_context=ErrorContext(module="multi_layer_cache"),
            )
        )

    async def get(
        self,
        prompt: str,
        model_name: str,
        session_id: str | None = None,
        user_id: str | None = None,
        *,
        tenant_id: str | None = None,
    ) -> dict[str, Any] | None:
        key = _cache_key(prompt, model_name, session_id, user_id, tenant_id)
        if key is None:
            return None
        start = time.monotonic()
        response = None
        try:
            if redis_cache := self._get_redis_cache():
                response = await redis_cache.get(_redis_key(key))
        except Exception as exc:
            self._record_redis_error("READ", exc)

        layer, source = "exact", "L1_EXACT_CACHE"
        if not response and session_id:
            with _session_lock:
                response = _session_cache.get(key)
            if response:
                layer, source = "session", "L4_SESSION_CACHE"
                self.local_cache_hits += 1
            else:
                self.local_cache_misses += 1

        duration = time.monotonic() - start
        if response:
            self.cache_stats[f"{layer}_hits"] += 1
            self.cache_stats["tokens_saved"] += estimate_tokens(response)
        else:
            self.cache_stats["misses"] += 1
        await record_cache_access(bool(response))
        await metrics_collector.observe_histogram(
            "cache_access_duration_seconds",
            duration,
            {"layer": layer if response else "all", "result": "hit" if response else "miss"},
        )
        if response:
            return {"response": response, "source": source, "latency_ms": int(duration * 1000)}
        return None

    async def set(
        self,
        prompt: str,
        response: str,
        model_name: str,
        session_id: str | None = None,
        user_id: str | None = None,
        *,
        tenant_id: str | None = None,
    ) -> None:
        key = _cache_key(prompt, model_name, session_id, user_id, tenant_id)
        if key is None or not response or len(response.encode()) > _MAX_RESPONSE_BYTES:
            return
        start = time.monotonic()
        try:
            if redis_cache := self._get_redis_cache():
                await redis_cache.setex(_redis_key(key), self._exact_ttl(), response)
        except Exception as exc:
            self._record_redis_error("WRITE", exc)

        if session_id:
            with _session_lock:
                _session_cache[key] = response
        await metrics_collector.observe_histogram(
            "cache_total_set_duration_seconds", time.monotonic() - start, {}
        )

    def _exact_ttl(self) -> int:
        ttl = 3600
        if os.getenv("ENABLE_SMART_TTL", "").strip().lower() == "true":
            try:
                from core.learning.policies import smart_ttl

                hits = self.cache_stats["exact_hits"]
                total = hits + max(1, self.cache_stats["misses"])
                return smart_ttl(ttl, hit_rate=hits / total, reuse_count=hits)
            except Exception as exc:
                logger.debug(f"Smart cache TTL unavailable, using default: {exc}")
        return ttl

    async def get_cache_statistics(self) -> dict[str, Any]:
        stats = self.cache_stats
        hits = sum(stats[f"{layer}_hits"] for layer in ("exact", "session", "semantic", "prefix"))
        total = hits + stats["misses"]
        return {
            **stats,
            "total_accesses": total,
            "hit_rate_percentage": hits / total * 100 if total else 0,
            "local_cache_hits": self.local_cache_hits,
            "local_cache_misses": self.local_cache_misses,
            "avg_tokens_saved_per_hit": round(stats["tokens_saved"] / hits, 1) if hits else None,
        }


def invalidate_session_cache(tenant_id: str | None = None, *, all_scopes: bool = False) -> None:
    with _session_lock:
        if all_scopes:
            _session_cache.clear()
        elif isinstance(tenant_id, str) and tenant_id:
            for key in list(_session_cache):
                if (key[0] or key[1]) == tenant_id:
                    _session_cache.pop(key, None)


def _cache_invalidation_listener(event: ErrorEvent) -> None:
    if event.error_type in {"CIRCUIT_OPEN", "LLM_DOWN", "RATE_LIMIT_EXCEEDED"}:
        # An environment name or missing tenant is not an invalidation scope.
        invalidate_session_cache(event.context.get("tenant_id"))


error_event_bus.register_listener("*", _cache_invalidation_listener)


async def start_swarm_cache_invalidator() -> None:
    """Apply scoped invalidation messages to the worker-local cache."""
    try:
        async for raw in swarm_streamer.subscribe():
            try:
                message = json.loads(raw)
                event = message["type"]
                if event in {
                    "KNOWLEDGE_BASE_UPDATED",
                    "TENANT_CONFIG_CHANGED",
                    "TENANT_DELETED",
                    "SYSTEM_CIRCUIT_OPEN",
                    "CACHE_INVALIDATE_REQUESTED",
                }:
                    data = message.get("data", {})
                    invalidate_session_cache(
                        data.get("tenant_id"),
                        all_scopes=event == "CACHE_INVALIDATE_REQUESTED" and data.get("scope") == "global",
                    )
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                logger.warning(f"Invalid swarm cache event ignored: {exc}")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error(f"Swarm cache invalidator crashed: {exc}")


multi_layer_cache = MultiLayerCache()

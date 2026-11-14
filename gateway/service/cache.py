"""
gateway/service/cache.py — Multi-Tier L1 (In-Memory LRU) + L2 (Upstash Redis REST) Response Cache.

Caches deterministic (temperature=0, non-streaming) chat completions for sub-40ms
responses, with automatic failover across configured Upstash Redis REST clusters.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("supremeai.cache")

DEFAULT_TTL_SECONDS = int(os.getenv("RESPONSE_CACHE_TTL", "300"))
L1_MAX_SIZE = int(os.getenv("RESPONSE_CACHE_L1_SIZE", "1000"))

_UPSTASH_TIERS = [
    ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"),
    ("UPSTASH_REDIS_SECONDARY_REST_URL", "UPSTASH_REDIS_SECONDARY_REST_TOKEN"),
    ("UPSTASH_REDIS_TERTIARY_REST_URL", "UPSTASH_REDIS_TERTIARY_REST_TOKEN"),
    ("UPSTASH_REDIS_QUATERNARY_REST_URL", "UPSTASH_REDIS_QUATERNARY_REST_TOKEN"),
    ("UPSTASH_REDIS_QUINARY_REST_URL", "UPSTASH_REDIS_QUINARY_REST_TOKEN"),
]


class MultiTierResponseCache:
    """L1 in-memory LRU + L2 Upstash Redis REST cache with multi-cluster failover."""

    def __init__(self, max_l1_size: int = L1_MAX_SIZE, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.max_l1_size = max_l1_size
        self.ttl_seconds = ttl_seconds
        self._l1: OrderedDict[str, Tuple[float, Dict[str, Any]]] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(1.5, connect=0.8))
        return self._client

    def _active_redis_clusters(self) -> List[Tuple[str, str]]:
        clusters: List[Tuple[str, str]] = []
        for url_env, tok_env in _UPSTASH_TIERS:
            url = os.getenv(url_env, "").strip().rstrip("/")
            tok = os.getenv(tok_env, "").strip()
            if url.startswith("http") and len(tok) >= 8:
                clusters.append((url, tok))
        return clusters

    @staticmethod
    def is_cacheable(body: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> bool:
        """Only cache non-streaming, deterministic (temperature == 0) requests."""
        if body.get("stream"):
            return False
        temp = body.get("temperature")
        if temp is None or float(temp) != 0.0:
            return False
        if headers:
            cc = headers.get("cache-control", "").lower()
            if "no-cache" in cc or "no-store" in cc:
                return False
        return True

    @staticmethod
    def build_key(body: Dict[str, Any]) -> str:
        """Deterministic SHA-256 cache key from model, messages, and temperature."""
        canonical = {
            "model": body.get("model", "auto"),
            "messages": body.get("messages", []),
            "temperature": 0.0,
        }
        raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        return f"supremeai:resp:{digest}"

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        # 1. Check L1 LRU
        entry = self._l1.get(key)
        if entry is not None:
            expires_at, data = entry
            if expires_at > now:
                self._l1.move_to_end(key)
                self.hits += 1
                return data
            self._l1.pop(key, None)

        # 2. Check L2 Upstash Redis clusters
        clusters = self._active_redis_clusters()
        if clusters:
            client = self._get_client()
            for url, tok in clusters:
                try:
                    resp = await client.get(
                        f"{url}/get/{key}",
                        headers={"Authorization": f"Bearer {tok}"},
                    )
                    if resp.status_code == 200:
                        raw_val = resp.json().get("result")
                        if raw_val:
                            parsed = json.loads(raw_val)
                            self._set_l1(key, parsed, now + self.ttl_seconds)
                            self.hits += 1
                            return parsed
                        break  # Key not in primary cluster
                except Exception:
                    continue

        self.misses += 1
        return None

    def _set_l1(self, key: str, data: Dict[str, Any], expires_at: float) -> None:
        self._l1[key] = (expires_at, data)
        self._l1.move_to_end(key)
        while len(self._l1) > self.max_l1_size:
            self._l1.popitem(last=False)

    async def set(self, key: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        ttl_s = ttl if ttl is not None else self.ttl_seconds
        self._set_l1(key, data, time.time() + ttl_s)

        clusters = self._active_redis_clusters()
        if clusters:
            client = self._get_client()
            serialized = json.dumps(data, ensure_ascii=False)
            for url, tok in clusters:
                try:
                    resp = await client.post(
                        f"{url}/set/{key}?EX={ttl_s}",
                        content=serialized.encode("utf-8"),
                        headers={"Authorization": f"Bearer {tok}"},
                    )
                    if resp.status_code == 200:
                        return
                except Exception:
                    continue

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        return {
            "l1_size": len(self._l1),
            "l1_max_size": self.max_l1_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": round(self.hits / total, 4) if total > 0 else 0.0,
            "redis_clusters_configured": len(self._active_redis_clusters()),
        }


response_cache = MultiTierResponseCache()

"""Web-surface runtime controls: concurrency (S1), affinity (S2), tenant isolation (S4),
response cache (S6), and quality scoring (S8).

Defaults are loaded from ``config/web_surfaces.yaml`` (H1 SSOT) when PyYAML is
available, with safe built-in fallbacks so the relay remains stdlib-importable.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

_DEFAULT_CONCURRENCY: dict[str, int] = {"duck": 4, "gemini": 2}
_REFUSAL_MARKERS: tuple[str, ...] = (
    "i cannot fulfill this request",
    "as an ai language model",
    "access denied",
    "cloudflare",
    "captcha",
    "rate limit exceeded",
)


def load_surface_concurrency(config_path: Path | None = None) -> dict[str, int]:
    """Read per-engine max_concurrency from config/web_surfaces.yaml (H1)."""
    path = config_path or (Path(__file__).resolve().parents[1] / "config" / "web_surfaces.yaml")
    if not path.exists():
        return dict(_DEFAULT_CONCURRENCY)
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        surfaces = data.get("surfaces") or {}
        out: dict[str, int] = {}
        for name, spec in surfaces.items():
            if isinstance(spec, dict) and "max_concurrency" in spec:
                out[str(name)] = max(1, int(spec["max_concurrency"]))
        return out or dict(_DEFAULT_CONCURRENCY)
    except Exception:
        return dict(_DEFAULT_CONCURRENCY)


class EngineConcurrencyLimiter:
    """S1: Per-engine asyncio semaphore limiting concurrent in-flight requests."""

    def __init__(self, limits: dict[str, int] | None = None) -> None:
        self._limits = limits if limits is not None else load_surface_concurrency()
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._in_flight: dict[str, int] = {}

    def limit_for(self, engine: str) -> int:
        return self._limits.get(engine, 2)

    def in_flight(self, engine: str) -> int:
        return self._in_flight.get(engine, 0)

    def _sem(self, engine: str) -> asyncio.Semaphore:
        if engine not in self._semaphores:
            self._semaphores[engine] = asyncio.Semaphore(self.limit_for(engine))
        return self._semaphores[engine]

    @asynccontextmanager
    async def acquire(self, engine: str) -> AsyncIterator[None]:
        sem = self._sem(engine)
        await sem.acquire()
        self._in_flight[engine] = self._in_flight.get(engine, 0) + 1
        try:
            yield
        finally:
            self._in_flight[engine] = max(0, self._in_flight.get(engine, 1) - 1)
            sem.release()


class TenantSessionAffinity:
    """S2 + S4: Per-(tenant_id, session_id) engine affinity with TTL."""

    def __init__(self, ttl_s: float = 1800.0, max_entries: int = 2048) -> None:
        self._ttl_s = ttl_s
        self._max_entries = max_entries
        self._entries: OrderedDict[tuple[str, str], tuple[str, float]] = OrderedDict()

    def get(self, tenant_id: str, session_id: str, *, now: float | None = None) -> str | None:
        if not session_id:
            return None
        key = (tenant_id or "default", session_id)
        item = self._entries.get(key)
        if item is None:
            return None
        engine, expires_at = item
        ts = time.monotonic() if now is None else now
        if ts >= expires_at:
            self._entries.pop(key, None)
            return None
        self._entries.move_to_end(key)
        return engine

    def set(self, tenant_id: str, session_id: str, engine: str, *, now: float | None = None) -> None:
        if not session_id or not engine:
            return
        key = (tenant_id or "default", session_id)
        ts = time.monotonic() if now is None else now
        self._entries[key] = (engine, ts + self._ttl_s)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)


class TenantSemanticCache:
    """S6 + S4: Tenant-isolated TTL response cache."""

    def __init__(self, ttl_s: float = 300.0, max_entries: int = 1024) -> None:
        self._ttl_s = ttl_s
        self._max_entries = max_entries
        self._entries: OrderedDict[str, tuple[str, float]] = OrderedDict()

    @staticmethod
    def make_key(tenant_id: str, model: str, prompt: str) -> str:
        norm_prompt = " ".join((prompt or "").strip().lower().split())
        digest = hashlib.sha256(f"{tenant_id or 'default'}|{model}|{norm_prompt}".encode("utf-8")).hexdigest()
        return digest

    def get(self, tenant_id: str, model: str, prompt: str, *, now: float | None = None) -> str | None:
        key = self.make_key(tenant_id, model, prompt)
        item = self._entries.get(key)
        if item is None:
            return None
        value, expires_at = item
        ts = time.monotonic() if now is None else now
        if ts >= expires_at:
            self._entries.pop(key, None)
            return None
        self._entries.move_to_end(key)
        return value

    def set(self, tenant_id: str, model: str, prompt: str, response: str, *, now: float | None = None) -> None:
        if not response:
            return
        key = self.make_key(tenant_id, model, prompt)
        ts = time.monotonic() if now is None else now
        self._entries[key] = (response, ts + self._ttl_s)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)


def score_response_quality(text: str, *, min_chars: int = 8) -> float:
    """S8: Return a quality score in [0.0, 1.0] for a web-engine response."""
    if not text or not text.strip():
        return 0.0
    cleaned = text.strip()
    if len(cleaned) < min_chars:
        return 0.2
    lowered = cleaned.lower()
    if any(marker in lowered for marker in _REFUSAL_MARKERS):
        return 0.3
    return 1.0

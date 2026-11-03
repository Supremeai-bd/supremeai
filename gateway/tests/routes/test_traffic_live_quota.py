"""Upstash daily-quota contract tests for the /api/admin/traffic/live path.

Root cause (fleet-redis-quota): the old read path fired 30 sequential LRANGE
commands per dashboard poll; TrafficMonitor.tsx polled every 5s → ~518,000
commands/day, exhausting the 5-account Upstash federation (SCAN evidence:
traffic:live:* keys parked on the failover account). The fix: ONE EVAL per
poll (+ per-key fail-honest fallback), 30s dashboard cadence, 35-min retention.

These tests pin:
  1. exactly ONE eval command per /live poll (eval path healthy);
  2. zero lrange commands on the healthy path;
  3. per-key fallback fires when EVAL is unavailable (fail-honest, same shape);
  4. malformed EVAL results fall back instead of corrupting the response;
  5. source contracts: 35-min write retention + 30s frontend cadence.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import api.routes.traffic_monitor as traffic_module
from api.dependencies import get_current_admin, get_current_user_token
from core.app import app

client = TestClient(app)
ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}

BACKEND_ROOT = Path(__file__).resolve().parents[3]


class RecordingFakeRedis:
    """Minimal async stub recording every command (quota auditability)."""

    def __init__(self, data: dict[str, list[str]] | None = None) -> None:
        self._data: dict[str, list[str]] = data or {}
        self.eval_calls: list[tuple[str, int, tuple[str, ...]]] = []
        self.lrange_calls: list[tuple[str, int, int]] = []
        self.eval_raises = False
        self.eval_bad_shape = False

    async def eval(self, script: str, numkeys: int, *keys_and_args: str):
        self.eval_calls.append((script, numkeys, keys_and_args))
        if self.eval_raises:
            raise RuntimeError("EVAL unsupported by this client")
        if self.eval_bad_shape:
            return [None, "garbage"]
        keys = list(keys_and_args)[:numkeys]
        return [list(self._data.get(k, [])) for k in keys]

    async def lrange(self, key: str, start: int, end: int):
        self.lrange_calls.append((key, start, end))
        return list(self._data.get(key, []))


@pytest.fixture(autouse=True)
def override_admin_auth():
    app.dependency_overrides[get_current_user_token] = lambda: {
        "sub": "admin@supremeai.test",
        "role": "admin",
    }
    app.dependency_overrides[get_current_admin] = lambda: {
        "sub": "admin@supremeai.test",
        "role": "admin",
    }
    with patch("core.security.authentication.auth_middleware._decode_jwt") as mock_jwt:
        mock_jwt.return_value = {"sub": "admin@supremeai.test", "role": "admin"}
        yield
    app.dependency_overrides.pop(get_current_user_token, None)
    app.dependency_overrides.pop(get_current_admin, None)


def _seed_window(cur_minute: int) -> dict[str, list[str]]:
    """Seed the 30-minute window with known traffic payloads."""
    data: dict[str, list[str]] = {}
    items_by_offset = {0: 3, 1: 2, 2: 5}
    for offset, count in items_by_offset.items():
        key = f"traffic:live:{cur_minute - offset}"
        rows = []
        for i in range(count):
            status = 500 if (i == 0 and offset == 0) else 200
            rows.append(
                json.dumps(
                    {
                        "method": "GET",
                        "path": "/x",
                        "status": status,
                        "duration": 0.1 * (i + 1),
                        "error": None,
                    }
                )
            )
        data[key] = rows
    return data


def test_traffic_live_single_eval_command():
    """Healthy path: exactly ONE eval, ZERO lrange, correct aggregation."""
    for _ in range(3):  # retry on minute-boundary skew
        cur = int(time.time()) // 60
        fake = RecordingFakeRedis(_seed_window(cur))
        with patch.object(traffic_module.redis_manager, "_client", fake):
            resp = client.get("/api/admin/traffic/live", headers=ADMIN_HEADERS)
        if int(time.time()) // 60 != cur:
            continue  # minute rolled mid-request — reseed and retry
        break
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        "current_rps",
        "window_30min",
        "distribution",
        "error_rate_percent",
        "p95_latency_ms",
    }
    assert len(fake.eval_calls) == 1, "window must be read in ONE command"
    script, numkeys, keys = fake.eval_calls[0]
    assert numkeys == 30
    assert len(keys) == 30
    assert fake.lrange_calls == [], "healthy path must not fire per-key reads"
    # Aggregation: 10 sampled items total, 1 error, durations 0.1..0.5
    assert body["window_30min"][29] == 3
    assert body["window_30min"][28] == 2
    assert body["window_30min"][27] == 5
    assert sum(body["window_30min"]) == 10
    assert abs(body["error_rate_percent"] - 10.0) < 0.01
    assert body["current_rps"] == round(3 / 60.0, 2)


def test_traffic_live_eval_unavailable_falls_back_per_key():
    """EVAL unsupported → fail-honest per-key fallback, same shape."""
    cur = int(time.time()) // 60
    fake = RecordingFakeRedis(_seed_window(cur))
    fake.eval_raises = True
    with patch.object(traffic_module.redis_manager, "_client", fake):
        resp = client.get("/api/admin/traffic/live", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert len(fake.eval_calls) == 1
    assert len(fake.lrange_calls) == 30, "fallback must read the 30 keys"
    body = resp.json()
    assert len(body["window_30min"]) == 30
    assert sum(body["window_30min"]) == 10


def test_traffic_live_bad_eval_shape_falls_back():
    """Malformed EVAL result → fallback path, never a corrupt 200."""
    cur = int(time.time()) // 60
    fake = RecordingFakeRedis(_seed_window(cur))
    fake.eval_bad_shape = True
    with patch.object(traffic_module.redis_manager, "_client", fake):
        resp = client.get("/api/admin/traffic/live", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert len(fake.lrange_calls) == 30
    assert sum(resp.json()["window_30min"]) == 10


def test_traffic_live_no_redis_returns_empty():
    """Redis absent → 200 with zeroed metrics (existing contract)."""
    with patch.object(traffic_module.redis_manager, "_client", None):
        resp = client.get("/api/admin/traffic/live", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_rps"] == 0.0
    assert body["window_30min"] == [0] * 30


def test_middleware_write_retention_source_contract():
    """Minute-keys must expire within the 30-min read window + margin."""
    src = (BACKEND_ROOT / "core" / "observability" / "observability_middleware.py").read_text(
        encoding="utf-8"
    )
    assert "expire(minute_key, 2100)" in src, "retention must be 35min"
    assert "86400" not in src, "24h retention must not return (key bloat)"


def test_frontend_polling_cadence_source_contract():
    """TrafficMonitor must poll at 30s — 5s cadence was the quota burner."""
    tsx = (
        BACKEND_ROOT.parent
        / "frontend"
        / "src"
        / "commandcenter"
        / "modules"
        / "observe"
        / "TrafficMonitor.tsx"
    ).read_text(encoding="utf-8")
    assert "useTraffic(30_000)" in tsx
    assert "useTraffic(5_000)" not in tsx


def test_window_read_script_is_single_command():
    """The Lua window reader loops server-side over #KEYS with a single
    redis.call body — the whole 30-key window is ONE command regardless."""
    script = traffic_module._WINDOW_READ_SCRIPT
    assert "for i = 1, #KEYS" in script
    assert script.count("redis.call('LRANGE'") == 1

"""Relay latency ingest: seed, never overwrite, never claim health.

The pool ranks providers by latency, and every web engine's number was a
constant. The relay measures the truth per engine, so this module moves it — but
three limits keep it honest, and each one has a test here:

* it seeds only slots that have never been measured (a proxy must not overwrite
  a real observation);
* it never marks a session healthy (fast engine ≠ live cookie);
* a relay failure keeps the last known values and says so.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from gateway.service import web_engine_health as health  # noqa: E402


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _Client:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[str] = []

    async def get(self, url, **_kwargs):
        self.calls.append(url)
        if self.error:
            raise self.error
        return self.response


def _squad(**slots_by_provider):
    pools = {}
    for provider, latencies in slots_by_provider.items():
        pools[provider] = SimpleNamespace(
            slots=[SimpleNamespace(ewma_latency_ms=latency) for latency in latencies]
        )
    return SimpleNamespace(pools=pools)


def test_engine_map_covers_every_web_engine():
    mapping = health.engine_providers()
    assert mapping["duck"] == ("claude_web", "chatgpt_web")
    assert set(mapping["gemini-web"]) == {"gemini_v0_web", "ghost_gemini", "web_session"}


def test_parse_keeps_only_positive_numeric_latencies():
    document = {
        "data": [
            {"id": "duck", "latency_ms": 412.54},
            {"id": "gemini-web", "latency_ms": 0},
            {"id": "gemini-web", "latency_ms": "n/a"},
            {"id": "", "latency_ms": 5},
            "not-a-row",
        ]
    }
    assert health.parse_engine_latency(document) == {"duck": 412.5}


@pytest.mark.parametrize("payload", [None, [], {"data": "x"}, {"no": "data"}])
def test_parse_tolerates_malformed_payloads(payload):
    assert health.parse_engine_latency(payload) == {}


def test_seed_fills_only_unmeasured_slots():
    squad = _squad(claude_web=[0.0, 900.0], chatgpt_web=[0.0], gemini_v0_web=[0.0])
    seeded = health.seed_latency(squad, {"duck": 300.0, "gemini-web": 2500.0})
    assert seeded == 3
    assert [slot.ewma_latency_ms for slot in squad.pools["claude_web"].slots] == [300.0, 900.0]
    # A measured slot keeps its own evidence.
    assert health.seed_latency(squad, {"duck": 100.0}) == 0


def test_seed_never_touches_health_flags():
    slot = SimpleNamespace(ewma_latency_ms=0.0, cooldown_until=99.0, consecutive_failures=2)
    squad = SimpleNamespace(pools={"claude_web": SimpleNamespace(slots=[slot])})
    health.seed_latency(squad, {"duck": 250.0})
    assert (slot.cooldown_until, slot.consecutive_failures) == (99.0, 2)


def test_seed_ignores_unknown_engines_and_missing_squad():
    assert health.seed_latency(None, {"duck": 1.0}) == 0
    assert health.seed_latency(_squad(claude_web=[0.0]), {"unknown-engine": 1.0}) == 0


async def test_fetch_reads_models_and_returns_latency():
    client = _Client(_Response({"data": [{"id": "duck", "latency_ms": 321.0}]}))
    latencies = await health.fetch_engine_latency("https://relay.example.com/", client=client)
    assert latencies == {"duck": 321.0}
    assert client.calls == ["https://relay.example.com/models"]


async def test_fetch_keeps_state_on_http_error(caplog):
    client = _Client(_Response({}, status_code=503))
    assert await health.fetch_engine_latency("https://relay.example.com", client=client) == {}
    assert "503" in caplog.text


async def test_fetch_keeps_state_on_invalid_json(caplog):
    client = _Client(_Response(ValueError("bad json")))
    assert await health.fetch_engine_latency("https://relay.example.com", client=client) == {}
    assert "ValueError" in caplog.text


async def test_refresh_seeds_from_the_relay():
    squad = _squad(gemini_v0_web=[0.0])
    client = _Client(_Response({"data": [{"id": "gemini-web", "latency_ms": 1800.0}]}))
    latencies = await health.run_refresh(squad, client=client, base_url="https://relay.example.com")
    assert latencies == {"gemini-web": 1800.0}
    assert squad.pools["gemini_v0_web"].slots[0].ewma_latency_ms == 1800.0


async def test_refresh_deadline_is_reported_not_raised(monkeypatch, caplog):
    async def never(*_args, **_kwargs):
        await asyncio.sleep(3600)

    monkeypatch.setattr(health, "fetch_engine_latency", never)
    monkeypatch.setattr(health, "REFRESH_DEADLINE_S", 0.01)
    assert await health.run_refresh(_squad(), base_url="https://relay.example.com") == {}
    assert "exceeded" in caplog.text


async def test_loop_sleeps_between_passes(monkeypatch):
    """One pass per interval — pinned, because '30 minutes' is the contract."""
    passes: list[int] = []

    async def fake_refresh(*_args, **_kwargs):
        passes.append(1)
        return {}

    async def fake_sleep(seconds):
        assert seconds == health.ENGINE_REFRESH_S
        raise asyncio.CancelledError

    monkeypatch.setattr(health, "run_refresh", fake_refresh)
    monkeypatch.setattr(health.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await health.web_engine_health_loop(_squad())
    assert passes == [1]


def test_refresh_interval_is_thirty_minutes():
    assert health.ENGINE_REFRESH_S == 1800.0

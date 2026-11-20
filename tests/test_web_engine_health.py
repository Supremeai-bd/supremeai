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


# ── session evidence ────────────────────────────────────────────────────────
# An expired cookie is the failure this repo keeps paying for. The gateway must
# cool the slots behind a dead engine, and must never cool one on a guess.


def _slots_squad(*, cooldown_until: float = 0.0):
    """Squad with one slot per web provider; records every injury the pool reports."""
    reported: list[tuple[str, int]] = []

    class _Pool:
        def __init__(self, provider):
            self.provider = provider
            self.slots = [SimpleNamespace(cooldown_until=cooldown_until, ewma_latency_ms=0.0)]

        def report_injury(self, slot, status_code, latency_ms=0.0):
            reported.append((self.provider, status_code))
            slot.cooldown_until = 10_000.0

    pools = {
        provider: _Pool(provider)
        for providers in health.engine_providers().values()
        for provider in providers
    }
    return SimpleNamespace(pools=pools), reported


def test_parse_session_states_keeps_only_known_states():
    document = {
        "sessions": {
            "duck": {"state": "CHALLENGED"},
            "gemini": {"state": "EXPIRED"},
            "other": {"state": "OK"},
            "weird": {"state": "SOMETHING"},
            "broken": "not-a-dict",
        }
    }
    assert health.parse_session_states(document) == {
        "duck": "CHALLENGED",
        "gemini": "EXPIRED",
        "other": "OK",
    }


@pytest.mark.parametrize("payload", [None, {}, {"sessions": []}, {"sessions": "x"}])
def test_parse_session_states_tolerates_malformed_payloads(payload):
    assert health.parse_session_states(payload) == {}


def test_expired_session_cools_every_provider_behind_the_engine():
    squad, reported = _slots_squad()
    cooled = health.apply_session_states(squad, {"gemini-web": "EXPIRED"})
    assert cooled == 3, "gemini-web backs gemini_v0_web, ghost_gemini and web_session"
    assert all(status == 403 for _provider, status in reported)


def test_challenged_session_uses_the_rate_limit_cooldown():
    squad, reported = _slots_squad()
    health.apply_session_states(squad, {"duck": "CHALLENGED"})
    assert reported == [("claude_web", 429), ("chatgpt_web", 429)]


@pytest.mark.parametrize("state", ["OK", "UNKNOWN"])
def test_a_healthy_or_unknown_session_never_cools_anything(state):
    """'We could not tell' must not take a working surface out of rotation."""
    squad, reported = _slots_squad()
    assert health.apply_session_states(squad, {"gemini-web": state}) == 0
    assert reported == []


def test_an_already_cooled_slot_is_not_re_injured():
    squad, reported = _slots_squad(cooldown_until=9_999.0)
    assert health.apply_session_states(squad, {"gemini-web": "EXPIRED"}, now=1_000.0) == 0
    assert reported == [], "re-injuring every pass would keep resetting the cooldown clock"


async def test_fetch_session_states_reads_health():
    client = _Client(_Response({"sessions": {"gemini-web": {"state": "EXPIRED"}}}))
    states = await health.fetch_session_states("https://relay.example.com/", client=client)
    assert states == {"gemini-web": "EXPIRED"}
    assert client.calls == ["https://relay.example.com/health"]


async def test_fetch_session_states_keeps_state_on_error(caplog):
    client = _Client(_Response({}, status_code=502))
    assert await health.fetch_session_states("https://relay.example.com", client=client) == {}
    assert "502" in caplog.text


async def test_session_refresh_applies_what_it_reads():
    squad, reported = _slots_squad()
    client = _Client(_Response({"sessions": {"duck": {"state": "EXPIRED"}}}))
    states = await health.run_session_refresh(
        squad, client=client, base_url="https://relay.example.com"
    )
    assert states == {"duck": "EXPIRED"}
    assert reported == [("claude_web", 403), ("chatgpt_web", 403)]


async def test_loop_refreshes_latency_and_sessions_each_pass(monkeypatch):
    calls: list[str] = []

    async def fake_latency(*_args, **_kwargs):
        calls.append("latency")
        return {}

    async def fake_sessions(*_args, **_kwargs):
        calls.append("sessions")
        return {}

    async def fake_sleep(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(health, "run_refresh", fake_latency)
    monkeypatch.setattr(health, "run_session_refresh", fake_sessions)
    monkeypatch.setattr(health.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await health.web_engine_health_loop(_squad())
    assert calls == ["latency", "sessions"]


# --- S3: the operator's switch ---------------------------------------------
# A kill switch that cannot be un-thrown is not a switch, and one that fakes a
# credential failure is a lie in the stats. These pin both halves: parking is
# separate from injury (no error counters), and release restores exactly what
# was there before — or leaves a newer injury alone.


import time  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_parks():
    health.reset_disabled_parks()
    yield
    health.reset_disabled_parks()


def test_a_disabled_engine_wins_over_its_last_outcome():
    states = health.parse_session_states(
        {"sessions": {"duck": {"state": "OK", "disabled": True}}}
    )
    assert states == {"duck": health.DISABLED_STATE}


def test_an_enabled_engine_keeps_its_outcome():
    states = health.parse_session_states(
        {"sessions": {"duck": {"state": "OK", "disabled": False}}}
    )
    assert states == {"duck": "OK"}


def _squad_with_slots(**slots):
    squad = SimpleNamespace(pools={})
    for provider, names in slots.items():
        pool = SimpleNamespace(slots=[])
        for name in names:
            slot = SimpleNamespace(name=name, cooldown_until=0.0, total_errors=0, consecutive_failures=0)
            pool.slots.append(slot)
            pool.report_injury = lambda _slot, _status, _pool=pool: None
        squad.pools[provider] = pool
    return squad


def test_disabling_parks_the_slots_without_recording_a_failure():
    squad = _squad_with_slots(claude_web=["relay-a"], chatgpt_web=["relay-b"])
    health.apply_session_states(squad, {"duck": health.DISABLED_STATE})

    for provider in ("claude_web", "chatgpt_web"):
        slot = squad.pools[provider].slots[0]
        assert slot.cooldown_until > time.time(), "a switched-off engine must not be routed to"
        assert slot.total_errors == 0, "an operator decision is not a failed request"
        assert slot.consecutive_failures == 0

    assert health.parked_slots() == (("chatgpt_web", "relay-b"), ("claude_web", "relay-a"))


def test_parking_twice_does_not_extend_the_window():
    squad = _squad_with_slots(claude_web=["relay-a"])
    health.apply_session_states(squad, {"duck": health.DISABLED_STATE})
    parked_until = squad.pools["claude_web"].slots[0].cooldown_until

    health.apply_session_states(squad, {"duck": health.DISABLED_STATE})
    assert squad.pools["claude_web"].slots[0].cooldown_until == parked_until


def test_re_enabling_releases_exactly_what_was_parked():
    squad = _squad_with_slots(claude_web=["relay-a"])
    slot = squad.pools["claude_web"].slots[0]
    slot.cooldown_until = 123.0

    health.apply_session_states(squad, {"duck": health.DISABLED_STATE})
    assert slot.cooldown_until > 123.0

    health.apply_session_states(squad, {"duck": "OK"})
    assert slot.cooldown_until == 123.0, "release must restore the previous cooldown, not zero it"
    assert health.parked_slots() == ()


def test_a_real_injury_while_parked_survives_re_enabling():
    """The switch must not launder an auth cooldown that arrived in the meantime."""
    squad = _squad_with_slots(gemini_v0_web=["relay-g"])
    slot = squad.pools["gemini_v0_web"].slots[0]

    health.apply_session_states(squad, {"gemini-web": health.DISABLED_STATE})
    injury = time.time() + 900
    slot.cooldown_until = injury

    health.apply_session_states(squad, {"gemini-web": "OK"})
    assert slot.cooldown_until == injury


def test_a_disabled_engine_is_never_also_injured():
    squad = _squad_with_slots(claude_web=["relay-a"])
    cooled = health.apply_session_states(
        squad, {"duck": health.DISABLED_STATE}
    )
    assert cooled == 0


def test_fetch_session_states_reads_the_switch():
    assert health.parse_session_states(
        {"sessions": {"gemini-web": {"state": "UNKNOWN", "disabled": True}, "duck": {"state": "OK"}}}
    ) == {"gemini-web": health.DISABLED_STATE, "duck": "OK"}

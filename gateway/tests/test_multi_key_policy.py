"""Multi-key policy: N independent client credentials with N budgets.

Context: the "give every client its own key" plan was not expressible before
2026-11-19. Two structural blockers, both removed here:

1. **The secret env name was derived from `owner`** (`SUPREMEAI_API_KEY_<OWNER>`),
   so two entries with the same owner collided on one variable and the second
   key silently never loaded. Keys may now declare `env` explicitly, and a
   duplicate env name is a hard config error instead of a silent skip.
2. **`rate_limit` was global**, and the limiter buckets by owner label — so
   every authenticated caller drained the same window and one noisy client
   could 429 the whole fleet. A key may now declare `rate_limit`, and the
   gateway applies that owner's limiter instead of the global one.

The tests below pin both, plus the header contract (`X-RateLimit-Limit` must
describe the budget that actually decided).
"""

from __future__ import annotations

import json

import pytest

from gateway.config import ConfigError, parse_routing_policy
from gateway.main import build_key_limiters, create_app
from gateway.provider_chain import AttemptResult


def _policy(api_keys: dict, *, global_max: int = 100) -> dict:
    return {
        "schema_version": "gateway-routing/1",
        "chains": {"auto": [{"provider": "groq", "model": "llama-3.1-8b-instant"}]},
        "default_chain": "auto",
        "rate_limit": {"window_seconds": 60, "max_requests": global_max},
        "api_keys": api_keys,
    }


SIX_KEYS = {
    f"supremeai-key-client-{i:04d}": {
        "owner": f"client-{i}",
        "scopes": ["chat"],
        "env": f"SUPREMEAI_API_KEY_CLIENT_{i}",
        **({"rate_limit": {"max_requests": i}} if i <= 2 else {}),
    }
    for i in range(1, 7)
}
SIX_ENV = {f"SUPREMEAI_API_KEY_CLIENT_{i}": f"secret-{i}" for i in range(1, 7)}


# --- config plane ----------------------------------------------------------


def test_six_keys_load_with_independent_identities():
    cfg = parse_routing_policy(_policy(SIX_KEYS), env=SIX_ENV)
    assert len(cfg.api_keys) == 6
    assert {r.owner for r in cfg.api_keys.values()} == {f"client-{i}" for i in range(1, 7)}
    assert cfg.api_keys["supremeai-key-client-0001"].env == "SUPREMEAI_API_KEY_CLIENT_1"
    assert cfg.api_keys["supremeai-key-client-0001"].max_requests == 1
    assert cfg.api_keys["supremeai-key-client-0003"].max_requests is None


def test_owner_collision_without_env_is_a_hard_error():
    """The old silent-skip foot-gun: two keys, one derived env name."""
    policy = _policy(
        {
            "supremeai-key-dup-0000000001": {"owner": "client-1", "scopes": ["chat"]},
            "supremeai-key-dup-0000000002": {"owner": "client-1", "scopes": ["chat"]},
        }
    )
    with pytest.raises(ConfigError, match="claimed by two entries"):
        parse_routing_policy(policy, env={"SUPREMEAI_API_KEY_CLIENT_1": "x"})


def test_explicit_env_lets_one_owner_hold_two_keys():
    policy = _policy(
        {
            "supremeai-key-dup-0000000001": {
                "owner": "client-1", "scopes": ["chat"],
                "env": "SUPREMEAI_API_KEY_CLIENT_1", "rate_limit": {"max_requests": 5},
            },
            "supremeai-key-dup-0000000002": {
                "owner": "client-1", "scopes": ["chat"],
                "env": "SUPREMEAI_API_KEY_CLIENT_1B", "rate_limit": {"max_requests": 9},
            },
        }
    )
    cfg = parse_routing_policy(policy, env={"SUPREMEAI_API_KEY_CLIENT_1": "a",
                                           "SUPREMEAI_API_KEY_CLIENT_1B": "b"})
    assert cfg.api_keys["supremeai-key-dup-0000000001"].max_requests == 5
    assert cfg.api_keys["supremeai-key-dup-0000000002"].max_requests == 9


def test_missing_key_material_still_skips_the_entry():
    env = dict(SIX_ENV)
    env.pop("SUPREMEAI_API_KEY_CLIENT_6")
    cfg = parse_routing_policy(_policy(SIX_KEYS), env=env)
    assert "supremeai-key-client-0006" not in cfg.api_keys
    assert len(cfg.api_keys) == 5


@pytest.mark.parametrize(
    "meta",
    [
        {"owner": "c", "scopes": ["chat"], "env": "CLIENT_KEY_1"},          # bad prefix
        {"owner": "c", "scopes": ["chat"], "rate_limit": {"max_requests": 0}},
        {"owner": "c", "scopes": ["chat"], "rate_limit": {"burst": 3}},     # unknown field
        {"owner": "c", "scopes": ["chat"], "value": "secret"},              # never inline
    ],
)
def test_invalid_key_metadata_fails_closed(meta):
    policy = _policy({"supremeai-key-bad-0000000001": meta})
    with pytest.raises(ConfigError):
        parse_routing_policy(policy, env={"SUPREMEAI_API_KEY_C": "x"})


def test_limiter_registry_covers_only_owners_with_a_budget():
    cfg = parse_routing_policy(_policy(SIX_KEYS), env=SIX_ENV)
    limiters = build_key_limiters(cfg)
    assert set(limiters) == {"client-1", "client-2"}
    assert limiters["client-1"].max_requests == 1
    assert limiters["client-2"].max_requests == 2
    assert limiters["client-1"].window_s == 60  # global window reused


# --- request plane ---------------------------------------------------------


def _app(monkeypatch, api_keys: dict, *, global_max: int = 100, env: dict | None = None):
    monkeypatch.setenv("SUPREMEAI_GUEST_DAILY_MAX", "0")
    cfg = parse_routing_policy(_policy(api_keys, global_max=global_max), env=env or SIX_ENV)

    async def attempt(endpoint, payload):
        return AttemptResult(
            endpoint, 200, {},
            json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode(), 1,
        )

    from fastapi.testclient import TestClient

    return TestClient(create_app(cfg, attempt_fn=attempt))


def _call(client, key: str):
    return client.post(
        "/v1/chat/completions",
        json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
        headers={"x-supremeai-key": key},
    )


def test_one_owner_budget_does_not_drain_another(monkeypatch):
    client = _app(monkeypatch, SIX_KEYS)

    first = _call(client, "supremeai-key-client-0001")     # budget: 1/window
    assert first.status_code == 200
    assert first.headers["X-RateLimit-Limit"] == "1"
    assert _call(client, "supremeai-key-client-0001").status_code == 429

    # client-2 has its own independent budget (2/window) and is unaffected.
    assert _call(client, "supremeai-key-client-0002").status_code == 200
    assert _call(client, "supremeai-key-client-0002").status_code == 200
    assert _call(client, "supremeai-key-client-0002").status_code == 429


def test_key_without_budget_falls_back_to_the_global_window(monkeypatch):
    client = _app(monkeypatch, SIX_KEYS, global_max=2)
    key = "supremeai-key-client-0003"  # no rate_limit declared
    first = _call(client, key)
    assert first.status_code == 200
    assert first.headers["X-RateLimit-Limit"] == "2"
    assert _call(client, key).status_code == 200
    assert _call(client, key).status_code == 429


def test_429_body_reports_the_budget_that_rejected(monkeypatch):
    client = _app(monkeypatch, SIX_KEYS)
    key = "supremeai-key-client-0001"
    _call(client, key)
    rejected = _call(client, key)
    assert rejected.status_code == 429
    assert rejected.headers["X-RateLimit-Limit"] == "1"
    assert "1 requests per 60s window" in rejected.json()["error"]["message"]
    assert rejected.headers["Retry-After"]

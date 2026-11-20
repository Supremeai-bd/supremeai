"""The approval tooling must produce what the gateway actually accepts.

`scripts/ops/free_route_policy_tool.py` re-implements the fingerprint instead of
importing it, so it can run where the gateway's dependencies are not installed
(CI guards run without fastapi). That duplication is only safe if drift fails
loudly — hence the equality test below, which compares the tool's tag with
`free_route_policy.credential_identity()` for the same inputs.

The rest pins the refusals an operator will hit: an http relay can never be
approved, a placeholder model cannot be approved, and a provider that is not a
vision provider cannot carry `vision_models`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ops"))

import free_route_policy_tool as tool  # noqa: E402

HMAC_KEY = "ab" * 32
CREDENTIAL = "cookie-bundle-value"
BASE = "https://relay.example.com"


def live_evidence(engine="duck", **kwargs):
    """Evidence block for a relay that just confirmed the engine."""
    return tool.make_evidence(engine, **kwargs)


@pytest.fixture
def minted():
    return tool.build_entry(
        provider="claude_web",
        base_url=BASE,
        credential=CREDENTIAL,
        models=["duck-claude"],
        vision_models=[],
        ttl_hours=24,
        hmac_key_hex=HMAC_KEY,
        evidence=live_evidence(),
    )


def test_fingerprint_matches_the_gateway_implementation(monkeypatch):
    """The duplication spoken about in the module docstring, pinned."""
    monkeypatch.setenv("SUPREMEAI_FREE_ROUTE_HMAC_KEY", HMAC_KEY)
    from gateway.service.free_route_policy import credential_identity

    identity = credential_identity("claude_web", BASE, CREDENTIAL)
    assert identity is not None, "gateway rejected a 64-hex HMAC key"
    assert identity[2] == tool.fingerprint("claude_web", BASE, CREDENTIAL, HMAC_KEY)


def test_the_gateway_parser_accepts_the_minted_policy(minted):
    from gateway.service.free_route_policy import _policy

    parsed = _policy(json.dumps([minted]))
    assert len(parsed) == 1, "the gateway would have silently approved nothing"
    (provider, base_url, _tag), (expiry, models, vision, evidence) = next(iter(parsed.items()))
    assert provider == "claude_web"
    assert base_url == BASE
    assert models == ("duck-claude",)
    assert vision == ()
    assert evidence is not None and evidence.engine == "duck"


def test_secret_never_appears_in_the_output(minted):
    rendered = json.dumps(minted)
    assert CREDENTIAL not in rendered
    assert HMAC_KEY not in rendered


@pytest.mark.parametrize(
    ("base_url", "reason"),
    [
        ("http://127.0.0.1:8788", "https"),
        ("https://user:pw@relay.example.com", "not an approvable"),
        ("https://relay.example.com?x=1", "not an approvable"),
        ("", "not an approvable"),
    ],
)
def test_unapprovable_base_urls_are_refused_with_a_reason(base_url, reason):
    with pytest.raises(tool.PolicyError) as excinfo:
        tool.https_base(base_url)
    assert reason in str(excinfo.value)


@pytest.mark.parametrize(
    ("models", "vision", "provider", "reason"),
    [
        ([], [], "claude_web", "at least one concrete model"),
        (["auto"], [], "claude_web", "placeholder"),
        (["duck-claude"], ["gemini-web"], "claude_web", "not in models"),
        (["duck-claude"], ["duck-claude"], "claude_web", "cannot carry vision_models"),
        (["glm-5"], [], "kilo", ":free"),
        (["duck-claude"], [], "Bad-Name", "[a-z0-9_]+"),
    ],
)
def test_rules_the_parser_enforces_are_refused_early(models, vision, provider, reason):
    with pytest.raises(tool.PolicyError) as excinfo:
        tool.build_entry(
            provider=provider,
            base_url=BASE,
            credential=CREDENTIAL,
            models=models,
            vision_models=vision,
            ttl_hours=24,
            hmac_key_hex=HMAC_KEY,
            evidence=live_evidence(),
        )
    assert reason in str(excinfo.value)


def test_merge_replaces_the_same_identity_and_keeps_the_rest(minted):
    other = {"provider": "kilo", "base_url": "https://a.example.com", "models": ["x:free"]}
    merged = tool.merge_policies(json.dumps([other, minted | {"models": ["old"]}]), [minted])
    assert len(merged) == 2
    assert [entry["models"] for entry in merged if entry["provider"] == "claude_web"] == [["duck-claude"]]


def test_merge_rejects_a_corrupt_existing_policy():
    with pytest.raises(tool.PolicyError):
        tool.merge_policies("{not json", [])


def test_expiry_is_timezone_aware(minted):
    from datetime import datetime

    assert datetime.fromisoformat(minted["expires_at"]).tzinfo is not None


def test_check_reports_missing_and_expired(monkeypatch):
    monkeypatch.delenv("SUPREMEAI_FREE_ROUTE_POLICY", raising=False)
    lines = tool.check_approvals("", ["claude_web"])
    assert lines == [
        f"MISSING  claude_web: no approval entry in {tool.POLICY_ENV} (web slot: mint with --from-relay)"
    ]


def test_self_test_passes():
    assert tool._self_test() == 0


def test_main_refuses_without_an_hmac_key(monkeypatch, capsys):
    monkeypatch.delenv(tool.HMAC_KEY_ENV, raising=False)
    monkeypatch.setenv("RELAY_CREDENTIAL", CREDENTIAL)
    code = tool.main(["--provider", "claude_web", "--base-url", BASE,
                      "--credential-env", "RELAY_CREDENTIAL", "--models", "duck-claude"])
    assert code == 2
    assert "nothing minted" in capsys.readouterr().err


def test_main_mints_parseable_json(monkeypatch, capsys):
    monkeypatch.setenv(tool.HMAC_KEY_ENV, HMAC_KEY)
    monkeypatch.setenv("RELAY_CREDENTIAL", CREDENTIAL)
    monkeypatch.setattr(tool, "fetch_relay_health", lambda *_a, **_k: {"duck": {"state": "OK"}})
    code = tool.main(["--provider", "claude_web", "--base-url", BASE, "--from-relay",
                      "--credential-env", "RELAY_CREDENTIAL", "--models", "duck-claude"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["provider"] == "claude_web"
    assert payload[0]["evidence"]["engine"] == "duck"
    assert CREDENTIAL not in json.dumps(payload)


# --- B5: a web slot is approved on evidence, not on a promise ---------------
# A catalog provider proves it is free with a `:free` model. A web slot has no
# catalog — it is a browser session — so the only proof is the relay that holds
# the session. These tests pin that an approval cannot be minted (or keep
# serving) without a recent OK reading, and that one unproven slot does not take
# the rest of the policy down with it.

from datetime import datetime, timedelta, timezone  # noqa: E402

import urllib.error  # noqa: E402


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _opener(body: bytes = b"{}", *, error: Exception | None = None):
    def open_url(request, timeout=None):  # noqa: ARG001 - mirrors urlopen's signature
        if error is not None:
            raise error
        return _FakeResponse(body)

    return open_url


def test_engine_ids_match_the_gateway_mapping():
    """The tool duplicates the engine map to stay dependency-free; drift fails here."""
    from gateway.service.providers.web_engines import WEB_ENGINES_BY_PROVIDER

    assert tool.WEB_ENGINE_IDS == {
        provider: engine.engine for provider, engine in WEB_ENGINES_BY_PROVIDER.items()
    }


def test_a_web_slot_cannot_be_minted_on_a_promise():
    with pytest.raises(tool.PolicyError, match="--from-relay"):
        tool.build_entry(
            provider="claude_web",
            base_url=BASE,
            credential=CREDENTIAL,
            models=["duck-claude"],
            vision_models=[],
            ttl_hours=24,
            hmac_key_hex=HMAC_KEY,
        )


def test_evidence_from_the_wrong_engine_cannot_approve_a_slot():
    """`claude_web` routes to `duck`; a healthy gemini session proves nothing about it."""
    with pytest.raises(tool.PolicyError, match="routes to `duck`"):
        tool.build_entry(
            provider="claude_web",
            base_url=BASE,
            credential=CREDENTIAL,
            models=["duck-claude"],
            vision_models=[],
            ttl_hours=24,
            hmac_key_hex=HMAC_KEY,
            evidence=live_evidence("gemini-web"),
        )


def test_stale_evidence_is_refused_at_mint_time():
    aged = live_evidence(observed_at=datetime.now(timezone.utc) - timedelta(hours=7))
    with pytest.raises(tool.PolicyError, match="7.0h old"):
        tool.build_entry(
            provider="claude_web",
            base_url=BASE,
            credential=CREDENTIAL,
            models=["duck-claude"],
            vision_models=[],
            ttl_hours=24,
            hmac_key_hex=HMAC_KEY,
            evidence=aged,
        )


def test_evidence_for_uses_the_relays_clock_not_the_mint_clock():
    """`observed_at` is when the relay confirmed the session, not when we ran the tool."""
    now = datetime.now(timezone.utc)
    sessions = {"duck": {"state": "OK", "updated_at": (now - timedelta(hours=5)).timestamp()}}
    evidence = tool.evidence_for("claude_web", sessions, now=now)
    observed = datetime.fromisoformat(evidence["observed_at"])
    assert 4.9 < (now - observed).total_seconds() / 3600 < 5.1
    assert evidence["engine"] == "duck" and evidence["state"] == "OK"


@pytest.mark.parametrize("state", ["EXPIRED", "CHALLENGED", "UNKNOWN"])
def test_evidence_for_refuses_a_surface_that_is_not_ok(state):
    with pytest.raises(tool.PolicyError, match="only a live OK surface"):
        tool.evidence_for("claude_web", {"duck": {"state": state}})


def test_evidence_for_refuses_an_engine_the_relay_never_mentioned():
    with pytest.raises(tool.PolicyError, match="no `duck` session"):
        tool.evidence_for("claude_web", {"gemini-web": {"state": "OK"}})


def test_evidence_does_not_apply_to_a_catalog_provider():
    with pytest.raises(tool.PolicyError, match="not a web slot"):
        tool.evidence_for("kilo", {"duck": {"state": "OK"}})


def test_fetch_relay_health_refuses_a_localhost_relay():
    with pytest.raises(tool.PolicyError, match="https"):
        tool.fetch_relay_health("http://127.0.0.1:8788")


def test_fetch_relay_health_reports_http_errors():
    error = urllib.error.HTTPError(BASE, 503, "down", {}, None)
    with pytest.raises(tool.PolicyError, match="HTTP 503"):
        tool.fetch_relay_health(BASE, opener=_opener(error=error))


def test_fetch_relay_health_reports_a_body_that_is_not_json():
    with pytest.raises(tool.PolicyError, match="not JSON"):
        tool.fetch_relay_health(BASE, opener=_opener(b"<html>no</html>"))


def test_fetch_relay_health_requires_session_evidence():
    with pytest.raises(tool.PolicyError, match="no session evidence"):
        tool.fetch_relay_health(BASE, opener=_opener(b'{"status": "ok"}'))


def test_fetch_relay_health_parses_the_sessions_block():
    body = json.dumps({"sessions": {"duck": {"state": "OK"}, "junk": 3}}).encode()
    sessions = tool.fetch_relay_health(BASE, opener=_opener(body))
    assert sessions == {"duck": {"state": "OK"}}


def test_the_gateway_drops_only_the_unproven_entry(monkeypatch):
    """One slot without evidence must not disable the providers that never needed it."""
    from gateway.service.free_route_policy import _policy, approved_route

    monkeypatch.setenv(tool.HMAC_KEY_ENV, HMAC_KEY)
    kilo = tool.build_entry("kilo", "https://kilo.example.com", "k", ["glm-5:free"], [], 24, HMAC_KEY)
    unproven = {
        key: value
        for key, value in tool.build_entry(
            "claude_web", BASE, CREDENTIAL, ["duck-claude"], [], 24, HMAC_KEY, evidence=live_evidence()
        ).items()
        if key != "evidence"
    }
    monkeypatch.setenv(tool.POLICY_ENV, json.dumps([unproven, kilo]))
    parsed = _policy(json.dumps([unproven, kilo]))
    assert [identity[0] for identity in parsed] == ["kilo"]
    assert approved_route("claude_web", BASE, CREDENTIAL) is None
    assert approved_route("kilo", "https://kilo.example.com", "k") is not None


def test_the_gateway_stops_serving_when_evidence_ages_out(monkeypatch):
    """The approval is still in date; the session it was approving is not."""
    from gateway.service.free_route_policy import approved_route

    monkeypatch.setenv(tool.HMAC_KEY_ENV, HMAC_KEY)
    minted = tool.build_entry(
        "claude_web", BASE, CREDENTIAL, ["duck-claude"], [], 72, HMAC_KEY, evidence=live_evidence()
    )
    monkeypatch.setenv(tool.POLICY_ENV, json.dumps([minted]))
    assert approved_route("claude_web", BASE, CREDENTIAL) is not None

    aged = minted | {
        "evidence": minted["evidence"]
        | {"observed_at": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat()}
    }
    monkeypatch.setenv(tool.POLICY_ENV, json.dumps([aged]))
    assert approved_route("claude_web", BASE, CREDENTIAL) is None


def test_check_reports_stale_evidence(minted):
    aged = minted | {
        "evidence": minted["evidence"]
        | {"observed_at": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat()}
    }
    (line,) = tool.check_approvals(json.dumps([aged]), ["claude_web"])
    assert line.startswith("STALE"), line
    assert "duck OK" in line

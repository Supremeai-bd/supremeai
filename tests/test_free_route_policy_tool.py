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
    (provider, base_url, _tag), (expiry, models, vision) = next(iter(parsed.items()))
    assert provider == "claude_web"
    assert base_url == BASE
    assert models == ("duck-claude",)
    assert vision == ()


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
    assert lines == [f"MISSING  claude_web: no approval entry in {tool.POLICY_ENV}"]


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
    code = tool.main(["--provider", "claude_web", "--base-url", BASE,
                      "--credential-env", "RELAY_CREDENTIAL", "--models", "duck-claude"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["provider"] == "claude_web"
    assert CREDENTIAL not in json.dumps(payload)

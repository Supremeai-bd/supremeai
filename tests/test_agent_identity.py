"""Tests for scripts/agents/agent_identity.py — #3277 slot-derived identity.

Verifies:
1. App-bot login → leased lane-slot parsing (supremeai-coder-1-bot[bot] → coder-1).
2. resolve_agent_identity() Step 1.5: bot-token recovery of the slot identity
   when the CAS branch already exists (identity.json rewrite, NO new index).
3. Fresh CAS claim of the expected slot branch when it does not exist yet.
4. Backwards-compatible gap-fill fallback for non-bot/unknown tokens.
5. Gap-fill fallback when the bot's CAS claim loses a race.
6. _authenticated_login(): gh CLI success and no-token None.

All tests isolate the machine-local identity file into tmp_path so the real
~/.supremeai/identity.json is never touched.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.agents import agent_identity
from scripts.agents.agent_identity import (
    AgentIdentity,
    _authenticated_login,
    _bot_slot_from_login,
    resolve_agent_identity,
)


@pytest.fixture()
def isolated_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point IDENTITY_DIR/IDENTITY_FILE into tmp_path for the duration of a test."""
    idir = tmp_path / ".supremeai"
    ifile = idir / "identity.json"
    monkeypatch.setattr(agent_identity, "IDENTITY_DIR", idir)
    monkeypatch.setattr(agent_identity, "IDENTITY_FILE", ifile)
    return ifile


# ─────────────────── 1. bot-login → slot parsing ───────────────────
@pytest.mark.parametrize(
    ("login", "expected"),
    [
        ("supremeai-coder-1-bot[bot]", "coder-1"),
        ("supremeai-coder-7-bot[bot]", "coder-7"),
        ("supremeai-ci-fixer-2-bot[bot]", "ci-fixer-2"),
        ("supremeai-coder-1-bot", "coder-1"),  # App-served login without suffix
    ],
)
def test_bot_slot_from_login_parses_app_bot(login: str, expected: str):
    assert _bot_slot_from_login(login) == expected


@pytest.mark.parametrize(
    "login",
    [
        "SaifulHaqueNiloy",           # user token — never slot-derived
        "octocat",
        "dependabot[bot]",            # non-fleet bot
        "supremeai-coder-bot[bot]",   # missing slot index
        "supremeai-coder-x-bot[bot]", # index must be numeric
        "",                           # empty
    ],
)
def test_bot_slot_from_login_rejects_non_bot_logins(login: str):
    assert _bot_slot_from_login(login) is None


# ─────────────────── 2. recover when CAS branch exists ───────────────────
def test_resolve_recovers_slot_identity_when_branch_exists(isolated_identity, monkeypatch):
    monkeypatch.setattr(agent_identity, "_authenticated_login",
                        lambda: "supremeai-coder-1-bot[bot]")
    monkeypatch.setattr(agent_identity, "_list_existing_agent_branches",
                        lambda role, model: {"glm5.2-coder-1", "glm5.2-coder-2"})
    pushes = []
    monkeypatch.setattr(agent_identity, "_git_push_atomic",
                        lambda branch: pushes.append(branch) or True)

    identity = resolve_agent_identity(preferred="coder", model="glm5.2")

    # Recovered the leased slot — NO new index assigned, NO branch push
    assert identity.agent_name == "glm5.2-coder-1"
    assert identity.model == "glm5.2"
    assert pushes == [], "recovery must not create branches"
    # identity.json rewritten with the recovered name
    saved = json.loads(isolated_identity.read_text(encoding="utf-8"))
    assert saved["agent_name"] == "glm5.2-coder-1"


# ─────────────────── 3. fresh CAS claim on own slot ───────────────────
def test_resolve_claims_expected_slot_branch_when_missing(isolated_identity, monkeypatch):
    monkeypatch.setattr(agent_identity, "_authenticated_login",
                        lambda: "supremeai-coder-1-bot[bot]")
    monkeypatch.setattr(agent_identity, "_list_existing_agent_branches",
                        lambda role, model: set())
    pushes = []
    monkeypatch.setattr(agent_identity, "_git_push_atomic",
                        lambda branch: pushes.append(branch) or True)

    identity = resolve_agent_identity(preferred="coder", model="glm5.2")

    # Exactly the slot-derived name claimed on the agent/ namespace
    assert identity.agent_name == "glm5.2-coder-1"
    assert pushes == ["agent/glm5.2-coder-1"]
    assert agent_identity._bot_slot_from_login("supremeai-coder-1-bot[bot]") == "coder-1"


def test_resolve_slot_wins_over_conflicting_preferred_role(isolated_identity,
                                                           monkeypatch,
                                                           capsys):
    monkeypatch.setattr(agent_identity, "_authenticated_login",
                        lambda: "supremeai-coder-1-bot[bot]")
    monkeypatch.setattr(agent_identity, "_list_existing_agent_branches",
                        lambda role, model: {"glm5.2-coder-1"})

    identity = resolve_agent_identity(preferred="auditor", model="glm5.2")

    # Lease Gate invariant: the token's slot beats the requested role
    assert identity.agent_name == "glm5.2-coder-1"
    assert "Lease Gate" in capsys.readouterr().err


# ─────────────────── 4. non-bot → backwards-compatible gap-fill ───────────────────
def test_resolve_falls_back_to_gapfill_for_non_bot(isolated_identity, monkeypatch):
    monkeypatch.setattr(agent_identity, "_authenticated_login",
                        lambda: "SaifulHaqueNiloy")  # user token — no slot
    monkeypatch.setattr(agent_identity, "_claim_new_agent_name",
                        lambda role, model: "glm5.2-coder-7")

    identity = resolve_agent_identity(preferred="coder", model="glm5.2")

    assert identity.agent_name == "glm5.2-coder-7"
    saved = json.loads(isolated_identity.read_text(encoding="utf-8"))
    assert saved["agent_name"] == "glm5.2-coder-7"


def test_resolve_gapfill_when_login_lookup_fails(isolated_identity, monkeypatch):
    monkeypatch.setattr(agent_identity, "_authenticated_login", lambda: None)
    monkeypatch.setattr(agent_identity, "_claim_new_agent_name",
                        lambda role, model: "glm5.2-coder-2")

    identity = resolve_agent_identity(preferred="coder", model="glm5.2")
    assert identity.agent_name == "glm5.2-coder-2"


# ─────────────────── 5. CAS race lost → gap-fill fallback ───────────────────
def test_resolve_gapfill_when_cas_loses_race(isolated_identity, monkeypatch):
    monkeypatch.setattr(agent_identity, "_authenticated_login",
                        lambda: "supremeai-coder-1-bot[bot]")
    monkeypatch.setattr(agent_identity, "_list_existing_agent_branches",
                        lambda role, model: set())
    monkeypatch.setattr(agent_identity, "_git_push_atomic", lambda branch: False)
    monkeypatch.setattr(agent_identity, "_claim_new_agent_name",
                        lambda role, model: "glm5.2-coder-8")

    identity = resolve_agent_identity(preferred="coder", model="glm5.2")
    assert identity.agent_name == "glm5.2-coder-8"


# ─────────────────── 6. _authenticated_login transports ───────────────────
def test_authenticated_login_prefers_gh_cli(monkeypatch):
    class R:
        returncode = 0
        stdout = "supremeai-coder-1-bot[bot]\n"

    monkeypatch.setattr("subprocess.run", lambda *a, **k: R())
    monkeypatch.setattr(agent_identity.os, "environ",
                        {**agent_identity.os.environ, "GITHUB_TOKEN": ""})
    assert _authenticated_login() == "supremeai-coder-1-bot[bot]"


def test_authenticated_login_none_without_token_or_gh(monkeypatch):
    class R:
        returncode = 1
        stdout = ""

    monkeypatch.setattr("subprocess.run", lambda *a, **k: R())
    monkeypatch.setattr(agent_identity.os, "environ",
                        {**agent_identity.os.environ, "GITHUB_TOKEN": ""})
    assert _authenticated_login() is None


# ─────────────────── sanity: dataclass round-trip intact ───────────────────
def test_agent_identity_roundtrip(isolated_identity):
    ident = AgentIdentity(
        agent_name="glm5.2-coder-1",
        machine_id="m",
        created_at=1.0,
        last_active=2.0,
        model="glm5.2",
    )
    agent_identity._save_identity(ident)
    loaded = json.loads(isolated_identity.read_text(encoding="utf-8"))
    assert loaded["agent_name"] == "glm5.2-coder-1"
    assert loaded["model"] == "glm5.2"

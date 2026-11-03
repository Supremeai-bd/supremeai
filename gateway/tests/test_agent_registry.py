"""Agent Registry tests — governance Phase 1 (issue #1150).

বাংলা: কোনো নেটওয়ার্ক/বাহ্যিক স্টোর নেই — YAML ফাইল tmp_path-এ, FastAPI
নিজস্ব TestClient ছাড়াই রাউট ফাংশন সরাসরি কল করা হয় (conftest-নিরপেক্ষ)।
কভারেজ: validation (id/branch/main-নিষেধ), upsert/list/get/remove,
ownership record চুক্তি, singleton।
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routes.agent_registry import (
    assign_ownership,
    get_agent,
    list_agents,
    remove_agent,
    upsert_agent,
)
from core.agent_registry import AgentRecord, AgentRegistry, get_agent_registry


@pytest.fixture()
def registry(tmp_path):
    return AgentRegistry(path=tmp_path / "agent_roles.yaml")


# ── Registry core ────────────────────────────────────────────────────────────
def test_upsert_and_list_roundtrip(registry):
    registry.upsert(
        AgentRecord(id="agent-1", role="planner", provider="gemini", workspace_branch="agent-1")
    )
    registry.upsert(
        AgentRecord(id="agent-2", role="coder", provider="claude", workspace_branch="agent-2")
    )
    ids = [a.id for a in registry.list_agents()]
    assert ids == ["agent-1", "agent-2"]


def test_upsert_rejects_main_branch():
    with pytest.raises(ValueError, match="main"):
        AgentRegistry.validate_identity("agent-1", "main")


def test_upsert_rejects_bad_id_and_branch():
    with pytest.raises(ValueError):
        AgentRegistry.validate_identity("bad id!", "agent-x")
    with pytest.raises(ValueError):
        AgentRegistry.validate_identity("agent-1", "../escape")
    with pytest.raises(ValueError):
        AgentRegistry.validate_identity("agent-1", "-leading-dash")


def test_upsert_persists_to_yaml_file(registry, tmp_path):
    registry.upsert(
        AgentRecord(id="agent-9", role="gate", provider="gpt", workspace_branch="agent-9")
    )
    # নতুন ইনস্ট্যান্স একই ফাইল থেকে পড়বে — persistence প্রমাণ
    fresh = AgentRegistry(path=registry.path)
    assert fresh.get("agent-9") is not None
    assert fresh.get("agent-9").provider == "gpt"


def test_get_unknown_returns_none(registry):
    assert registry.get("ghost") is None


def test_remove_agent(registry):
    registry.upsert(
        AgentRecord(id="agent-4", role="observer", provider="mistral", workspace_branch="agent-4")
    )
    assert registry.remove("agent-4") is True
    assert registry.remove("agent-4") is False


# ── Ownership contract (#1150 Phase-1 §2) ────────────────────────────────────
def test_ownership_record_has_all_contract_fields(registry):
    registry.upsert(
        AgentRecord(id="agent-2", role="coder", provider="claude", workspace_branch="agent-2")
    )
    rec = registry.ownership_record("agent-2", "task-42", "backend/api only")
    assert rec == {
        "task_id": "task-42",
        "agent_id": "agent-2",
        "expected_scope": "backend/api only",
        "status": "assigned",
        "branch": "agent-2",
        "provider": "claude",
        "role": "coder",
    }


def test_ownership_rejects_unknown_agent(registry):
    with pytest.raises(ValueError, match="unknown agent"):
        registry.ownership_record("ghost", "t1", "scope")


def test_ownership_rejects_bad_status(registry):
    registry.upsert(
        AgentRecord(id="agent-2", role="coder", provider="claude", workspace_branch="agent-2")
    )
    with pytest.raises(ValueError, match="status"):
        registry.ownership_record("agent-2", "t1", "scope", status="flying")


# ── Route layer (direct calls) ───────────────────────────────────────────────
def test_route_upsert_and_list(monkeypatch, tmp_path):
    reg = AgentRegistry(path=tmp_path / "r.yaml")
    monkeypatch.setattr("api.routes.agent_registry.get_agent_registry", lambda: reg)
    created = __import__("asyncio").run(
        upsert_agent(
            __import__(
                "api.routes.agent_registry", fromlist=["AgentUpsertRequest"]
            ).AgentUpsertRequest(
                id="agent-5", role="coder", provider="any-vendor", workspace_branch="agent-5"
            ),
            {},
        )
    )
    assert created.id == "agent-5"
    listed = __import__("asyncio").run(list_agents(active_only=True))
    assert [a.id for a in listed] == ["agent-5"]


def test_route_get_unknown_raises_404(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "api.routes.agent_registry.get_agent_registry",
        lambda: AgentRegistry(path=tmp_path / "r.yaml"),
    )
    import asyncio

    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_agent("ghost"))
    assert exc.value.status_code == 404


def test_route_ownership_unknown_agent_maps_to_404(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "api.routes.agent_registry.get_agent_registry",
        lambda: AgentRegistry(path=tmp_path / "r.yaml"),
    )
    import asyncio

    from api.routes.agent_registry import OwnershipRequest

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            assign_ownership("ghost", OwnershipRequest(task_id="t", expected_scope="s"), {})
        )
    assert exc.value.status_code == 404


def test_route_delete_unknown_raises_404(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "api.routes.agent_registry.get_agent_registry",
        lambda: AgentRegistry(path=tmp_path / "r.yaml"),
    )
    import asyncio

    with pytest.raises(HTTPException) as exc:
        asyncio.run(remove_agent("ghost", {}))
    assert exc.value.status_code == 404


def test_singleton_is_shared():
    assert get_agent_registry() is get_agent_registry()

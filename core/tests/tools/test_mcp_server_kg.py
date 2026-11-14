"""
KG MCP server contract suite — backend/tools/mcp/mcp_server.py
===============================================================

Target: Knowledge-Graph MCP server (Server("supremeai-knowledge-graph")) —
78 statements @ 0% before this suite. Goal: 100% statements + 100% branches
without touching owner code (wire-first doctrine).

Coverage map
------------
- ``_check_policy``            : ALLOW / REQUIRE_APPROVAL / blocked-decision paths
- ``handle_list_tools``        : 5-tool registry contract (names, schemas, required fields)
- ``handle_call_tool`` guards  : arguments=None, tenant missing, tenant="default"
- policy gate (REAL)           : refresh_render_account_status -> REQUIRE_APPROVAL R2
                                 via the live policy engine (gate-before-dispatch ordering)
- dispatch (forced ALLOW)      : preflight / account status (dual-alias db patch) /
                                 refresh / skill dependencies (dry-run + neo4j driver) /
                                 learning path (hit + no-path) / unknown tool ValueError
- error + finally-audit        : exception -> error text; audit_tool_call recorded both
                                 on policy-block (error="policy_blocked") and success
- ``main()``                   : stdio transport wiring (fake streams + fake app.run)

Test-environment notes
----------------------
- GraphService() instantiates at module import; without NEO4J_PASSWORD it is in
  dry-run mode (driver=None), which is exactly what production uses when the
  graph credential is absent — real branches, no network.
- ``services.render_account_service`` is lazily imported inside handlers; a fake
  module is injected via ``sys.modules`` so no heavy imports are triggered.
- ``database.supabase_client.db`` is patched on BOTH module aliases
  (``database.supabase_client`` + ``backend.database.supabase_client``).
"""

from __future__ import annotations

import importlib
import json
import sys
import types as pytypes
from typing import Any
from unittest.mock import AsyncMock

import pytest

import tools.mcp.mcp_server as mcp_server

# =============================================================================
# Helpers
# =============================================================================


class AuditRecorder:
    """Stands in for ``audit_tool_call`` and records every call."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        tool_name: str,
        decision: str,
        risk_level: str,
        latency_ms: float = 0.0,
        error: str | None = None,
        tenant_id: str | None = None,
        # ── MCP Tower gap-4 (#928): extended per-agent audit contract ──
        agent_id: str = "unknown",
        client_role: str = "agent",
        provider: str = "unknown",
        args_hash: str = "",
        result_status: str = "ok",
        result_ref: str | None = None,
        hitl_required: bool = False,
        hitl_approver: str | None = None,
    ) -> None:
        self.calls.append(
            {
                "tool": tool_name,
                "decision": decision,
                "risk": risk_level,
                "latency": latency_ms,
                "error": error,
                "tenant": tenant_id,
                "agent_id": agent_id,
                "client_role": client_role,
                "provider": provider,
                "args_hash": args_hash,
                "result_status": result_status,
                "result_ref": result_ref,
                "hitl": {"required": hitl_required, "approver": hitl_approver},
            }
        )


@pytest.fixture
def audit_spy(monkeypatch: pytest.MonkeyPatch) -> AuditRecorder:
    recorder = AuditRecorder()
    monkeypatch.setattr(mcp_server, "audit_tool_call", recorder)
    return recorder


def _text(result: list[Any]) -> str:
    """Extract the single TextContent payload from a handler result."""
    assert len(result) == 1, f"expected exactly one content block, got {len(result)}"
    assert result[0].type == "text"
    return result[0].text


def _json(result: list[Any]) -> Any:
    return json.loads(_text(result))


def _force_policy(monkeypatch: pytest.MonkeyPatch, decision: str, risk: str) -> None:
    """Replace the module-level policy evaluation with a deterministic outcome."""
    monkeypatch.setattr(mcp_server, "evaluate_tool", lambda name: (decision, risk))


def _install_fake_render_service(monkeypatch: pytest.MonkeyPatch, **static_attrs: Any) -> type:
    """Inject a fake ``services.render_account_service`` module for lazy imports."""
    fake_mod = pytypes.ModuleType("services.render_account_service")

    class FakeRenderAccountService:
        pass

    for name, fn in static_attrs.items():
        setattr(FakeRenderAccountService, name, staticmethod(fn))
    fake_mod.RenderAccountService = FakeRenderAccountService
    monkeypatch.setitem(sys.modules, "services.render_account_service", fake_mod)
    return FakeRenderAccountService


class FakeDb:
    """Fake supabase ``db`` singleton capturing ``get_render_account_states``."""

    def __init__(self, states: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[str | None] = []
        self._states = states or []

    def get_render_account_states(self, role: str | None = None):
        self.calls.append(role)
        if self._states:
            return self._states
        return [{"account_role": role, "state": "ok", "cooldown_until": None}]


def _patch_db(monkeypatch: pytest.MonkeyPatch, fake_db: FakeDb) -> None:
    """Patch ``db`` on both module aliases (house gotcha w)."""
    for name in ("database.supabase_client", "backend.database.supabase_client"):
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        monkeypatch.setattr(mod, "db", fake_db, raising=False)


class _FakeQueryResult:
    async def data(self) -> list[dict[str, Any]]:
        return [{"name": "Alpha"}, {"name": "Beta"}]


class _FakeSession:
    def __init__(self, log: list[str]) -> None:
        self.queries: list[str] = log
        self.query: str | None = None

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def run(self, query: str, *args: Any, **kwargs: Any) -> _FakeQueryResult:
        self.query = query
        self.queries.append(query)
        return _FakeQueryResult()


class _FakeDriver:
    def __init__(self) -> None:
        self.sessions: list[_FakeSession] = []

    def session(self) -> _FakeSession:
        session = _FakeSession([])
        self.sessions.append(session)
        return session


# =============================================================================
# _check_policy — three-decision contract
# =============================================================================


class TestCheckPolicy:
    def test_allow_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _force_policy(monkeypatch, "ALLOW", "R0")
        assert mcp_server._check_policy("any_tool") is None

    def test_require_approval_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _force_policy(monkeypatch, "REQUIRE_APPROVAL", "R2")
        block = mcp_server._check_policy("risky_tool")
        assert block == {
            "approval_required": True,
            "risk_level": "R2",
            "tool": "risky_tool",
            "reason": ("Tool 'risky_tool' is classified as R2. Requires explicit human approval."),
        }

    def test_other_decision_is_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _force_policy(monkeypatch, "DENY", "R4")
        block = mcp_server._check_policy("forbidden_tool")
        assert block is not None
        assert block["approval_required"] is True
        assert block["risk_level"] == "R4"
        assert "blocked by policy" in block["reason"]
        assert "decision=DENY" in block["reason"]


# =============================================================================
# handle_list_tools — registry contract
# =============================================================================


class TestListTools:
    async def test_registry_names_and_schemas(self) -> None:
        tools = await mcp_server.handle_list_tools()
        names = [t.name for t in tools]
        assert names == [
            "get_skill_dependencies",
            "find_optimal_learning_path",
            "get_render_deploy_preflight",
            "get_render_account_status",
            "refresh_render_account_status",
            # MESH-6 (#926): Tower task-queue tools (platform-level)
            "mesh_dispatch_task",
            "mesh_task_status",
            "mesh_release_task",
            # MCP Tower gap-3 (#927): Agent mailbox tools (platform-level)
            "agent_send",
            "agent_inbox",
            "agent_ack",
            "topic_subscribe",
            # MCP Tower gap-4 (#928): per-agent verified audit tools
            "audit_query",
            "audit_verify",
        ]
        for tool in tools:
            assert tool.description
            schema = getattr(tool, "inputSchema", getattr(tool, "input_schema", {}))
            assert schema["type"] == "object"

    async def test_required_fields_match_contract(self) -> None:
        def _schema(tool: Any) -> dict[str, Any]:
            return getattr(tool, "inputSchema", getattr(tool, "input_schema", {}))

        tools = {t.name: t for t in await mcp_server.handle_list_tools()}
        assert _schema(tools["find_optimal_learning_path"])["required"] == [
            "start_skill",
            "end_skill",
        ]
        assert _schema(tools["refresh_render_account_status"])["required"] == ["account_role"]
        # optional knobs are advertised
        assert "force" in _schema(tools["refresh_render_account_status"])["properties"]
        assert "account_role" in _schema(tools["get_render_account_status"])["properties"]
        # graph tools expose empty property sets
        assert _schema(tools["get_skill_dependencies"])["properties"] == {}
        assert _schema(tools["get_render_deploy_preflight"])["properties"] == {}
        # MESH-6 (#926): task-queue tool contracts
        assert _schema(tools["mesh_dispatch_task"])["required"] == ["task_type", "title"]
        assert _schema(tools["mesh_release_task"])["required"] == ["task_id"]
        # task_status-এ task_id optional — queue snapshot mode
        assert "required" not in _schema(tools["mesh_task_status"])
        # MCP Tower gap-3 (#927): mailbox tool contracts
        assert _schema(tools["agent_send"])["required"] == ["from_agent", "to_agent"]
        assert _schema(tools["agent_inbox"])["required"] == ["agent_id"]
        assert _schema(tools["agent_ack"])["required"] == ["message_id", "agent_id"]
        assert _schema(tools["topic_subscribe"])["required"] == ["agent_id", "topics"]


# =============================================================================
# handle_call_tool — tenant guard
# =============================================================================


class TestTenantGuard:
    async def test_none_arguments_treated_as_empty(self, audit_spy: AuditRecorder) -> None:
        payload = _json(await mcp_server.handle_call_tool("get_skill_dependencies", None))
        assert payload == {"error": "tenant_id is required"}
        # guard fires before any dispatch or audit
        assert audit_spy.calls == []

    async def test_missing_tenant_rejected(self, audit_spy: AuditRecorder) -> None:
        payload = _json(await mcp_server.handle_call_tool("get_skill_dependencies", {"role": "x"}))
        assert payload == {"error": "tenant_id is required"}

    async def test_default_tenant_rejected(self) -> None:
        payload = _json(
            await mcp_server.handle_call_tool("get_skill_dependencies", {"tenant_id": "default"})
        )
        assert payload == {"error": "tenant_id is required"}

    async def test_whitespace_tenant_rejected(self) -> None:
        payload = _json(
            await mcp_server.handle_call_tool("get_skill_dependencies", {"tenant_id": "   "})
        )
        assert payload == {"error": "tenant_id is required"}


# =============================================================================
# Policy gate — REAL engine + forced decisions
# =============================================================================


class TestPolicyGateReal:
    async def test_refresh_tool_requires_approval_via_real_policy(
        self, audit_spy: AuditRecorder
    ) -> None:
        """Locks the live policy contract: refresh action = REQUIRE_APPROVAL / R2.

        Also locks gate-before-dispatch ordering: the block short-circuits before
        any service call, and the audit trail records error="policy_blocked".
        """
        result = await mcp_server.handle_call_tool(
            "refresh_render_account_status",
            {"tenant_id": "tenant-1", "account_role": "core"},
        )
        payload = _json(result)
        assert payload["approval_required"] is True
        assert payload["tool"] == "refresh_render_account_status"
        # Live engine classifies refresh as R2 today — tripwire if owner re-tunes policy.
        assert payload["risk_level"] == "R2"
        assert "Requires explicit human approval" in payload["reason"]
        assert len(audit_spy.calls) == 1
        block_call = audit_spy.calls[0]
        assert block_call["error"] == "policy_blocked"
        assert block_call["tenant"] == "tenant-1"
        assert block_call["tool"] == "refresh_render_account_status"
        assert block_call["decision"] == "REQUIRE_APPROVAL"

    async def test_unknown_tool_hits_policy_gate_before_dispatch(
        self, audit_spy: AuditRecorder
    ) -> None:
        """Policy-first ordering: unregistered tools are gated (REQUIRE_APPROVAL
        default for unknown provider/action) before the ValueError path can run."""
        payload = _json(
            await mcp_server.handle_call_tool("not_a_registered_tool", {"tenant_id": "t1"})
        )
        assert payload["approval_required"] is True
        assert payload["tool"] == "not_a_registered_tool"
        assert audit_spy.calls[0]["error"] == "policy_blocked"


class TestPolicyGateForced:
    async def test_denied_decision_returns_blocked_payload(
        self, monkeypatch: pytest.MonkeyPatch, audit_spy: AuditRecorder
    ) -> None:
        _force_policy(monkeypatch, "DENY", "R4")
        payload = _json(
            await mcp_server.handle_call_tool("get_skill_dependencies", {"tenant_id": "t1"})
        )
        assert payload["approval_required"] is True
        assert payload["risk_level"] == "R4"
        assert "blocked by policy" in payload["reason"]
        assert audit_spy.calls[0]["error"] == "policy_blocked"

    async def test_required_approval_decision_returns_approval_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _force_policy(monkeypatch, "REQUIRE_APPROVAL", "R1")
        payload = _json(
            await mcp_server.handle_call_tool("get_skill_dependencies", {"tenant_id": "t1"})
        )
        assert payload["approval_required"] is True
        assert payload["risk_level"] == "R1"
        assert "Requires explicit human approval" in payload["reason"]


# =============================================================================
# Dispatch — ALLOW path through the real gate (read tools are R0)
# =============================================================================


class TestDispatchPreflight:
    async def test_preflight_returns_json_overview(
        self, monkeypatch: pytest.MonkeyPatch, audit_spy: AuditRecorder
    ) -> None:
        overview = {"roles": {"core": {"state": "healthy"}}, "limits": {"daily": 10}}
        _install_fake_render_service(monkeypatch, get_status_overview=lambda: overview)
        payload = _json(
            await mcp_server.handle_call_tool("get_render_deploy_preflight", {"tenant_id": "t1"})
        )
        assert payload == overview
        assert audit_spy.calls[0]["error"] is None
        assert audit_spy.calls[0]["decision"] == "ALLOW"
        assert audit_spy.calls[0]["tenant"] == "t1"
        assert audit_spy.calls[0]["latency"] >= 0.0

    async def test_preflight_service_failure_becomes_error_text(
        self, monkeypatch: pytest.MonkeyPatch, audit_spy: AuditRecorder
    ) -> None:
        def boom() -> dict[str, Any]:
            raise RuntimeError("render unreachable")

        _install_fake_render_service(monkeypatch, get_status_overview=boom)
        text = _text(
            await mcp_server.handle_call_tool("get_render_deploy_preflight", {"tenant_id": "t1"})
        )
        assert text.startswith("Error gathering graph context:")
        assert "render unreachable" in text
        # finally-audit still fires on the failure path
        assert audit_spy.calls[0]["error"] is None


class TestDispatchAccountStatus:
    async def test_account_status_round_trips_db_states(
        self, monkeypatch: pytest.MonkeyPatch, audit_spy: AuditRecorder
    ) -> None:
        fake_db = FakeDb()
        _patch_db(monkeypatch, fake_db)
        payload = _json(
            await mcp_server.handle_call_tool(
                "get_render_account_status",
                {"tenant_id": "t1", "account_role": "worker"},
            )
        )
        assert payload == [{"account_role": "worker", "state": "ok", "cooldown_until": None}]
        assert fake_db.calls == ["worker"]
        assert audit_spy.calls[0]["tenant"] == "t1"


class TestDispatchRefresh:
    async def test_refresh_success_when_policy_forced_allow(
        self, monkeypatch: pytest.MonkeyPatch, audit_spy: AuditRecorder
    ) -> None:
        """The real gate blocks refresh (see TestPolicyGateReal); forcing ALLOW
        exercises the dispatch body itself."""
        _force_policy(monkeypatch, "ALLOW", "R0")
        captured: dict[str, Any] = {}

        def fake_refresh(account_role: str, force: bool, manual_by: str):
            captured.update(role=account_role, force=force, manual_by=manual_by)
            return {"status": "refreshed", "role": account_role}

        _install_fake_render_service(monkeypatch, refresh_account_status=fake_refresh)
        payload = _json(
            await mcp_server.handle_call_tool(
                "refresh_render_account_status",
                {"tenant_id": "t1", "account_role": "mcp", "force": True},
            )
        )
        assert payload == {"status": "refreshed", "role": "mcp"}
        assert captured == {"role": "mcp", "force": True, "manual_by": "mcp_tool"}
        assert audit_spy.calls[0]["error"] is None

    async def test_refresh_defaults_force_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _force_policy(monkeypatch, "ALLOW", "R0")
        captured: dict[str, Any] = {}

        def fake_refresh(account_role: str, force: bool, manual_by: str):
            captured.update(force=force)
            return {}

        _install_fake_render_service(monkeypatch, refresh_account_status=fake_refresh)
        await mcp_server.handle_call_tool(
            "refresh_render_account_status", {"tenant_id": "t1", "account_role": "core"}
        )
        assert captured["force"] is False


class TestDispatchSkillDependencies:
    async def test_dry_run_returns_mock_nodes(self, audit_spy: AuditRecorder) -> None:
        """No NEO4J credential in test env -> module-level GraphService is dry-run."""
        assert mcp_server.graph_service.dry_run is True
        text = _text(
            await mcp_server.handle_call_tool("get_skill_dependencies", {"tenant_id": "t1"})
        )
        assert text.startswith("SupremeAI Skills Graph Context:")
        graph_data = json.loads(text.split(":", 1)[1])
        assert graph_data["status"] == "dry-run"
        assert graph_data["nodes"] == ["Python", "FastAPI", "Redis"]
        assert audit_spy.calls[0]["decision"] == "ALLOW"

    async def test_neo4j_driver_path_returns_node_names(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        driver = _FakeDriver()
        monkeypatch.setattr(mcp_server.graph_service, "dry_run", False)
        monkeypatch.setattr(mcp_server.graph_service, "driver", driver)
        text = _text(
            await mcp_server.handle_call_tool("get_skill_dependencies", {"tenant_id": "t1"})
        )
        graph_data = json.loads(text.split(":", 1)[1])
        assert graph_data == {"nodes": ["Alpha", "Beta"]}
        assert len(driver.sessions) == 1
        assert driver.sessions[0].query == "MATCH (n:Skill) RETURN n.name AS name LIMIT 50"

    async def test_neo4j_failure_becomes_error_text(
        self, monkeypatch: pytest.MonkeyPatch, audit_spy: AuditRecorder
    ) -> None:
        class ExplodingSession(_FakeSession):
            async def run(self, query: str, *args: Any, **kwargs: Any):
                raise RuntimeError("bolt down")

        class ExplodingDriver:
            def session(self) -> ExplodingSession:
                return ExplodingSession([])

        monkeypatch.setattr(mcp_server.graph_service, "dry_run", False)
        monkeypatch.setattr(mcp_server.graph_service, "driver", ExplodingDriver())
        text = _text(
            await mcp_server.handle_call_tool("get_skill_dependencies", {"tenant_id": "t1"})
        )
        assert "Error gathering graph context:" in text
        assert "bolt down" in text


class TestDispatchLearningPath:
    async def test_dry_run_returns_fixed_path(self) -> None:
        text = _text(
            await mcp_server.handle_call_tool(
                "find_optimal_learning_path",
                {"tenant_id": "t1", "start_skill": "A", "end_skill": "B"},
            )
        )
        assert text.startswith("Optimal execution path from A to B:")
        assert "Dry-run Path Node 1 -> Dry-run Path Node 2" in text

    async def test_no_path_found_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def empty_path(start: str, end: str) -> list[str]:
            return []

        monkeypatch.setattr(mcp_server.graph_service, "get_skill_path", empty_path)
        text = _text(
            await mcp_server.handle_call_tool(
                "find_optimal_learning_path",
                {"tenant_id": "t1", "start_skill": "A", "end_skill": "B"},
            )
        )
        assert "No path found." in text

    async def test_real_path_is_joined(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def path(start: str, end: str) -> list[str]:
            return ["Alpha", "Beta", "Gamma"]

        monkeypatch.setattr(mcp_server.graph_service, "get_skill_path", path)
        text = _text(
            await mcp_server.handle_call_tool(
                "find_optimal_learning_path",
                {"tenant_id": "t1", "start_skill": "Alpha", "end_skill": "Gamma"},
            )
        )
        assert "Alpha -> Beta -> Gamma" in text

    async def test_path_lookup_failure_becomes_error_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def explode(start: str, end: str) -> list[str]:
            raise ValueError("graph offline")

        monkeypatch.setattr(mcp_server.graph_service, "get_skill_path", explode)
        text = _text(
            await mcp_server.handle_call_tool(
                "find_optimal_learning_path",
                {"tenant_id": "t1", "start_skill": "A", "end_skill": "B"},
            )
        )
        assert "graph offline" in text


class TestUnknownToolDispatch:
    async def test_allowed_but_unimplemented_tool_raises_value_error(
        self, monkeypatch: pytest.MonkeyPatch, audit_spy: AuditRecorder
    ) -> None:
        """Only reachable when policy explicitly ALLOWs an unregistered name —
        the ValueError + except-branch contract."""
        _force_policy(monkeypatch, "ALLOW", "R0")
        text = _text(await mcp_server.handle_call_tool("ghost_tool", {"tenant_id": "t1"}))
        assert "Error gathering graph context:" in text
        assert "Unknown MCP tool: ghost_tool" in text
        assert audit_spy.calls[0]["error"] is None


# =============================================================================
# MCP Tower gap-3 (#927) — active mailbox dispatch contract
# =============================================================================


class TestAgentMailboxTools:
    """Exercise the active MCP API against an isolated real AgentMailbox."""

    @pytest.fixture
    def mailbox(self, monkeypatch: pytest.MonkeyPatch, audit_spy: AuditRecorder):
        from core import agent_mailbox

        mailbox = agent_mailbox.AgentMailbox()
        monkeypatch.setattr(agent_mailbox, "get_agent_mailbox", AsyncMock(return_value=mailbox))
        # Audit persistence is a separate contract; never touch the shared database here.
        monkeypatch.setattr(mcp_server, "_audit_chain_append", AsyncMock())
        return mailbox

    async def test_send_inbox_ack_and_subscribe(self, mailbox, audit_spy: AuditRecorder) -> None:
        sent = _json(
            await mcp_server.handle_call_tool(
                "agent_send",
                {
                    "tenant_id": "tenant-927",
                    "from_agent": "planner-1",
                    "to_agent": "coder-1",
                    "body": {"task": "build"},
                    "ttl_seconds": 60,
                },
            )
        )
        assert sent["message_id"].startswith("msg-")
        assert sent["tenant_id"] == "tenant-927"
        assert sent["from_agent"] == "planner-1"
        assert sent["to_agent"] == "coder-1"
        assert sent["body"] == {"task": "build"}
        assert sent["acked"] is False
        assert sent["expires_at_epoch"] - sent["created_at_epoch"] == 60
        assert await mailbox.count("tenant-927") == 1

        inbox_args = {"tenant_id": "tenant-927", "agent_id": "coder-1"}
        inbox = _json(await mcp_server.handle_call_tool("agent_inbox", inbox_args))
        assert inbox == {**inbox_args, "count": 1, "messages": [sent]}

        ack_args = {**inbox_args, "message_id": sent["message_id"]}
        acked = _json(await mcp_server.handle_call_tool("agent_ack", ack_args))
        assert acked["message_id"] == sent["message_id"]
        assert acked["acked"] is True
        assert acked["acked_by"] == "coder-1"
        assert acked["acked_at"]
        assert _json(await mcp_server.handle_call_tool("agent_ack", ack_args)) == acked
        unread = _json(
            await mcp_server.handle_call_tool("agent_inbox", {**inbox_args, "unread_only": True})
        )
        assert unread["count"] == 0
        assert unread["messages"] == []

        sub_args = {**inbox_args, "topics": ["deploy-events"]}
        sub = _json(await mcp_server.handle_call_tool("topic_subscribe", sub_args))
        assert sub == {"status": "ok", **sub_args}
        assert await mailbox.subscriptions(agent_id="coder-1", tenant_id="tenant-927") == [
            "deploy-events"
        ]
        assert [call["tool"] for call in audit_spy.calls] == [
            "agent_send",
            "agent_inbox",
            "agent_ack",
            "agent_ack",
            "agent_inbox",
            "topic_subscribe",
        ]
        mcp_server._audit_chain_append.assert_awaited()

    @pytest.mark.parametrize("tool", ["agent_send", "agent_inbox", "agent_ack", "topic_subscribe"])
    @pytest.mark.parametrize("tenant_id", ["", "default"])
    async def test_mailbox_requires_explicit_tenant(self, mailbox, tool, tenant_id):
        result = _json(await mcp_server.handle_call_tool(tool, {"tenant_id": tenant_id}))
        assert result == {"error": "tenant_id is required"}
        assert await mailbox.count() == 0
        mcp_server._audit_chain_append.assert_not_awaited()

    async def test_tenant_and_recipient_isolation(self, mailbox):
        sent = _json(
            await mcp_server.handle_call_tool(
                "agent_send",
                {"tenant_id": "tenant-a", "from_agent": "planner", "to_agent": "coder"},
            )
        )
        for tenant, agent in [("tenant-b", "coder"), ("tenant-a", "other")]:
            args = {"tenant_id": tenant, "agent_id": agent}
            inbox = _json(await mcp_server.handle_call_tool("agent_inbox", args))
            assert inbox["count"] == 0
            assert inbox["messages"] == []
            error = _text(
                await mcp_server.handle_call_tool(
                    "agent_ack", {**args, "message_id": sent["message_id"]}
                )
            )
            assert "Error gathering graph context:" in error
            assert (
                "cross-tenant ack denied" in error
                if tenant == "tenant-b"
                else "not the recipient" in error
            )
        stored = await mailbox.inbox(agent_id="coder", tenant_id="tenant-a")
        assert len(stored) == 1
        assert stored[0].acked is False

    async def test_subscription_gates_role_and_topic_broadcast(self, mailbox):
        args = {"tenant_id": "tenant-927", "agent_id": "coder-1", "role": "coder"}
        sent = _json(
            await mcp_server.handle_call_tool(
                "agent_send",
                {
                    "tenant_id": "tenant-927",
                    "from_agent": "planner-1",
                    "to_agent": "*",
                    "to_role": "coder",
                    "topic": "deploy-events",
                    "body": {"revision": "fixture"},
                },
            )
        )
        assert _json(await mcp_server.handle_call_tool("agent_inbox", args))["count"] == 0
        sub_args = {"tenant_id": "tenant-927", "agent_id": "coder-1", "topics": ["deploy-events"]}
        await mcp_server.handle_call_tool("topic_subscribe", sub_args)
        sub = _json(await mcp_server.handle_call_tool("topic_subscribe", sub_args))
        assert sub["topics"] == ["deploy-events"]
        inbox = _json(await mcp_server.handle_call_tool("agent_inbox", args))
        assert inbox["messages"] == [sent]
        assert inbox["count"] == 1
        for changes in [{"role": "tester"}, {"tenant_id": "tenant-other"}, {"agent_id": "coder-2"}]:
            assert (
                _json(await mcp_server.handle_call_tool("agent_inbox", {**args, **changes}))[
                    "count"
                ]
                == 0
            )


# =============================================================================
# Audit wiring + main() stdio transport
# =============================================================================


class TestAuditWiring:
    def test_real_audit_tool_call_persists_tenant_context(self) -> None:
        """Prove the module-level import is wired to the real audit trail AND that
        the tenant context actually lands in the entry (regression lock: the
        convenience wrapper previously dropped ``tenant_id`` before constructing
        MCPAuditEntry, making every audited call raise ValueError)."""
        from core.mcp_audit import audit_tool_call, get_audit_logger

        logger_instance = get_audit_logger()
        before = len(logger_instance._buffer)
        audit_tool_call("suite-probe", "ALLOW", "R0", latency_ms=1.5, tenant_id="t-probe")
        assert len(logger_instance._buffer) == before + 1
        entry = logger_instance._buffer[-1]
        assert entry.tool_name == "suite-probe"
        assert entry.tenant_id == "t-probe"
        assert entry.decision == "ALLOW"
        assert entry.risk_level == "R0"
        assert entry.latency_ms == 1.5


class TestMainStdio:
    async def test_main_runs_app_over_stdio_streams(self, monkeypatch: pytest.MonkeyPatch) -> None:
        lifecycle: dict[str, bool] = {}

        class FakeStdioServer:
            async def __aenter__(self):
                lifecycle["entered"] = True
                return ("READ_STREAM", "WRITE_STREAM")

            async def __aexit__(self, *args: Any) -> bool:
                lifecycle["exited"] = True
                return False

        monkeypatch.setattr("mcp.server.stdio.stdio_server", lambda: FakeStdioServer())
        seen: dict[str, Any] = {}

        async def fake_run(read_stream, write_stream, init_options):
            seen["read"] = read_stream
            seen["write"] = write_stream
            seen["init"] = init_options

        monkeypatch.setattr(mcp_server.app, "run", fake_run)
        monkeypatch.setattr(mcp_server.app, "create_initialization_options", lambda: {"init": True})

        await mcp_server.main()

        assert seen == {
            "read": "READ_STREAM",
            "write": "WRITE_STREAM",
            "init": {"init": True},
        }
        assert lifecycle == {"entered": True, "exited": True}

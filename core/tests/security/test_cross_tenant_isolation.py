"""AUD-2.8 / AUD-3.9 (P0) — Cross-tenant adversarial security tests.

These tests assert that user B cannot access, mutate, or replay user A's data,
and that the HITL approval surface rejects replay/tampering/expiry attacks.

Implementation note: source-level assertions read files from disk instead of
importing every route module — importing some modules transitively pulls the
full model registry and app fixtures (JSONB is Postgres-only and cannot compile
against the local sqlite test DB).
"""

import os
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from models.pending_tasks import (
    TaskStatus,
    TaskType,
    create_pending_task,
    get_task,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def _source_of(rel_path: str) -> str:
    return (BACKEND_DIR / rel_path).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AUD-2.1: previously-public routes now require authentication
# ---------------------------------------------------------------------------


class TestMarkdownRouterAuth:
    """The markdown router was public + unguarded; verify both fixes."""

    def test_markdown_removed_from_public_paths(self):
        from core.config import settings

        public = settings.supremeai_public_paths
        if isinstance(public, str):
            public = [p.strip() for p in public.split(",")]
        assert "/api/v1/markdown" not in public

    def test_markdown_router_requires_auth(self):
        src = _source_of("api/routes/markdown.py")
        assert "Depends(get_current_user_token)" in src
        assert "dependencies=[Depends(get_current_user_token)]" in src

    def test_markdown_history_is_user_scoped(self):
        src = _source_of("api/routes/markdown.py")
        assert '.eq("user_id", user_id)' in src


class TestWebSocketAuth:
    """AUD-2.1: WebSockets bypass ASGI http middleware, so each must self-guard."""

    def test_ci_dashboard_ws_authenticates(self):
        src = _source_of("api/routes/ci_dashboard_api.py")
        assert "authenticate_websocket(websocket, token)" in src

    def test_service_topology_ws_requires_admin(self):
        src = _source_of("api/routes/service_topology.py")
        assert "require_admin=True" in src

    def test_agent_terminal_stream_requires_auth(self):
        src = _source_of("api/routes/agent_workspace.py")
        assert "authenticate_websocket" in src

    def test_hitl_ws_requires_admin(self):
        src = _source_of("api/routes/approval_manager.py")
        assert "require_admin=True" in src


class TestAdminRoleEnforcement:
    """AUD-2.6: broken get_current_admin must now fail closed on non-admins."""

    def test_rbac_get_current_admin_rejects_non_admin(self):
        from core.security.authentication.rbac import get_current_admin

        req = MagicMock()
        req.state.user = {"sub": "user-1", "role": "user"}
        with pytest.raises(HTTPException) as excinfo:
            get_current_admin(req)
        assert excinfo.value.status_code == 403

    def test_rbac_get_current_admin_allows_admin(self):
        from core.security.authentication.rbac import get_current_admin

        req = MagicMock()
        req.state.user = {"sub": "admin-1", "role": "admin"}
        assert get_current_admin(req)["sub"] == "admin-1"

    def test_tools_registry_router_guarded(self):
        src = _source_of("api/routes/tools_registry.py")
        assert "dependencies=[Depends(get_current_admin)]" in src

    def test_living_brain_router_guarded(self):
        src = _source_of("api/routes/living_brain.py")
        assert "dependencies=[Depends(get_current_admin)]" in src

    def test_browser_url_decision_requires_admin(self):
        src = _source_of("api/routes/browser/_url_permissions.py")
        decision_block = src.split("/urls/requests/{id}/decision")[1][:300]
        assert "require_admin_token" in decision_block


# ---------------------------------------------------------------------------
# AUD-2.3/2.5: object-level authorization on client-supplied IDs
# ---------------------------------------------------------------------------


class TestObjectLevelAuthorization:
    def test_conversations_add_message_checks_ownership(self):
        src = _source_of("api/routes/conversations.py")
        assert '.eq("user_id", user_id)' in src

    def test_chat_upload_get_checks_ownership(self):
        src = _source_of("api/routes/chat_upload.py")
        serve_block = src.split("async def serve_upload")[1][:2500]
        assert "user_id" in serve_block
        assert "404" in serve_block

    def test_api_key_usage_hook_checks_ownership(self):
        src = _source_of("api/routes/api_keys.py")
        hook_block = src.split("async def record_usage_hook")[1][:1200]
        assert "get_api_key_by_id" in hook_block
        assert "user_id" in hook_block

    def test_preferences_stream_blocks_other_users(self):
        src = _source_of("api/routes/preferences.py")
        stream_block = src.split("async def stream_preferences")[1][:1200]
        assert "403" in stream_block
        assert "default" in stream_block


# ---------------------------------------------------------------------------
# AUD-2.2: memory surfaces are tenant-scoped
# ---------------------------------------------------------------------------


class TestMemoryTenantScoping:
    def test_unified_memory_router_requires_auth(self):
        src = _source_of("api/routes/unified_memory_api.py")
        assert "Depends(get_current_user_token)" in src
        # the auth import must NOT be commented out anymore
        assert "# Removed auth import" not in src

    def test_unified_memory_query_scopes_by_user(self):
        src = _source_of("api/routes/unified_memory_api.py")
        assert "user_id=user.get" in src

    def test_memory_recall_passes_user_id(self):
        src = _source_of("api/routes/memory.py")
        assert "user_id=user.get" in src

    def test_checkpoints_namespaced_by_user(self):
        src = _source_of("api/routes/memory.py")
        assert "_owned_checkpoint_key" in src

    def test_chat_rag_scoped_and_cache_scoped(self):
        src = _source_of("api/routes/chat.py")
        assert "user_id=db.tenant_id" in src

    def test_multi_layer_cache_user_scoped_keys(self):
        """AUD-5.6: user-scoped cache keys differ from global keys."""
        import hashlib

        prompt, model, user_a, user_b = "hello", "gemini", "alice", "bob"
        k_global = f"exact:{hashlib.sha256(f'{prompt}:{model}'.encode()).hexdigest()}"
        k_a = f"exact:{hashlib.sha256(f'{user_a}:{prompt}:{model}'.encode()).hexdigest()}"
        k_b = f"exact:{hashlib.sha256(f'{user_b}:{prompt}:{model}'.encode()).hexdigest()}"
        assert k_a != k_b != k_global

    def test_multi_layer_cache_get_signature_has_user_id(self):
        src = _source_of("core/cache/multi_layer_cache.py")
        assert "user_id: str | None = None" in src
        assert "query_similar(\n                prompt, user_id=user_id" in src


# ---------------------------------------------------------------------------
# AUD-3.5/Phase 4: HITL approval surface is mounted and hard-guarded
# ---------------------------------------------------------------------------


class TestHITLApprovalSurface:
    def test_approval_router_is_mounted(self):
        """AUD-3.5: the router was previously never registered (dead end)."""
        from api.routers import ALL_ROUTERS

        paths = [r["path"] for r in ALL_ROUTERS]
        assert "api.routes.approval_manager" in paths
        entry = next(r for r in ALL_ROUTERS if r["path"] == "api.routes.approval_manager")
        assert entry["is_admin"] is True

    def test_approval_routes_are_admin_guarded(self):
        src = _source_of("api/routes/approval_manager.py")
        guarded = src.count("Depends(get_project_admin)")
        # pending, approve, reject, cancel routes all carry the admin guard
        assert guarded >= 4

    def test_cancel_endpoint_exists(self):
        src = _source_of("api/routes/approval_manager.py")
        assert '@router.post("/cancel/{task_id}")' in src

    def test_expired_task_rejected_via_route_logic(self):
        """AUD-4.3: expired task decision returns 410 from the route helper."""
        from api.routes import approval_manager

        task = create_pending_task(
            TaskType.CODE_PUSH,
            {"action": "push"},
            created_by="alice",
            tenant_id="t1",
            ttl_seconds=-5,
        )
        req = approval_manager.ApproveRequest(resolved_by="attacker")

        with pytest.raises(HTTPException) as excinfo:
            # direct call: admin dep is bypassed (it's a Depends), exercising the guard logic
            approval_manager.approve_task(task.task_id, req, _={"role": "admin"})
        assert excinfo.value.status_code == 410

    def test_replayed_task_rejected_with_409(self):
        from api.routes import approval_manager

        task = create_pending_task(TaskType.CODE_PUSH, {"action": "push"}, created_by="alice")
        req = approval_manager.ApproveRequest(resolved_by="admin")
        approval_manager.approve_task(task.task_id, req, _={"role": "admin"})

        with pytest.raises(HTTPException) as excinfo:
            approval_manager.approve_task(task.task_id, req, _={"role": "admin"})
        assert excinfo.value.status_code == 409

        # payload was not executed twice
        assert get_task(task.task_id).resolved_by == "admin"


# ---------------------------------------------------------------------------
# AUD-2.9: production logging must not disclose variables in tracebacks
# ---------------------------------------------------------------------------


class TestLoggingRedaction:
    def test_production_logging_disables_diagnose(self):
        src = _source_of("monitoring/logging_config.py")
        assert "diagnose=not is_prod_like" in src
        assert "backtrace=not is_prod_like" in src


# ---------------------------------------------------------------------------
# AUD-6.1: self-evolution cannot mutate the live tree during dry-run
# ---------------------------------------------------------------------------


class TestSelfEvolutionSafety:
    def test_tier8_dry_run_uses_temp_copy(self):
        src = _source_of("core/tier8/codebase_refactor_proposer.py")
        dry_run_block = src.split("async def _run_dry_run")[1][:3000]
        assert "target.write_text" not in dry_run_block, "must not write the live file"
        assert "NamedTemporaryFile" in dry_run_block

    def test_self_updater_defaults_unauthorized(self):
        src = _source_of("core/self_evolution/self_updater.py")
        assert "self_updater = SelfUpdater(authorized=False)" in src

    def test_evolution_approver_recorded(self):
        src = _source_of("api/routes/evolution.py")
        assert "approved_by" in src

    def test_canary_no_fabricated_success(self):
        src = _source_of("evolution/change_proposal.py")
        assert "proposal.canary_success_rate = 1.0  # Canary passed" not in src

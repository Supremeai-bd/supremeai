"""ERR-H04 contract tests — the 17 previously-dead ecosystem admin calls.

Covers the routes wired into ``api.routes.ecosystem_admin`` (SO1-4, SP1-4,
LE1-3, GO1-2, PR4, C5) plus the A5/A6 auth-user routes, each verified against
the real engine stores (no mocks).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from adaptive_engine.source_governance import LearnedItem, SourceCategory, SourceState
from api.routes import ecosystem_admin

ADMIN_TOKEN = "test-admin-token-err-h04"


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch) -> None:
    """Point the shared ecosystem SQLite store at a per-test file.

    Engine singletons hold no connection, but their ``_ensure_schema`` runs once
    per process — reset them so every test rebuilds schema on ITS tmp database.
    """
    import adaptive_engine._store as store
    import adaptive_engine.approval_workflow as aw
    import adaptive_engine.capability_registry as cr
    import adaptive_engine.governance as gv
    import adaptive_engine.learning_loop as ll
    import adaptive_engine.source_governance as sg
    import adaptive_engine.task_engine as te

    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_DB_PATH", tmp_path / "ecosystem.db")
    monkeypatch.setattr(sg, "_gov", None)
    monkeypatch.setattr(gv, "_engine", None)
    monkeypatch.setattr(aw, "_wf", None)
    monkeypatch.setattr(te, "_engine", None)
    monkeypatch.setattr(ll, "_loop", None)
    monkeypatch.setattr(cr, "_registry", None)


@pytest.fixture()
def client(monkeypatch, isolated_db) -> Iterator[TestClient]:
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
    app = FastAPI()
    app.include_router(ecosystem_admin.router)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def static_token_only(monkeypatch) -> None:
    """Force the static-token auth path by removing the JWT bypass."""

    def _no_jwt(_request):
        raise HTTPException(status_code=401, detail="no jwt in this test")

    monkeypatch.setattr(ecosystem_admin, "get_current_user_token", _no_jwt)


# --- sources (SO1-SO4) -----------------------------------------------------


class TestSourcesContract:
    def test_discover_list_get_transition(self, client: TestClient):
        res = client.post(
            "/api/v1/ecosystem/admin/sources/discover",
            json={"url": "https://docs.example.com/guide", "category": "TECH_DOCS"},
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["url"] == "https://docs.example.com/guide"
        assert body["state"] == SourceState.DISCOVERED
        source_id = body["source_id"]

        listed = client.get("/api/v1/ecosystem/admin/sources").json()
        assert any(s["source_id"] == source_id for s in listed)
        assert all("domain" in s and "trust_score" in s for s in listed)

        got = client.get(f"/api/v1/ecosystem/admin/sources/{source_id}").json()
        assert got["category"] == "TECH_DOCS"

        res = client.post(
            f"/api/v1/ecosystem/admin/sources/{source_id}/transition",
            json={"to_state": "APPROVAL_PENDING"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["state"] == SourceState.APPROVAL_PENDING

    def test_discover_invalid_category_400(self, client: TestClient):
        res = client.post(
            "/api/v1/ecosystem/admin/sources/discover",
            json={"url": "https://x.example.com", "category": "NOT_A_CATEGORY"},
        )
        assert res.status_code == 400

    def test_transition_unknown_source_404(self, client: TestClient):
        res = client.post(
            "/api/v1/ecosystem/admin/sources/src-does-not-exist/transition",
            json={"to_state": "BLOCKED"},
        )
        assert res.status_code == 404

    def test_transition_illegal_move_409(self, client: TestClient):
        res = client.post(
            "/api/v1/ecosystem/admin/sources/discover",
            json={"url": "https://locked.example.com"},
        )
        source_id = res.json()["source_id"]
        # DISCOVERED -> ALLOWLISTED is legal; ALLOWLISTED -> DISCOVERED is not.
        client.post(
            f"/api/v1/ecosystem/admin/sources/{source_id}/transition",
            json={"to_state": "ALLOWLISTED"},
        )
        res = client.post(
            f"/api/v1/ecosystem/admin/sources/{source_id}/transition",
            json={"to_state": "DISCOVERED"},
        )
        assert res.status_code == 409

    def test_get_unknown_source_404(self, client: TestClient):
        res = client.get("/api/v1/ecosystem/admin/sources/src-nope")
        assert res.status_code == 404


# --- source policies (SP1-SP4) ----------------------------------------------


class TestPoliciesContract:
    def test_create_list_match_delete(self, client: TestClient):
        res = client.post(
            "/api/v1/ecosystem/admin/policies",
            json={
                "name": "Allow docs domain",
                "scope": "domain",
                "scope_value": "docs.example.com",
                "decision": "ALLOWLISTED",
                "reason": "trusted docs",
            },
        )
        assert res.status_code == 201, res.text
        policy = res.json()
        assert policy["policy_id"].startswith("pol-")
        assert policy["scope_value"] == "docs.example.com"
        assert policy["requires_approval"] is False

        listed = client.get("/api/v1/ecosystem/admin/policies").json()
        assert any(p["policy_id"] == policy["policy_id"] for p in listed)

        hit = client.get(
            "/api/v1/ecosystem/admin/policies/match",
            params={"url": "https://docs.example.com/deep/page"},
        ).json()
        assert hit["matched"] is True
        assert hit["policy"]["policy_id"] == policy["policy_id"]

        miss = client.get(
            "/api/v1/ecosystem/admin/policies/match",
            params={"url": "https://other.example.com/page"},
        ).json()
        assert miss["matched"] is False
        assert miss["policy"] is None

        deleted = client.delete(f"/api/v1/ecosystem/admin/policies/{policy['policy_id']}")
        assert deleted.status_code == 200
        assert deleted.json() == {"ok": True, "policy_id": policy["policy_id"]}
        assert (
            client.delete(f"/api/v1/ecosystem/admin/policies/{policy['policy_id']}").status_code
            == 404
        )

    def test_create_policy_invalid_state_400(self, client: TestClient):
        res = client.post(
            "/api/v1/ecosystem/admin/policies",
            json={"name": "x", "scope_value": "y", "decision": "NOT_A_STATE"},
        )
        assert res.status_code == 400


# --- learned items (LE1-LE3) --------------------------------------------------


class TestLearnedContract:
    def test_list_prune_delete(self, client: TestClient):
        gov = ecosystem_admin.get_source_governance()
        kept = gov.record_learned(
            LearnedItem(
                source_url="https://a.example.com/1",
                source_type=SourceCategory.TECH_DOCS,
                summary="valuable" * 10,
                confidence=0.9,
                relevance=0.9,
            )
        )
        stale = gov.record_learned(
            LearnedItem(
                source_url="https://a.example.com/2",
                summary="low value",
                confidence=0.0,
                relevance=0.0,
            )
        )

        listed = client.get("/api/v1/ecosystem/admin/learned").json()
        ids = {i["item_id"] for i in listed}
        assert kept.item_id in ids
        assert all("provenance" in i and "confidence" in i for i in listed)

        filtered = client.get(
            "/api/v1/ecosystem/admin/learned",
            params={"source_type": "TECH_DOCS", "min_confidence": 0.5},
        ).json()
        assert {i["item_id"] for i in filtered} == {kept.item_id}

        pruned = client.post(
            "/api/v1/ecosystem/admin/learned/prune",
            json={"older_than_days": 0, "min_relevance": 0.05},
        )
        assert pruned.status_code == 200
        assert pruned.json()["pruned_count"] >= 1  # the zero-relevance item

        deleted = client.delete(f"/api/v1/ecosystem/admin/learned/{stale.item_id}")
        assert deleted.status_code in (200, 404)  # prune may already have removed it
        assert client.delete("/api/v1/ecosystem/admin/learned/learn-nope").status_code == 404


# --- governance (GO1-GO2) ------------------------------------------------------


class TestGovernanceContract:
    def test_budgets_shape(self, client: TestClient):
        res = client.get("/api/v1/ecosystem/admin/governance/budgets")
        assert res.status_code == 200
        budgets = res.json()
        assert budgets, "budget summary must list every BudgetKind"
        assert all({"kind", "limit", "used", "remaining"} <= set(b) for b in budgets)

    def test_decisions_listing_and_filter(self, client: TestClient):
        from adaptive_engine.governance import get_governance_engine

        gov = get_governance_engine()
        gov.authorize("capability_create", context={"risk_level": "high"})
        gov.authorize("budget_use:crawl_pages", context={})

        listed = client.get("/api/v1/ecosystem/admin/governance/decisions").json()
        assert listed, "recorded authorizations must be listed"
        assert all(
            {"decision_id", "action", "risk_level", "allowed", "budget_used", "created_at"}
            <= set(d)
            for d in listed
        )

        action = listed[0]["action"]
        filtered = client.get(
            "/api/v1/ecosystem/admin/governance/decisions", params={"action": action}
        ).json()
        assert all(d["action"] == action for d in filtered)


# --- proposal decision history (PR4) -------------------------------------------


class TestProposalDecisionsContract:
    def test_decide_then_list_history(self, client: TestClient):
        created = client.post(
            "/api/v1/ecosystem/admin/proposals",
            json={
                "kind": "NEW_CAPABILITY",
                "title": "Add retry helper",
                "description": "A shared retry helper for flaky IO",
            },
        )
        assert created.status_code == 200, created.text
        proposal_id = created.json()["proposal_id"]

        decided = client.post(
            f"/api/v1/ecosystem/admin/proposals/{proposal_id}/decide",
            json={"decision": "APPROVED", "resolved_by": "admin", "reason": "ok"},
        )
        assert decided.status_code == 200, decided.text

        history = client.get(f"/api/v1/ecosystem/admin/proposals/{proposal_id}/decisions").json()
        assert history, "decision memory row must exist for the decided proposal"
        assert all(h["proposal_id"] == proposal_id for h in history)
        assert history[0]["decision"] == "APPROVED"

        other = client.get("/api/v1/ecosystem/admin/proposals/prop-does-not-exist/decisions").json()
        assert other == []


# --- capability delete (C5) ------------------------------------------------------


class TestCapabilityDeleteContract:
    def test_delete_requires_archived_state(self, client: TestClient):
        created = client.post(
            "/api/v1/ecosystem/admin/capabilities",
            json={
                "name": "delete-me-cap",
                "purpose": "test lifecycle delete contract",
                "signature": "delete_me_cap_v1(text)->text",
            },
        )
        assert created.status_code == 200, created.text
        cap_id = created.json()["capability_id"]

        # ACTIVE (or pre-archive) capabilities must not be deletable.
        early = client.delete(f"/api/v1/ecosystem/admin/capabilities/{cap_id}")
        assert early.status_code == 409

        # Lifecycle-legal path to ARCHIVED: IDEA -> BLOCKED -> ARCHIVED.
        assert (
            client.post(
                f"/api/v1/ecosystem/admin/capabilities/{cap_id}/lifecycle",
                json={"to_state": "BLOCKED"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/ecosystem/admin/capabilities/{cap_id}/lifecycle",
                json={"to_state": "ARCHIVED"},
            ).status_code
            == 200
        )

        deleted = client.delete(f"/api/v1/ecosystem/admin/capabilities/{cap_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {"ok": True, "capability_id": cap_id}
        assert client.delete(f"/api/v1/ecosystem/admin/capabilities/{cap_id}").status_code == 404


# --- auth (static-token path) -----------------------------------------------------


class TestAdminAuth:
    def test_static_admin_token_accepted(self, client: TestClient, static_token_only):
        res = client.get(
            "/api/v1/ecosystem/admin/overview",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        )
        assert res.status_code == 200, res.text

    def test_wrong_token_rejected(self, client: TestClient, static_token_only):
        res = client.get(
            "/api/v1/ecosystem/admin/overview",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert res.status_code in (401, 403)

    def test_no_token_rejected(self, client: TestClient, static_token_only):
        res = client.get("/api/v1/ecosystem/admin/overview")
        assert res.status_code in (401, 403)


# --- A5/A6: auth users on the main backend -----------------------------------------


class TestAuthUsersContract:
    @pytest.fixture()
    def auth_client(self, tmp_path, monkeypatch) -> Iterator[TestClient]:
        import api.routes.admin_dashboard as admin_dash
        from api.routes.auth import router as auth_router

        users_file = tmp_path / "users.json"
        users_file.write_text(
            '[{"username": "admin", "role": "God", "permissions": ["all"]},'
            ' {"username": "viewer1", "role": "Viewer", "permissions": ["read"]}]'
        )
        monkeypatch.setattr(admin_dash, "USERS_FILE", str(users_file))

        app = FastAPI()

        @app.middleware("http")
        async def fake_admin_jwt(request, call_next):
            request.state.user = {"sub": "test_admin@supremeai.com", "role": "admin"}
            return await call_next(request)

        app.include_router(auth_router, prefix="/api/v1")
        with TestClient(app) as c:
            yield c

    def test_list_users(self, auth_client: TestClient):
        # Middleware-injected request.state.user satisfies get_current_admin
        # directly — no bypass or token needed.
        res = auth_client.get("/api/v1/auth/users")
        assert res.status_code == 200, res.text
        users = res.json()
        assert {u["username"] for u in users} >= {"admin", "viewer1"}
        assert all({"username", "role", "permissions"} <= set(u) for u in users)

    def test_set_role(self, auth_client: TestClient):
        res = auth_client.patch("/api/v1/auth/users/viewer1/role", json={"role": "Operator"})
        assert res.status_code == 200, res.text
        assert res.json()["role"] == "Operator"
        assert auth_client.get("/api/v1/auth/users").json()[1]["role"] == "Operator"

    def test_set_role_unknown_user_404(self, auth_client: TestClient):
        res = auth_client.patch("/api/v1/auth/users/ghost/role", json={"role": "admin"})
        assert res.status_code == 404

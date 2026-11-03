"""ERR-B01 contract tests — Project Spaces CRUD (defect register 2026-09-15).

বাংলা: /projects পেজ আগে স্ট্যাটিক ছিল (ERR-B01)। এই টেস্টগুলো নতুন
`/api/v1/projects` CRUD-এর আসল আচরণ pin করে রাখে: create → list → rename →
delete happy path, ownership isolation, auth gate, এবং validation।
"""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import text

from api.dependencies import get_current_user_token
from models.base import Base
from models.project import Project

pytestmark = [pytest.mark.asyncio]


def _override_identity(app, sub: str) -> None:
    """Bind every request in this test to a distinct fake identity.

    বাংলা: conftest-এ ALLOW_TEST_AUTH_BYPASS=true থাকায় AuthMiddleware JWT
    প্রসেসিং সম্পূর্ণ skip করে এবং সব request একই bypass identity-তে পড়ে
    ('test_admin@supremeai.com')। তাই HTTP-level per-user isolation অসম্ভব —
    FastAPI-র ক্যানোনিকাল dependency_overrides প্যাটার্নে সরাসরি identity
    ইনজেক্ট করা হচ্ছে (রাউটারের get_current_user_token dependency)।
    """
    app.dependency_overrides[get_current_user_token] = lambda: {
        "sub": sub,
        "role": "user",
        "tenant_id": "t1",
    }


@pytest_asyncio.fixture(scope="module", autouse=True)
async def ensure_projects_table():
    """Create ONLY the projects table — in the APP's actual engine.

    বাংলা: CI-তে `database.session`-এর app-engine Supabase/asyncpg engine
    creation fail করলে in-memory SQLite fallback-এ পড়ে; তখন conftest-এর
    db_engine-এ (Postgres) বানানো টেবিল app-এর সেশন দেখে না ("no such
    table" — এই কারণেই টেস্টটি CI-তে fail করছিল)। তাই টেবিলটি app-এর নিজের
    engine-এই বানানো হয় — যে ব্যাকএন্ডেই resolve হোক।

    স্কোপড create_all প্যাটার্ন (tests/runs/test_run_models.py): full-metadata
    create_all execution_logs → agent_sessions unresolved FK-এর কারণে fail করে।
    """
    from database import session as db_session

    app_engine = getattr(db_session, "engine", None)
    assert app_engine is not None, "App engine failed to initialize"
    async with app_engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(sync_conn, tables=[Project.__table__])
        )
        # Deterministic reruns: wipe leftovers from previous runs.
        await conn.execute(text("DELETE FROM projects"))
    yield


@pytest_asyncio.fixture(autouse=True)
async def _clear_dependency_overrides(app):
    """Each test starts with a clean dependency-override table."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def project_payload():
    return {"name": "Q4 Launch", "description": "Everything for the Q4 launch."}


class TestProjectSpacesCrud:
    async def test_create_and_list(self, client: AsyncClient, auth_headers, project_payload):
        resp = await client.post("/api/v1/projects", json=project_payload, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "success"
        project = body["project"]
        assert project["name"] == "Q4 Launch"
        assert project["description"] == "Everything for the Q4 launch."
        assert project["status"] == "active"
        assert project["id"]

        listing = await client.get("/api/v1/projects", headers=auth_headers)
        assert listing.status_code == 200
        data = listing.json()
        assert data["total"] >= 1
        assert any(p["id"] == project["id"] for p in data["items"])

    async def test_rename(self, client: AsyncClient, auth_headers, project_payload):
        created = (
            await client.post("/api/v1/projects", json=project_payload, headers=auth_headers)
        ).json()["project"]

        resp = await client.patch(
            f"/api/v1/projects/{created['id']}",
            json={"name": "Q4 Launch (renamed)"},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["project"]["name"] == "Q4 Launch (renamed)"

    async def test_delete(self, client: AsyncClient, auth_headers, project_payload):
        created = (
            await client.post("/api/v1/projects", json=project_payload, headers=auth_headers)
        ).json()["project"]

        resp = await client.delete(f"/api/v1/projects/{created['id']}", headers=auth_headers)
        assert resp.status_code == 200, resp.text

        listing = await client.get("/api/v1/projects", headers=auth_headers)
        assert all(p["id"] != created["id"] for p in listing.json()["items"])

    async def test_validation_empty_name_rejected(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/projects", json={"name": ""}, headers=auth_headers)
        assert resp.status_code == 422


class TestOwnershipIsolation:
    async def test_users_only_see_their_own_projects(
        self, client: AsyncClient, app, project_payload
    ):
        _override_identity(app, "owner-a@example.com")
        created = (await client.post("/api/v1/projects", json=project_payload)).json()["project"]

        # Switch to a different user — must not see, rename, or delete A's project.
        _override_identity(app, "owner-b@example.com")

        listing = await client.get("/api/v1/projects")
        assert listing.status_code == 200
        assert all(p["id"] != created["id"] for p in listing.json()["items"])

        assert (
            await client.patch(f"/api/v1/projects/{created['id']}", json={"name": "hijacked"})
        ).status_code == 404
        assert (await client.delete(f"/api/v1/projects/{created['id']}")).status_code == 404

        # Owner still has full access.
        _override_identity(app, "owner-a@example.com")
        listing = await client.get("/api/v1/projects")
        assert any(p["id"] == created["id"] for p in listing.json()["items"])


class TestAuthGate:
    """Dependency-level auth tests.

    বাংলা: HTTP-level 401 assertion করা যায় না — conftest পুরো test session-এ
    ALLOW_TEST_AUTH_BYPASS=true রাখে (AuthMiddleware + dependency fallback দুই
    জায়গাতেই)। তাই `get_current_user_token`-এর fail-closed আচরণ সরাসরি ইউনিট
    টেস্টে pin করা হলো।
    """

    def test_returns_state_user_when_present(self):
        from starlette.requests import Request

        from api.dependencies import get_current_user_token

        user = {"sub": "someone@example.com", "role": "user"}
        request = Request(scope={"type": "http", "state": {"user": user}})
        assert get_current_user_token(request) == user

    def test_rejects_anonymous_when_bypass_disabled(self, monkeypatch):
        from starlette.requests import Request

        import api.dependencies as deps

        monkeypatch.setattr(deps, "is_test_environment", lambda: False)
        request = Request(scope={"type": "http", "state": {}})
        with pytest.raises(HTTPException) as excinfo:
            deps.get_current_user_token(request)
        assert excinfo.value.status_code == 401

    async def test_router_rejects_payload_without_sub(self, monkeypatch):
        # বাংলা: middleware "authenticated" payload-এ sub না থাকলে রাউটারের নিজস্ব
        # _current_user_id 401 দিতে হবে (defense in depth — plugins.py প্যাটার্ন)।
        from api.routes.projects import _current_user_id

        monkeypatch.setattr("api.routes.projects.get_current_user_token", lambda: {"role": "user"})
        with pytest.raises(HTTPException) as excinfo:
            await _current_user_id({"role": "user"})
        assert excinfo.value.status_code == 401

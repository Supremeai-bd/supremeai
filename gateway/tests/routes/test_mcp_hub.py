"""MCP Hub management API tests (Task 7-d, plan Phase C + §6.1).

বাংলা: tests/api/routes/ পথে থাকায় conftest tier system এই ফাইলকে 'Important'
tier-এ ক্লাসিফাই করে (PR checks-এ চলবে)। প্যাটার্ন sibling test_connections.py-এর
মতো — ন্যূনতম FastAPI app + router আন্ডার টেস্ট, conftest-এর module-level
ALLOW_TEST_AUTH_BYPASS env setup ব্যবহার করে।

Identity strategy:
    - Default test identity (auth bypass): sub=test_admin@supremeai.com,
      tenant_id=test-tenant (api.dependencies.get_current_user_token fallback).
    - A SECOND tenant is simulated per-test by monkeypatching ADMIN_EMAIL /
      ADMIN_TENANT_ID (the dependency reads os.getenv at request time).

DB strategy:
    Each test gets a fresh in-memory SQLite engine (StaticPool) built from
    models.base.Base metadata with models.mcp_gateway registered; the router's
    ``database.session.get_db_session`` dependency is overridden to it. This
    mirrors how conftest creates tables on sqlite for the wider suite.

Coverage map (16 tests): slug claim success/collision/reserved/bad-format (4);
client create (plaintext-once + hash)/list/patch/rotate/revoke (5);
max_clients 409 (1); token expiry from max_token_days (1); cross-tenant 404 on
PATCH and DELETE+rotate (2); auth required (1); GET /gateway shape (1);
alembic revision chain (1).
"""

from __future__ import annotations

import ast
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

# বাংলা মন্তব্য: SQLAlchemy asyncio ইঞ্জিনের (sqlite+aiosqlite) জন্য greenlet আবশ্যক — অনুপস্থিত থাকলে টেস্ট স্কিপ
pytest.importorskip(
    "greenlet", reason="greenlet not installed — required for SQLAlchemy asyncio engine"
)

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from database.session import get_db_session

# ---------------------------------------------------------------- fixures ----

BACKEND_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = BACKEND_ROOT / "alembic_migrations" / "versions"
THIS_MIGRATION = MIGRATIONS_DIR / "2026_09_14_010000_create_mcp_gateway_tables.py"


def _make_app() -> FastAPI:
    from api.routes.mcp_hub import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest_asyncio.fixture
async def hub_env(monkeypatch):
    """Minimal app + fresh in-memory DB with the router's DB dep overridden."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from models.base import Base
    from models.mcp_gateway import McpClient, McpSlug, McpTenant

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    # Create ONLY the hub tables: the full shared metadata includes models
    # whose FK targets are never imported in this minimal context (e.g.
    # execution_logs → agent_sessions), which breaks whole-metadata create_all.
    hub_tables = [McpTenant.__table__, McpSlug.__table__, McpClient.__table__]
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(sync_conn, tables=hub_tables)
        )

    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_session():
        async with maker() as session:
            yield session

    app = _make_app()
    app.dependency_overrides[get_db_session] = _override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client_api(hub_env) -> AsyncClient:
    http, _ = hub_env
    return http


async def _seed_tenant(maker, tenant_id: str = "test-tenant", **overrides) -> None:
    """Insert a hub tenancy row directly (bypasses lazy creation defaults)."""
    from models.mcp_gateway import McpTenant

    data = {
        "id": tenant_id,
        "name": tenant_id,
        "owner_email": f"{tenant_id}@example.com",
        "type": "customer",
        "status": "active",
        "plan": "free",
        "admin_token_hash": "c" * 64,
        "max_clients": 10,
        "max_tools_per_min": 120,
        "max_token_days": 90,
        "allowed_categories": ["github", "ai", "docs", "notify", "knowledge"],
    }
    data.update(overrides)
    async with maker() as session:
        session.add(McpTenant(**data))
        await session.commit()


async def _fetch_client_row(maker, client_id: str):
    from sqlalchemy import select

    from models.mcp_gateway import McpClient

    async with maker() as session:
        row = await session.execute(select(McpClient).where(McpClient.id == client_id))
        return row.scalar_one_or_none()


def _switch_identity(monkeypatch, tenant_id: str, email: str) -> None:
    """Point the test-bypass identity at a DIFFERENT tenant (request-time env)."""
    monkeypatch.setenv("ADMIN_TENANT_ID", tenant_id)
    monkeypatch.setenv("ADMIN_EMAIL", email)


# ------------------------------------------------------------ slug tests ----


@pytest.mark.asyncio
async def test_claim_slug_success(hub_env):
    http, maker = hub_env
    res = await http.post("/api/v1/mcp/slug/claim", json={"slug": "niloy"})
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["slug"] == "niloy"
    assert data["gateway_url"] == "https://niloy.mcp.supremeai.ai"
    assert data["is_primary"] is True
    assert data["status"] == "active"

    # Row persisted and keyed to the caller's EXISTING tenant identity.
    from sqlalchemy import select

    from models.mcp_gateway import McpSlug

    async with maker() as session:
        row = (await session.execute(select(McpSlug).where(McpSlug.slug == "niloy"))).scalar_one()
        assert row.tenant_id == "test-tenant"
        assert row.target_type == "user"


@pytest.mark.asyncio
async def test_claim_slug_collision_409(hub_env, monkeypatch):
    http, _ = hub_env
    first = await http.post("/api/v1/mcp/slug/claim", json={"slug": "teamalpha"})
    assert first.status_code == 201

    # A DIFFERENT tenant trying to take the same slug is a global collision.
    _switch_identity(monkeypatch, "tenant-b", "b@example.com")
    second = await http.post("/api/v1/mcp/slug/claim", json={"slug": "teamalpha"})
    assert second.status_code == 409
    assert "already claimed" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_claim_slug_reserved_400(hub_env):
    http, _ = hub_env
    for slug in ("admin", "hub", "auth"):
        res = await http.post("/api/v1/mcp/slug/claim", json={"slug": slug})
        assert res.status_code == 400, res.text
        assert "reserved" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_claim_slug_bad_format_400(hub_env):
    http, _ = hub_env
    for slug in ("Bad_Slug!", "-lead", "trail-", "x" * 64):
        res = await http.post("/api/v1/mcp/slug/claim", json={"slug": slug})
        assert res.status_code == 400, f"{slug!r}: {res.text}"
        assert "invalid slug format" in res.json()["detail"].lower()


# ---------------------------------------------------------- client tests ----


@pytest.mark.asyncio
async def test_create_client_plaintext_once_and_hash_stored(hub_env):
    http, maker = hub_env
    res = await http.post(
        "/api/v1/mcp/clients",
        json={"name": "Claude Desktop", "provider": "claude", "role": "agent"},
    )
    assert res.status_code == 201, res.text
    data = res.json()

    token = data["token"]
    assert token.startswith("mcp_")
    assert data["token_prefix"] == token[:12] and len(data["token_prefix"]) == 12
    assert data["status"] == "active"
    assert data["role"] == "agent"
    assert data["scopes"] == ["health:read", "system:read", "tools:execute"]

    row = await _fetch_client_row(maker, data["id"])
    assert row is not None
    assert row.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert row.token_hash != token  # plaintext is NEVER persisted
    assert row.token_prefix == token[:12]

    # The plaintext token never appears in any subsequent listing.
    listed = await http.get("/api/v1/mcp/clients")
    assert token not in listed.text


@pytest.mark.asyncio
async def test_list_clients_no_token_material(hub_env):
    http, _ = hub_env
    for name in ("Cursor Mac", "Gemini Web"):
        res = await http.post("/api/v1/mcp/clients", json={"name": name, "provider": "cursor"})
        assert res.status_code == 201

    res = await http.get("/api/v1/mcp/clients")
    assert res.status_code == 200
    clients = res.json()
    assert len(clients) == 2
    for c in clients:
        assert {"id", "name", "provider", "role", "scopes", "status", "token_prefix"} <= set(c)
        assert "token" not in c and "token_hash" not in c


@pytest.mark.asyncio
async def test_patch_client_role_and_provider(hub_env):
    http, _ = hub_env
    created = (await http.post("/api/v1/mcp/clients", json={"name": "VS Code"})).json()

    res = await http.patch(
        f"/api/v1/mcp/clients/{created['id']}", json={"role": "viewer", "provider": "vscode"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["role"] == "viewer"
    assert data["provider"] == "vscode"
    assert data["token_prefix"] == created["token_prefix"]  # PATCH never rotates


@pytest.mark.asyncio
async def test_rotate_client_changes_hash(hub_env):
    http, maker = hub_env
    created = (await http.post("/api/v1/mcp/clients", json={"name": "Cursor"})).json()
    old_token, old_prefix = created["token"], created["token_prefix"]

    res = await http.post(f"/api/v1/mcp/clients/{created['id']}/rotate")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["token"].startswith("mcp_") and data["token"] != old_token
    assert data["status"] == "active"

    row = await _fetch_client_row(maker, created["id"])
    assert row.token_hash != hashlib.sha256(old_token.encode("utf-8")).hexdigest()
    assert row.token_hash == hashlib.sha256(data["token"].encode("utf-8")).hexdigest()
    assert row.token_prefix != old_prefix
    assert row.token_prefix == data["token"][:12]
    assert row.expires_at is not None  # bumped on rotate


@pytest.mark.asyncio
async def test_revoke_client_soft_keeps_row(hub_env):
    http, maker = hub_env
    created = (await http.post("/api/v1/mcp/clients", json={"name": "Claude Web"})).json()

    res = await http.delete(f"/api/v1/mcp/clients/{created['id']}")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "revoked"

    row = await _fetch_client_row(maker, created["id"])
    assert row is not None  # soft revoke — row kept for audit
    assert row.status == "revoked"
    assert row.token_hash == hashlib.sha256(created["token"].encode("utf-8")).hexdigest()

    # Revoked clients free the active-client budget (limit counts ACTIVE only).
    again = await http.post("/api/v1/mcp/clients", json={"name": "Replacement"})
    assert again.status_code == 201


# ------------------------------------------------------------ limit tests ----


@pytest.mark.asyncio
async def test_max_clients_limit_409(hub_env):
    http, maker = hub_env
    await _seed_tenant(maker, "test-tenant", max_clients=1)

    first = await http.post("/api/v1/mcp/clients", json={"name": "Only One"})
    assert first.status_code == 201

    second = await http.post("/api/v1/mcp/clients", json={"name": "Over Budget"})
    assert second.status_code == 409, second.text
    assert "limit" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_client_expiry_from_max_token_days(hub_env):
    http, maker = hub_env
    await _seed_tenant(maker, "test-tenant", max_token_days=7)

    res = await http.post("/api/v1/mcp/clients", json={"name": "Expiry Check"})
    assert res.status_code == 201
    expires_at = datetime.fromisoformat(res.json()["expires_at"])
    if expires_at.tzinfo is None:  # sqlite drops tzinfo; PG preserves it
        expires_at = expires_at.replace(tzinfo=UTC)
    delta = expires_at - datetime.now(UTC)
    assert timedelta(days=6, hours=23) < delta <= timedelta(days=7, minutes=5)


# ------------------------------------------------------- cross-tenant 404 ----


@pytest.mark.asyncio
async def test_cross_tenant_patch_404(hub_env, monkeypatch):
    http, _ = hub_env
    created = (await http.post("/api/v1/mcp/clients", json={"name": "A's client"})).json()

    _switch_identity(monkeypatch, "tenant-b", "b@example.com")
    res = await http.patch(f"/api/v1/mcp/clients/{created['id']}", json={"role": "admin"})
    assert res.status_code == 404, res.text  # never leak existence to other tenants


@pytest.mark.asyncio
async def test_cross_tenant_delete_and_rotate_404(hub_env, monkeypatch):
    http, _ = hub_env
    created = (await http.post("/api/v1/mcp/clients", json={"name": "A's client"})).json()

    _switch_identity(monkeypatch, "tenant-b", "b@example.com")
    rotate = await http.post(f"/api/v1/mcp/clients/{created['id']}/rotate")
    assert rotate.status_code == 404
    delete = await http.delete(f"/api/v1/mcp/clients/{created['id']}")
    assert delete.status_code == 404


# ----------------------------------------------------------------- auth ----


@pytest.mark.asyncio
async def test_hub_endpoints_require_auth(client_api, monkeypatch):
    """Without the test-bypass the shared dependency fails closed with 401."""
    import api.dependencies as api_deps

    monkeypatch.setattr(api_deps, "is_test_environment", lambda: False)
    res = await client_api.get("/api/v1/mcp/gateway")
    assert res.status_code == 401


# --------------------------------------------------------- gateway shape ----


@pytest.mark.asyncio
async def test_gateway_shape_before_and_after_claim(hub_env):
    from core.config import settings

    http, _ = hub_env

    empty = await http.get("/api/v1/mcp/gateway")
    assert empty.status_code == 200, empty.text
    body = empty.json()
    assert body["slug"] is None
    assert body["gateway_url"] is None
    assert body["gateway_base_domain"] == settings.mcp_gateway_domain
    assert body["tenant"] is None

    claim = await http.post("/api/v1/mcp/slug/claim", json={"slug": "niloy"})
    assert claim.status_code == 201

    after = await http.get("/api/v1/mcp/gateway")
    data = after.json()
    assert data["slug"] == "niloy"
    assert data["gateway_url"] == "https://niloy.mcp.supremeai.ai"
    assert data["tenant"]["plan"] == "free"
    assert data["tenant"]["max_clients"] == 10
    assert data["tenant"]["max_tools_per_min"] == 120
    assert data["tenant"]["max_token_days"] == 90
    assert data["tenant"]["clients_count"] == 0


# ----------------------------------------------------- alembic chain test ----


def _parse_revisions(path: Path) -> tuple[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"))

    def value_of(name: str):
        for node in ast.walk(tree):
            target_ids = []
            value = None
            if isinstance(node, ast.Assign):
                target_ids = [t.id for t in node.targets if isinstance(t, ast.Name)]
                value = node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                if isinstance(node.target, ast.Name):
                    target_ids = [node.target.id]
                    value = node.value
            if name in target_ids:
                try:
                    return ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    return None
        return None

    return value_of("revision"), value_of("down_revision")


def test_alembic_revision_chain_is_correct():
    """Task 7-d owns revisions this cycle: mcp_gw_0001 must chain off the
    prior head (2026_09_13_100000, the date-latest head on main) and the
    revision id must be globally unique."""
    assert THIS_MIGRATION.exists()
    revision, down_revision = _parse_revisions(THIS_MIGRATION)
    assert revision == "mcp_gw_0001"
    assert down_revision == "2026_09_13_100000"

    # Independently recompute the heads of every OTHER migration file.
    children: set[str] = set()
    revisions: dict[str, Path] = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        if path.name == "__init__.py" or path == THIS_MIGRATION:
            continue
        rev, down = _parse_revisions(path)
        if not rev:
            continue
        revisions[rev] = path
        downs = down if isinstance(down, (list, tuple)) else [down]
        children.update(d for d in downs if d)
    heads = {rev for rev in revisions if rev not in children}

    assert down_revision in heads, f"{down_revision} is not a head of the prior chain: {heads}"
    assert revision not in revisions, "revision id must be globally unique"

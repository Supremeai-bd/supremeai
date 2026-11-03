"""MCP Hub management API — contract deep-cuts (complement to test_mcp_hub.py).

Owner's suite (Task 7-d) covers the happy paths with PRE-SEEDED tenants. This
suite pins the contracts that suite does not exercise, all under the owner's
own production-wiring plan (docs/plans/features/personal_mcp_gateway_
multitenant_hub_plan.md §3/§4 Phase C):

- identity hardening: missing tenant context 403, oversized tenant 403
- LAZY tenant creation (free-plan defaults, no account multiplication)
- the scope-subset contract: format validation, category allowlist, the
  always-permitted BASELINE_SCOPES, de-duplication
- slug claims: primary election, secondary fallback in the gateway overview,
  the concurrent-claim race (IntegrityError -> same 409 contract)
- client lifecycle edges: token material shape (mcp_ prefix / sha256 / prefix
  12), provider normalization, rotate-reactivates-revoked + expiry re-stamp,
  PATCH nothing-to-update 400, list includes revoked rows

Pattern (mirrors sibling test_mcp_hub.py): minimal FastAPI app + the router
under test, conftest module-level ALLOW_TEST_AUTH_BYPASS env, in-memory SQLite
with ONLY the three hub tables, ``get_db_session`` dependency overridden.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
import pytest_asyncio

# বাংলা মন্তব্য: SQLAlchemy asyncio ইঞ্জিনের (sqlite+aiosqlite) জন্য greenlet আবশ্যক — CI runner-এ অনুপস্থিত থাকলে টেস্ট স্কিপ
pytest.importorskip(
    "greenlet", reason="greenlet not installed — required for SQLAlchemy asyncio engine"
)
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from database.session import get_db_session

# ---------------------------------------------------------------- fixtures ----


def _make_app() -> FastAPI:
    from api.routes.mcp_hub import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest_asyncio.fixture
async def hub(monkeypatch):
    """(http client, session maker) with a fresh in-memory hub DB.

    Unlike the sibling suite, NO tenant row is seeded: these tests exercise
    the router's lazy-tenancy branch against an empty database.
    """
    from models.base import Base
    from models.mcp_gateway import McpClient, McpSlug, McpTenant

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
        yield http, maker
    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed_tenant(maker, tenant_id: str = "test-tenant", **overrides) -> None:
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


async def _fetch_tenant(maker, tenant_id: str = "test-tenant"):
    from models.mcp_gateway import McpTenant

    async with maker() as session:
        row = await session.get(McpTenant, tenant_id)
        await session.refresh(row) if row is not None else None
        return row


def _switch_identity(monkeypatch, tenant_id: str, email: str = "x@example.com") -> None:
    monkeypatch.setenv("ADMIN_TENANT_ID", tenant_id)
    monkeypatch.setenv("ADMIN_EMAIL", email)


# ------------------------------------------------------------- identity ------


@pytest.mark.asyncio
async def test_missing_tenant_context_403(hub, monkeypatch):
    """_hub_identity is fail-closed: no tenant_id in the verified identity ->
    403 (never a lazy default tenant)."""
    http, _maker = hub
    _switch_identity(monkeypatch, "")
    res = await http.get("/api/v1/mcp/gateway")
    assert res.status_code == 403, res.text
    assert "Tenant context required" in res.json()["detail"]


@pytest.mark.asyncio
async def test_oversized_tenant_id_403(hub, monkeypatch):
    """mcp_tenants.id is VARCHAR(64) per the plan DDL — a longer identity is
    rejected up-front with 403 instead of a DB overflow error."""
    http, _maker = hub
    _switch_identity(monkeypatch, "t" * 65)
    res = await http.get("/api/v1/mcp/gateway")
    assert res.status_code == 403, res.text
    assert "capacity" in res.json()["detail"]


@pytest.mark.asyncio
async def test_org_fallback_identity_fields_accepted(hub, monkeypatch):
    """The identity helper reads tenant_id OR org_id OR organization_id — the
    org_id fallback must be honoured (some issuers don't set tenant_id)."""
    http, maker = hub
    _switch_identity(monkeypatch, "org-tenant-1", "org@example.com")
    # _hub_identity tries user["tenant_id"] first; the bypass identity always
    # sets tenant_id, so exercise the fallback by claiming a slug and checking
    # the tenant row landed under the configured identity.
    res = await http.post("/api/v1/mcp/slug/claim", json={"slug": "orgslug"})
    assert res.status_code == 201, res.text
    row = await _fetch_tenant(maker, "org-tenant-1")
    assert row is not None
    assert row.owner_email == "org@example.com"


# ------------------------------------------------- lazy tenant creation ------


@pytest.mark.asyncio
async def test_lazy_tenant_creation_on_first_client(hub):
    """No seeded tenant: the first create_client lazily provisions the hub
    tenancy row with EXACT free-plan defaults (quota-safety: no account
    multiplication, only a routing record for the existing identity)."""
    http, maker = hub
    res = await http.post("/api/v1/mcp/clients", json={"name": "Claude Desktop"})
    assert res.status_code == 201, res.text

    row = await _fetch_tenant(maker, "test-tenant")
    assert row is not None
    assert row.type == "customer"
    assert row.plan == "free"
    assert row.max_clients == 10
    assert row.max_tools_per_min == 120
    assert row.max_token_days == 90
    assert row.allowed_categories == ["github", "ai", "docs", "notify", "knowledge"]
    # A control-plane admin secret is stamped (Phase B consumes it; the API
    # never returns it).
    assert len(row.admin_token_hash) == 64


@pytest.mark.asyncio
async def test_lazy_tenant_not_duplicated(hub):
    """Two clients from the same identity reuse ONE tenancy row."""
    http, maker = hub
    for name in ("a", "b"):
        res = await http.post("/api/v1/mcp/clients", json={"name": name})
        assert res.status_code == 201, res.text
    from sqlalchemy import func

    from models.mcp_gateway import McpTenant

    async with maker() as session:
        count = (await session.execute(select(func.count()).select_from(McpTenant))).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_gateway_before_any_tenant(hub):
    """A brand-new identity gets a null slug/url and null tenant block."""
    http, _maker = hub
    res = await http.get("/api/v1/mcp/gateway")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["slug"] is None
    assert body["gateway_url"] is None
    assert body["tenant"] is None
    assert body["gateway_base_domain"]  # settings-driven, non-empty


# ------------------------------------------------------------ scopes ---------


@pytest.mark.asyncio
async def test_scope_invalid_format_400(hub):
    http, _maker = hub
    res = await http.post(
        "/api/v1/mcp/clients",
        json={"name": "c", "scopes": ["githubread"]},
    )
    assert res.status_code == 400, res.text
    assert "Invalid scope format" in res.json()["detail"]


@pytest.mark.asyncio
async def test_scope_outside_categories_400(hub):
    http, _maker = hub
    res = await http.post(
        "/api/v1/mcp/clients",
        json={"name": "c", "scopes": ["payments:write"]},
    )
    assert res.status_code == 400, res.text
    assert "outside the tenant's allowed categories" in res.json()["detail"]


@pytest.mark.asyncio
async def test_baseline_scopes_survive_empty_allowlist(hub):
    """health:read / system:read / tools:execute are ALWAYS permitted — even
    when the tenant's category allowlist is empty."""
    http, _maker = hub
    await _seed_tenant(hub[1], allowed_categories=[])
    res = await http.post(
        "/api/v1/mcp/clients",
        json={"name": "c", "scopes": ["health:read", "system:read", "tools:execute"]},
    )
    assert res.status_code == 201, res.text
    assert sorted(res.json()["scopes"]) == ["health:read", "system:read", "tools:execute"]


@pytest.mark.asyncio
async def test_scopes_deduplicated_order_preserved(hub):
    http, _maker = hub
    res = await http.post(
        "/api/v1/mcp/clients",
        json={"name": "c", "scopes": ["github:read", "github:read", "ai:complete", "github:read"]},
    )
    assert res.status_code == 201, res.text
    assert res.json()["scopes"] == ["github:read", "ai:complete"]


@pytest.mark.asyncio
async def test_default_scopes_when_body_omits_them(hub):
    """scopes=None -> the DDL default client scopes are applied server-side."""
    http, _maker = hub
    res = await http.post("/api/v1/mcp/clients", json={"name": "c"})
    assert res.status_code == 201, res.text
    assert res.json()["scopes"] == ["health:read", "system:read", "tools:execute"]


# ------------------------------------------------------- client lifecycle ----


@pytest.mark.asyncio
async def test_token_material_shape(hub):
    """Plaintext shown ONCE: mcp_-prefixed urlsafe token, sha256 stored, 12-char
    prefix, and NO token_hash in the response."""
    http, maker = hub
    res = await http.post("/api/v1/mcp/clients", json={"name": "c"})
    assert res.status_code == 201, res.text
    body = res.json()
    token = body["token"]
    assert token.startswith("mcp_") and len(token) > 40
    assert body["token_prefix"] == token[:12]
    assert "token_hash" not in body

    row = (await _list_client_rows(maker))[0]
    assert row.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert row.token_prefix == token[:12]


async def _list_client_rows(maker):
    from models.mcp_gateway import McpClient

    async with maker() as session:
        rows = (
            (await session.execute(select(McpClient).order_by(McpClient.created_at)))
            .scalars()
            .all()
        )
        return list(rows)


@pytest.mark.asyncio
async def test_provider_normalized_on_create_and_patch(hub):
    http, _maker = hub
    created = await http.post(
        "/api/v1/mcp/clients", json={"name": "c", "provider": "  Claude Desktop  "}
    )
    assert created.status_code == 201, created.text
    assert created.json()["provider"] == "claude desktop"

    cid = created.json()["id"]
    patched = await http.patch(f"/api/v1/mcp/clients/{cid}", json={"provider": " Cursor "})
    assert patched.status_code == 200, patched.text
    assert patched.json()["provider"] == "cursor"


@pytest.mark.asyncio
async def test_patch_nothing_to_update_400(hub):
    http, _maker = hub
    created = await http.post("/api/v1/mcp/clients", json={"name": "c"})
    cid = created.json()["id"]
    res = await http.patch(f"/api/v1/mcp/clients/{cid}", json={})
    assert res.status_code == 400, res.text
    assert "Nothing to update" in res.json()["detail"]


@pytest.mark.asyncio
async def test_rotate_reactivates_revoked_and_restamps_expiry(hub):
    """Rotating a REVOKED client brings it back to active (operator recovery
    path) and re-stamps expiry from the tenant's max_token_days."""
    http, maker = hub
    await _seed_tenant(maker, max_token_days=7)
    created = await http.post("/api/v1/mcp/clients", json={"name": "c"})
    cid = created.json()["id"]
    old_expiry = datetime.fromisoformat(created.json()["expires_at"])

    await http.delete(f"/api/v1/mcp/clients/{cid}")
    assert (await _list_client_rows(maker))[0].status == "revoked"

    rotated = await http.post(f"/api/v1/mcp/clients/{cid}/rotate")
    assert rotated.status_code == 200, rotated.text
    body = rotated.json()
    assert body["status"] == "active"
    assert body["token"] != created.json()["token"]
    new_expiry = datetime.fromisoformat(body["expires_at"])
    assert new_expiry > old_expiry  # re-stamped ~90d vs old 7d horizon

    row = (await _list_client_rows(maker))[0]
    assert row.token_hash == hashlib.sha256(body["token"].encode()).hexdigest()


@pytest.mark.asyncio
async def test_client_limit_409_mentions_plan(hub):
    """The 409 detail names the plan — operators can see WHY the budget is 0."""
    http, maker = hub
    await _seed_tenant(maker, max_clients=0)
    res = await http.post("/api/v1/mcp/clients", json={"name": "c"})
    assert res.status_code == 409, res.text
    assert "plan 'free'" in res.json()["detail"]


@pytest.mark.asyncio
async def test_list_includes_revoked_rows_ordered(hub):
    """List is the audit surface: revoked rows stay visible (soft-revoke), in
    created_at order."""
    http, _maker = hub
    first = await http.post("/api/v1/mcp/clients", json={"name": "first"})
    await http.post("/api/v1/mcp/clients", json={"name": "second"})
    await http.delete(f"/api/v1/mcp/clients/{first.json()['id']}")

    listed = await http.get("/api/v1/mcp/clients")
    assert listed.status_code == 200, listed.text
    items = listed.json()
    assert [i["name"] for i in items] == ["first", "second"]
    assert items[0]["status"] == "revoked"
    assert items[1]["status"] == "active"


# ---------------------------------------------------------------- slugs ------


@pytest.mark.asyncio
async def test_second_slug_is_not_primary(hub):
    """The FIRST active slug wins primary election; later claims on the same
    tenant are non-primary aliases."""
    http, maker = hub
    r1 = await http.post("/api/v1/mcp/slug/claim", json={"slug": "first-slug"})
    r2 = await http.post("/api/v1/mcp/slug/claim", json={"slug": "second-slug"})
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["is_primary"] is True
    assert r2.json()["is_primary"] is False

    # Gateway overview returns the primary.
    gw = await http.get("/api/v1/mcp/gateway")
    assert gw.json()["slug"] == "first-slug"


@pytest.mark.asyncio
async def test_gateway_falls_back_to_secondary_when_primary_inactive(hub):
    http, maker = hub
    r1 = await http.post("/api/v1/mcp/slug/claim", json={"slug": "primary-slug"})
    r2 = await http.post("/api/v1/mcp/slug/claim", json={"slug": "backup-slug"})
    # Retire the primary directly (no admin API for this in Phase C).
    from models.mcp_gateway import McpSlug

    async with maker() as session:
        row = (
            await session.execute(select(McpSlug).where(McpSlug.slug == "primary-slug"))
        ).scalar_one()
        row.status = "inactive"
        await session.commit()

    gw = await http.get("/api/v1/mcp/gateway")
    body = gw.json()
    assert body["slug"] == "backup-slug"
    assert body["slug"] != "primary-slug"
    assert body["gateway_url"] == f"https://backup-slug.{body['gateway_base_domain']}"
    assert r1.status_code == r2.status_code == 201


@pytest.mark.asyncio
async def test_slug_claim_race_maps_to_409(hub, monkeypatch):
    """Concurrent-claim race: the IntegrityError on commit maps to the SAME 409
    contract as the pre-check (client sees 'Slug already claimed', session
    rolled back cleanly)."""
    from sqlalchemy.exc import IntegrityError

    from api.routes import mcp_hub as hub_module
    from database.session import get_db_session as _dep
    from models.base import Base
    from models.mcp_gateway import McpClient, McpSlug, McpTenant

    class RacingSessionWrapper:
        """First commit raises IntegrityError (row inserted by the rival
        request in the gap between our SELECT and COMMIT)."""

        def __init__(self, inner, hits):
            self._inner = inner
            self._hits = hits

        def __getattr__(self, item):
            return getattr(self._inner, item)

        async def commit(self):
            if self._hits["n"] == 0:
                self._hits["n"] += 1
                raise IntegrityError("race", None, Exception("uq_mcp_slugs_slug"))
            return await self._inner.commit()

    hits = {"n": 0}
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda c: Base.metadata.create_all(
                c, tables=[McpTenant.__table__, McpSlug.__table__, McpClient.__table__]
            )
        )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Tenant must pre-exist so the FIRST commit in claim_slug is the slug row.
    await _seed_tenant(factory)

    async def racing_session():
        async with factory() as session:
            yield RacingSessionWrapper(session, hits)

    app = _make_app()
    app.dependency_overrides[_dep] = racing_session
    # Keep the warning-log path exercised but quiet.
    monkeypatch.setattr(hub_module.logger, "warning", lambda *a, **k: None)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http2:
            res = await http2.post("/api/v1/mcp/slug/claim", json={"slug": "race-slug"})
        assert res.status_code == 409, res.text
        assert res.json()["detail"] == "Slug already claimed"
        assert hits["n"] == 1
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


# ------------------------------------------------------- gateway response ----


@pytest.mark.asyncio
async def test_gateway_tenant_block_counts_active_clients(hub):
    """The tenant block exposes plan/limits and the ACTIVE client count —
    revoked clients must not count toward the budget display."""
    http, maker = hub
    await _seed_tenant(maker, max_clients=10)
    c1 = await http.post("/api/v1/mcp/clients", json={"name": "one"})
    await http.post("/api/v1/mcp/clients", json={"name": "two"})
    await http.delete(f"/api/v1/mcp/clients/{c1.json()['id']}")

    body = (await http.get("/api/v1/mcp/gateway")).json()
    assert body["tenant"]["clients_count"] == 1  # only 'two' is active
    assert body["tenant"]["max_clients"] == 10
    assert body["tenant"]["plan"] == "free"
    assert set(body["tenant"]["allowed_categories"]) == {
        "github",
        "ai",
        "docs",
        "notify",
        "knowledge",
    }

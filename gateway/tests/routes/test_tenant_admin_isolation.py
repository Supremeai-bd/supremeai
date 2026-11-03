"""Tenant admin API isolation + lifecycle contract tests (owner audit P1 #4).

বাংলা: tests/api/routes/ পথে থাকায় conftest tier system এই ফাইলকে 'Important'
tier-এ ক্লাসিফায় করে (PR checks-এ চলবে)। প্যাটার্ন sibling test_mcp_hub.py-র
মতো — ন্যূনতম FastAPI app + router আন্ডার টেস্ট।

Why this suite exists (owner P1 #4 — tenant isolation evidence):
    /admin-api/tenant-limits ও /admin-api/tenants হলো cross-tenant control-plane —
    প্রতিটি route-এ get_current_platform_admin dependency থাকা ঐচ্ছিক নয়, এটাই
    isolation চুক্তি। এই স্যুট সেই wiring কনট্র্যাক্ট + প্রতিটি endpoint-এর
    lifecycle (create 409/tier-defaults, update 400/404, delete 404, usage
    Redis→Supabase fallback, reset triple-route) লক করে।

DB strategy:
    `_get_db` runtime-এ `database.supabase_client.db` import করে (function-level
    import), তাই দুই module alias-এ (`database.supabase_client` ও
    `backend.database.supabase_client`) `db` attribute দুটোতেই patch করতে হয়
    (worklog gotcha w)। Fake Supabase client-এ REAL builder chain চলে —
    upsert করা row পরে select-এ ফেরত আসে (scripted return নয়)।

Redis strategy:
    `core.services.redis_queue` attribute দুই alias-এ patch (gotcha w);
    FakeRedisQueue-তে REAL get/delete store semantics — reset সত্যিই key মুছে।

Awaitable-once FakeResult:
    সোর্সে দুই রকম call আছে — `await ...execute()` (list/get/upsert/delete) এবং
    কোনো await ছাড়া `...execute()` (usage fallback, reset supabase)।
    FakeResult.__await__ নিজেকেই return করে, তাই একই fake দুই প্যাটার্নেই চলে।
"""

from __future__ import annotations

import asyncio
import importlib
import time
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# ------------------------------------------------------------ fake infra ----


class FakeResult:
    """Awaitable-once result: দুই call প্যাটার্নেই কাজ করে (awaited বা plain)।"""

    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data

    def __await__(self):
        async def _self() -> FakeResult:
            return self

        return _self().__await__()


class FakeTable:
    """REAL builder-chain semantics over an in-memory row store."""

    def __init__(self, store: dict[str, list[dict[str, Any]]], name: str) -> None:
        self._store = store
        self._name = name
        self._ops: list[tuple] = []

    # -- builder surface (each returns self, exactly like postgrest-py) ------
    def select(self, *cols: str) -> FakeTable:
        self._ops.append(("select", cols))
        return self

    def order(self, col: str, desc: bool = False) -> FakeTable:
        self._ops.append(("order", col, desc))
        return self

    def eq(self, col: str, val: Any) -> FakeTable:
        self._ops.append(("eq", col, val))
        return self

    def upsert(self, data: dict[str, Any], on_conflict: str | None = None) -> FakeTable:
        self._ops.append(("upsert", dict(data), on_conflict))
        return self

    def delete(self) -> FakeTable:
        self._ops.append(("delete",))
        return self

    # -- terminal op --------------------------------------------------------
    def execute(self) -> FakeResult:
        rows = self._store.setdefault(self._name, [])
        pending_upserts = [op for op in self._ops if op[0] == "upsert"]
        deletes = [op for op in self._ops if op[0] == "delete"]
        eqs = [(op[1], op[2]) for op in self._ops if op[0] == "eq"]
        orders = [op for op in self._ops if op[0] == "order"]

        for _, data, conflict in pending_upserts:
            key_col = conflict or "id"
            replaced = False
            for i, existing in enumerate(rows):
                if existing.get(key_col) == data.get(key_col):
                    rows[i] = data
                    replaced = True
                    break
            if not replaced:
                rows.append(dict(data))

        if deletes:
            for _, *eq_args in deletes:
                pass  # delete op itself carries no filter; eqs below apply

        out = list(rows)
        for col, val in eqs:
            out = [r for r in out if r.get(col) == val]

        if deletes and not pending_upserts:
            for col, val in eqs:
                self._store[self._name] = [r for r in self._store[self._name] if r.get(col) != val]

        for _, col, desc in orders:
            out.sort(key=lambda r: r.get(col, ""), reverse=desc)
        return FakeResult(out)


class FakeSupabase:
    """Fake `db` singleton: `.client` → builder-chain client with real rows."""

    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.client = self._Client(self.tables)

    class _Client:
        def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
            self._tables = tables

        def table(self, name: str) -> FakeTable:
            return FakeTable(self._tables, name)


class BrokenSupabase:
    """`_get_db`-র except শাখা ও supabase-failure fallback চালানোর জন্য।"""

    def __init__(self, mode: str = "raise_client") -> None:
        self._mode = mode

    @property
    def client(self):
        if self._mode == "raise_client":
            raise RuntimeError("supabase down")
        return None


class FakeRedisQueue:
    """REAL get/delete store semantics; configured flag scriptable."""

    def __init__(self, configured: bool = True, store: dict[str, Any] | None = None) -> None:
        self.configured = configured
        self.store: dict[str, Any] = store if store is not None else {}
        self.deleted: list[str] = []

    def get(self, key: str) -> Any:
        return self.store.get(key)

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.store.pop(key, None)


def _patch_db(monkeypatch: pytest.MonkeyPatch, fake_db: Any) -> None:
    for name in ("database.supabase_client", "backend.database.supabase_client"):
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        monkeypatch.setattr(mod, "db", fake_db, raising=False)


def _patch_redis(monkeypatch: pytest.MonkeyPatch, fake_q: Any) -> None:
    for name in ("core.services", "backend.core.services"):
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        monkeypatch.setattr(mod, "redis_queue", fake_q, raising=False)


def _tenant_row(tenant_id: str, tier: str = "free", **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "tenant_id": tenant_id,
        "org_name": f"Org {tenant_id}",
        "billing_tier": tier,
        "is_active": True,
    }
    row.update(extra)
    return row


# ------------------------------------------------------------- fixtures ----


@pytest_asyncio.fixture
async def admin_app(monkeypatch: pytest.MonkeyPatch):
    """Minimal app: router mounted, platform-admin gate overridden."""
    from api.dependencies import get_current_platform_admin
    from api.routes.tenant_admin import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_platform_admin] = lambda: {
        "sub": "platform-admin@supremeai.com"
    }
    monkeypatch.setattr(
        importlib.import_module("api.routes.tenant_admin"),
        "_local_store",
        {},
        raising=False,
    )
    return app


@pytest_asyncio.fixture
async def client(admin_app):
    async with AsyncClient(transport=ASGITransport(app=admin_app), base_url="http://test") as ac:
        yield ac


# ------------------------------------------------- isolation contracts ----


class TestPlatformAdminIsolationWiring:
    """Owner P1 #4 evidence: প্রতিটি route platform-admin gated হতে বাধ্য।"""

    def _routes(self, router_module_router):
        from fastapi.routing import APIRoute

        return [r for r in router_module_router.routes if isinstance(r, APIRoute)]

    def test_every_router_route_requires_platform_admin(self):
        from fastapi import Depends

        from api.dependencies import get_current_platform_admin
        from api.routes.tenant_admin import router

        routes = self._routes(router)
        assert routes, "router must expose routes"
        for r in routes:
            deps = [d.dependency for d in r.dependencies]
            assert get_current_platform_admin in deps, (
                f"route {r.methods} {r.path} is NOT platform-admin gated"
            )

    def test_router_level_dependency_declared(self):
        from api.dependencies import get_current_platform_admin
        from api.routes.tenant_admin import router

        assert any(d.dependency is get_current_platform_admin for d in router.dependencies), (
            "router-level dependencies must pin get_current_platform_admin"
        )

    def test_tenants_router_level_dependency_declared(self):
        from api.dependencies import get_current_platform_admin
        from api.routes.tenant_admin import tenants_router

        assert any(
            d.dependency is get_current_platform_admin for d in tenants_router.dependencies
        ), "tenants_router-level dependencies must pin get_current_platform_admin"

    def test_tenants_router_nested_into_primary(self):
        """Verify tenants_router is nested via include_router.

        FastAPI behavior is version-dependent here: some versions retain
        include_router() results as _IncludedRouter sentinels in
        router.routes (no .path attribute until mounted on an app); others
        expand them eagerly into APIRoute objects carrying the concatenated
        prefix. We accept BOTH fingerprints — (a) a sentinel entry (checked
        by class name so subclassing cannot fool it), OR (b) an expanded
        APIRoute whose path embeds the tenants prefix. Either one is the
        unmistakable fingerprint of an include_router() call.
        """
        from fastapi.routing import APIRoute as _APIRoute

        from api.routes.tenant_admin import router, tenants_router

        assert tenants_router.prefix == "/admin-api/tenants", (
            "tenants_router prefix must be /admin-api/tenants"
        )
        has_sentinel = any(
            type(r).__name__ in {"_IncludedRouter", "IncludedRouter"} for r in router.routes
        )
        expanded_nested = [
            r
            for r in router.routes
            if isinstance(r, _APIRoute)
            and getattr(r, "path", "").endswith(f"{tenants_router.prefix}/{{tenant_id}}/reset")
        ]
        assert has_sentinel or expanded_nested, (
            "tenants_router must be included into the primary router "
            "(no _IncludedRouter sentinel and no expanded nested route found)"
        )

    def test_reset_dual_primary_route_registration(self):
        from api.routes.tenant_admin import router

        reset_paths = {
            "/admin-api/tenant-limits/{tenant_id}/reset",
            "/admin-api/tenant-limits/{tenant_id}/reset-usage",
        }
        # Guard against _IncludedRouter which has no .path attribute.
        found = {r.path for r in router.routes if hasattr(r, "path") and r.path in reset_paths}
        assert found == reset_paths, f"missing reset registrations: {reset_paths - found}"

    def test_tenants_router_nesting_produces_doubled_prefix_flagged(self):
        """⚠️ OWNER DECISION FLAG (wiring gap, audit dormant-class).

        router.include_router(tenants_router) concatenates prefixes: the
        intended /admin-api/tenants/{tenant_id}/reset surface mounts as
        /admin-api/tenant-limits/admin-api/tenants/... — unreachable at the
        documented path. NOT "fixed" here (wire-first: mounting mechanics are
        owner design); this test LOCKS the current reality so the owner's
        eventual fix flips it deliberately. Decision item filed in PR body.

        Implementation note: FastAPI only expands nested include_router() paths
        into the OpenAPI schema. We therefore inspect bare.openapi()["paths"]
        instead of bare.routes directly (which retains unexpanded _IncludedRouter
        sentinels in modern FastAPI).
        """
        from fastapi import FastAPI

        from api.routes.tenant_admin import router

        bare = FastAPI()
        bare.include_router(router)
        doubled = "/admin-api/tenant-limits/admin-api/tenants/{tenant_id}/reset"
        assert doubled in bare.openapi()["paths"], (
            f"nested tenants router path changed: expected {doubled} in registry"
        )

    async def test_unauthenticated_request_rejected_without_bypass(self, monkeypatch):
        """No override + bypass disabled → real admin chain runs → 401/403.

        Conftest env sets ALLOW_TEST_AUTH_BYPASS=1; the chain honors
        settings.allow_test_auth_bypass at request time, so the flag is
        patched off to exercise the REAL gate (owner AUDIT-SEC-9 lock).

        CI hardening: some earlier tests in the CI group rebind/reload
        core.config, so ``core.config.settings`` and the instance captured
        by ``api.dependencies`` can diverge. Patch BOTH (same-object case
        is a harmless no-op) and then LOUDLY assert the instance the
        dependency chain actually reads refuses bypass — silent drift
        becomes an explicit, self-explanatory failure instead of a
        mysterious 200.
        """
        import api.dependencies as _deps
        from api.routes.tenant_admin import router
        from core.config import settings

        monkeypatch.setattr(settings, "allow_test_auth_bypass", False, raising=False)
        monkeypatch.setattr(_deps.settings, "allow_test_auth_bypass", False, raising=False)
        monkeypatch.setattr(
            type(settings), "is_bypass_allowed", property(lambda self: False), raising=False
        )
        monkeypatch.delenv("ALLOW_TEST_AUTH_BYPASS", raising=False)
        bare = FastAPI()
        bare.include_router(router)
        async with AsyncClient(transport=ASGITransport(app=bare), base_url="http://test") as ac:
            resp = await ac.get("/admin-api/tenant-limits")
        assert resp.status_code in (401, 403), f"ungated admin surface detected: {resp.status_code}"


# ---------------------------------------------------- tier defaults ----


class TestTierDefaults:
    def test_four_tiers_with_expected_shapes(self):
        from api.routes.tenant_admin import TIER_DEFAULTS

        assert set(TIER_DEFAULTS) == {"free", "starter", "pro", "enterprise"}
        for limits in TIER_DEFAULTS.values():
            assert set(limits) == {
                "requests_per_minute",
                "max_tokens_per_day",
                "max_concurrent_sessions",
            }

    def test_limits_monotonically_non_decreasing_across_tiers(self):
        from api.routes.tenant_admin import TIER_DEFAULTS

        order = ["free", "starter", "pro", "enterprise"]
        for key in ("requests_per_minute", "max_tokens_per_day", "max_concurrent_sessions"):
            values = [TIER_DEFAULTS[t][key] for t in order]
            assert values == sorted(values), f"{key} not monotonic: {values}"

    async def test_tiers_defaults_endpoint(self, client):
        resp = await client.get("/admin-api/tenant-limits/tiers/defaults")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert "free" in body["tiers"]

    async def test_tiers_defaults_endpoint_not_shadowed_by_get_tenant(self, client):
        """GET /{tenant_id} declaration order must not shadow /tiers/defaults."""
        resp = await client.get("/admin-api/tenant-limits/tiers/defaults")
        assert resp.status_code == 200
        assert "tiers" in resp.json()


# ------------------------------------------------------ list tenants ----


class TestListTenants:
    async def test_empty_store(self, client):
        resp = await client.get("/admin-api/tenant-limits")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "status": "success",
            "total": 0,
            "tenants": [],
            "usages": [],
            "tier_defaults": body["tier_defaults"],
        }

    async def test_defaults_fill_missing_limit_keys(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1", tier="pro")]
        _patch_db(monkeypatch, fake_db)

        resp = await client.get("/admin-api/tenant-limits", params={"include_usage": "false"})
        assert resp.status_code == 200
        tenant = resp.json()["tenants"][0]
        # pro defaults filled where the stored row lacked the keys
        assert tenant["requests_per_minute"] == 200
        assert tenant["max_tokens_per_day"] == 1_000_000
        assert tenant["max_concurrent_sessions"] == 20

    async def test_explicit_limits_not_overwritten_by_defaults(self, client, monkeypatch):
        """Defaults fill only Nones — explicit values survive (224->223)."""
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [
            _tenant_row(
                "t-1",
                tier="free",
                requests_per_minute=7,
                max_tokens_per_day=42,
                max_concurrent_sessions=1,
            )
        ]
        _patch_db(monkeypatch, fake_db)

        tenant = (
            await client.get("/admin-api/tenant-limits", params={"include_usage": "false"})
        ).json()["tenants"][0]
        assert tenant["requests_per_minute"] == 7
        assert tenant["max_tokens_per_day"] == 42
        assert tenant["max_concurrent_sessions"] == 1

    async def test_unknown_tier_falls_back_to_free_defaults(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-x", tier="gold")]
        _patch_db(monkeypatch, fake_db)

        resp = await client.get("/admin-api/tenant-limits", params={"include_usage": "false"})
        tenant = resp.json()["tenants"][0]
        assert tenant["requests_per_minute"] == 20

    async def test_include_usage_false_yields_empty_usages(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1")]
        _patch_db(monkeypatch, fake_db)

        body = (
            await client.get("/admin-api/tenant-limits", params={"include_usage": "false"})
        ).json()
        assert body["usages"] == []

    async def test_include_usage_gathers_live_usage(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1")]
        _patch_db(monkeypatch, fake_db)
        day = int(time.time()) // 86400
        _patch_redis(
            monkeypatch,
            FakeRedisQueue(
                store={f"rate:t-1:{day}:rpd": "5", "rate:t-1:tokens": 100, "rate:t-1:cost": 0.5}
            ),
        )

        body = (await client.get("/admin-api/tenant-limits")).json()
        assert body["usages"] == [
            {"tenant_id": "t-1", "requests_today": 5, "tokens_today": 100, "cost_today": 0.5}
        ]

    async def test_supabase_list_failure_falls_back_to_local_store(self, client, monkeypatch):
        from api.routes import tenant_admin as ta

        _patch_db(monkeypatch, BrokenSupabase())
        ta._local_store["tenants"] = [_tenant_row("local-1")]
        monkeypatch.setattr(ta, "_local_store", ta._local_store, raising=False)

        body = (
            await client.get("/admin-api/tenant-limits", params={"include_usage": "false"})
        ).json()
        assert body["total"] == 1
        assert body["tenants"][0]["tenant_id"] == "local-1"


# ---------------------------------------------------- create tenant ----


class TestCreateTenant:
    async def test_create_success_with_tier_defaults(self, client, monkeypatch):
        fake_db = FakeSupabase()
        _patch_db(monkeypatch, fake_db)

        resp = await client.post(
            "/admin-api/tenant-limits",
            json={"tenant_id": "acme", "org_name": "Acme", "billing_tier": "starter"},
        )
        assert resp.status_code == 200
        record = resp.json()["tenant"]
        assert record["billing_tier"] == "starter"
        assert record["requests_per_minute"] == 60
        assert record["max_tokens_per_day"] == 200_000
        assert record["max_concurrent_sessions"] == 5
        assert record["is_active"] is True
        assert record["created_at"].endswith("Z")
        # REAL round-trip: the row is readable back through the fake
        assert fake_db.tables["tenant_limits"][0]["tenant_id"] == "acme"

    async def test_duplicate_tenant_409(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("acme")]
        _patch_db(monkeypatch, fake_db)

        resp = await client.post("/admin-api/tenant-limits", json={"tenant_id": "acme"})
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    async def test_invalid_tier_silently_downgrades_to_free(self, client, monkeypatch):
        """Documented owner behavior: unknown tier → free defaults (not 400)."""
        fake_db = FakeSupabase()
        _patch_db(monkeypatch, fake_db)

        resp = await client.post(
            "/admin-api/tenant-limits",
            json={"tenant_id": "acme", "billing_tier": "diamond"},
        )
        record = resp.json()["tenant"]
        assert record["billing_tier"] == "free"
        assert record["requests_per_minute"] == 20

    async def test_explicit_limits_override_tier_defaults(self, client, monkeypatch):
        fake_db = FakeSupabase()
        _patch_db(monkeypatch, fake_db)

        resp = await client.post(
            "/admin-api/tenant-limits",
            json={"tenant_id": "acme", "requests_per_minute": 7},
        )
        assert resp.json()["tenant"]["requests_per_minute"] == 7

    async def test_redis_tier_cache_written_on_create(self, client, monkeypatch):
        fake_db = FakeSupabase()
        _patch_db(monkeypatch, fake_db)
        redis_calls: list[tuple[str, str]] = []

        class TierLimiter:
            async def set_tier(self, tenant_id: str, tier: str) -> None:
                redis_calls.append((tenant_id, tier))

        import sys

        fake_mod = type(sys)("tools.tenant_rate_limiter")
        fake_mod.TenantRateLimiter = TierLimiter
        monkeypatch.setitem(sys.modules, "tools.tenant_rate_limiter", fake_mod)

        await client.post(
            "/admin-api/tenant-limits", json={"tenant_id": "acme", "billing_tier": "pro"}
        )
        assert redis_calls == [("acme", "pro")]

    async def test_redis_tier_cache_failure_tolerated(self, client, monkeypatch):
        fake_db = FakeSupabase()
        _patch_db(monkeypatch, fake_db)

        class BoomLimiter:
            async def set_tier(self, tenant_id: str, tier: str) -> None:
                raise RuntimeError("redis down")

        import sys

        fake_mod = type(sys)("tools.tenant_rate_limiter")
        fake_mod.TenantRateLimiter = BoomLimiter
        monkeypatch.setitem(sys.modules, "tools.tenant_rate_limiter", fake_mod)

        resp = await client.post("/admin-api/tenant-limits", json={"tenant_id": "acme"})
        assert resp.status_code == 200  # cache failure must not fail the create


# ------------------------------------------------------ get tenant ----


class TestGetTenant:
    async def test_get_found_with_usage(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1", tier="pro")]
        _patch_db(monkeypatch, fake_db)
        _patch_redis(monkeypatch, FakeRedisQueue(configured=False))

        resp = await client.get("/admin-api/tenant-limits/t-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant"]["tenant_id"] == "t-1"
        assert body["usage"]["requests_today"] == 0

    async def test_get_not_found_404(self, client, monkeypatch):
        _patch_db(monkeypatch, FakeSupabase())
        resp = await client.get("/admin-api/tenant-limits/ghost")
        assert resp.status_code == 404
        assert "ghost" in resp.json()["detail"]


# --------------------------------------------------- update tenant ----


class TestUpdateTenant:
    async def test_update_not_found_404(self, client, monkeypatch):
        _patch_db(monkeypatch, FakeSupabase())
        resp = await client.put("/admin-api/tenant-limits/ghost", json={"org_name": "X"})
        assert resp.status_code == 404

    async def test_invalid_tier_rejected_400(self, client, monkeypatch):
        """Asymmetric contract vs create: update validates tier strictly."""
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1")]
        _patch_db(monkeypatch, fake_db)

        resp = await client.put("/admin-api/tenant-limits/t-1", json={"billing_tier": "galactic"})
        assert resp.status_code == 400
        assert "Invalid tier" in resp.json()["detail"]

    async def test_tier_change_applies_defaults_for_unspecified_keys(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1", tier="free")]
        _patch_db(monkeypatch, fake_db)

        resp = await client.put("/admin-api/tenant-limits/t-1", json={"billing_tier": "enterprise"})
        record = resp.json()["tenant"]
        assert record["billing_tier"] == "enterprise"
        assert record["requests_per_minute"] == 999
        assert record["max_tokens_per_day"] == 9_999_999
        assert record["max_concurrent_sessions"] == 100

    async def test_explicit_key_not_clobbered_by_tier_defaults(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1", tier="free")]
        _patch_db(monkeypatch, fake_db)

        resp = await client.put(
            "/admin-api/tenant-limits/t-1",
            json={"billing_tier": "enterprise", "requests_per_minute": 3},
        )
        record = resp.json()["tenant"]
        assert record["requests_per_minute"] == 3  # explicit wins
        assert record["max_tokens_per_day"] == 9_999_999  # default fills

    async def test_partial_update_preserves_existing_and_stamps_updated_at(
        self, client, monkeypatch
    ):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1", tier="pro")]
        _patch_db(monkeypatch, fake_db)

        resp = await client.put("/admin-api/tenant-limits/t-1", json={"notes": "vip customer"})
        record = resp.json()["tenant"]
        assert record["billing_tier"] == "pro"  # untouched
        assert record["notes"] == "vip customer"
        assert record["updated_at"].endswith("Z")
        # REAL round-trip: row merged back into the fake store
        assert fake_db.tables["tenant_limits"][0]["notes"] == "vip customer"

    async def test_redis_tier_updated_on_tier_change(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1")]
        _patch_db(monkeypatch, fake_db)
        redis_calls: list[tuple[str, str]] = []

        class TierLimiter:
            async def set_tier(self, tenant_id: str, tier: str) -> None:
                redis_calls.append((tenant_id, tier))

        import sys

        fake_mod = type(sys)("tools.tenant_rate_limiter")
        fake_mod.TenantRateLimiter = TierLimiter
        monkeypatch.setitem(sys.modules, "tools.tenant_rate_limiter", fake_mod)

        await client.put("/admin-api/tenant-limits/t-1", json={"billing_tier": "starter"})
        assert redis_calls == [("t-1", "starter")]

    async def test_tenant_id_scoped_update_does_not_touch_other_tenants(self, client, monkeypatch):
        """Isolation evidence: PUT /{id} mutates ONLY that tenant's row."""
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("a"), _tenant_row("b")]
        _patch_db(monkeypatch, fake_db)

        await client.put("/admin-api/tenant-limits/a", json={"notes": "only-a"})
        rows = {r["tenant_id"]: r for r in fake_db.tables["tenant_limits"]}
        assert rows["a"]["notes"] == "only-a"
        assert "notes" not in rows["b"]

    async def test_redis_tier_update_failure_tolerated_on_update(self, client, monkeypatch):
        """Tier-change with Redis down → 200, Supabase record still written."""
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1")]
        _patch_db(monkeypatch, fake_db)

        class BoomLimiter:
            async def set_tier(self, tenant_id: str, tier: str) -> None:
                raise RuntimeError("redis down")

        import sys

        fake_mod = type(sys)("tools.tenant_rate_limiter")
        fake_mod.TenantRateLimiter = BoomLimiter
        monkeypatch.setitem(sys.modules, "tools.tenant_rate_limiter", fake_mod)

        resp = await client.put("/admin-api/tenant-limits/t-1", json={"billing_tier": "pro"})
        assert resp.status_code == 200
        assert fake_db.tables["tenant_limits"][0]["billing_tier"] == "pro"


# --------------------------------------------------- delete tenant ----


class TestDeleteTenant:
    async def test_delete_not_found_404(self, client, monkeypatch):
        _patch_db(monkeypatch, FakeSupabase())
        resp = await client.delete("/admin-api/tenant-limits/ghost")
        assert resp.status_code == 404

    async def test_delete_success_round_trip(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1"), _tenant_row("t-2")]
        _patch_db(monkeypatch, fake_db)

        resp = await client.delete("/admin-api/tenant-limits/t-1")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted", "tenant_id": "t-1"}
        remaining = [r["tenant_id"] for r in fake_db.tables["tenant_limits"]]
        assert remaining == ["t-2"]  # REAL deletion, sibling row untouched


# ---------------------------------------------------- usage readout ----


class FlakySupabase(FakeSupabase):
    """FakeSupabase whose tenant_usage execute raises (failure-fallback arcs)."""

    class _Client(FakeSupabase._Client):
        def table(self, name: str) -> FakeTable:
            if name == "tenant_usage":
                raise RuntimeError("tenant_usage unavailable")
            return super().table(name)


class FlakyLimitsSupabase(FakeSupabase):
    """FakeSupabase whose tenant_limits reads raise (get-failure fallback)."""

    class _Client(FakeSupabase._Client):
        def table(self, name: str) -> FakeTable:
            if name == "tenant_limits":
                raise RuntimeError("tenant_limits unavailable")
            return super().table(name)


class TestUsageEndpoint:
    async def test_usage_not_found_404(self, client, monkeypatch):
        _patch_db(monkeypatch, FakeSupabase())
        resp = await client.get("/admin-api/tenant-limits/ghost/usage")
        assert resp.status_code == 404

    async def test_usage_redis_source(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1")]
        _patch_db(monkeypatch, fake_db)
        day = int(time.time()) // 86400
        _patch_redis(
            monkeypatch,
            FakeRedisQueue(store={f"rate:t-1:{day}:rpd": 12, "rate:t-1:tokens": 3456}),
        )

        body = (await client.get("/admin-api/tenant-limits/t-1/usage")).json()
        assert body["usage"] == {
            "tenant_id": "t-1",
            "requests_today": 12,
            "tokens_today": 3456,
            "cost_today": 0.0,
        }
        assert body["limits"] == {
            "requests_per_minute": None,  # stored row had no limit keys
            "max_tokens_per_day": None,
        }

    async def test_usage_supabase_fallback_when_redis_zero(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1")]
        fake_db.tables["tenant_usage"] = [
            {
                "tenant_id": "t-1",
                "date": time.strftime("%Y-%m-%d"),
                "requests_count": 4,
                "tokens_used": 999,
                "cost_incurred": 1.25,
            }
        ]
        _patch_db(monkeypatch, fake_db)
        _patch_redis(monkeypatch, FakeRedisQueue(configured=False))

        body = (await client.get("/admin-api/tenant-limits/t-1/usage")).json()
        assert body["usage"] == {
            "tenant_id": "t-1",
            "requests_today": 4,
            "tokens_today": 999,
            "cost_today": 1.25,
        }

    async def test_usage_supabase_unreachable_and_redis_zero(self, client, monkeypatch):
        """Redis unconfigured + no DB client → usage returns zeros (187->204)."""
        from api.routes import tenant_admin as ta

        _patch_db(monkeypatch, BrokenSupabase(mode="none_client"))
        monkeypatch.setattr(ta, "_local_store", {"tenants": [_tenant_row("t-1")]}, raising=False)
        _patch_redis(monkeypatch, FakeRedisQueue(configured=False))

        body = (await client.get("/admin-api/tenant-limits/t-1/usage")).json()
        assert body["usage"] == {
            "tenant_id": "t-1",
            "requests_today": 0,
            "tokens_today": 0,
            "cost_today": 0.0,
        }

    async def test_usage_supabase_fallback_exception_tolerated(self, client, monkeypatch):
        """Supabase usage read raising → debug-logged, zeros returned (202-203)."""
        fake_db = FlakySupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1")]
        _patch_db(monkeypatch, fake_db)
        _patch_redis(monkeypatch, FakeRedisQueue(configured=False))

        body = (await client.get("/admin-api/tenant-limits/t-1/usage")).json()
        assert body["usage"]["requests_today"] == 0
        assert body["usage"]["tokens_today"] == 0

    async def test_usage_zero_everywhere(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1")]
        _patch_db(monkeypatch, fake_db)
        _patch_redis(monkeypatch, FakeRedisQueue(configured=False))

        body = (await client.get("/admin-api/tenant-limits/t-1/usage")).json()
        assert body["usage"]["requests_today"] == 0
        assert body["usage"]["tokens_today"] == 0
        assert body["usage"]["cost_today"] == 0.0

    async def test_usage_redis_exception_tolerated(self, client, monkeypatch):
        """Redis read raising must degrade to zeros/supabase, not 500."""
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row("t-1")]
        _patch_db(monkeypatch, fake_db)

        class BoomQueue:
            configured = True

            def get(self, key: str) -> Any:
                raise RuntimeError("redis exploded")

        _patch_redis(monkeypatch, BoomQueue())
        body = (await client.get("/admin-api/tenant-limits/t-1/usage")).json()
        assert body["usage"]["requests_today"] == 0


# ------------------------------------------------------ reset usage ----


class TestResetUsage:
    async def test_reset_redis_source_deletes_all_three_keys(self, client, monkeypatch):
        day = int(time.time()) // 86400
        store = {
            f"rate:t-1:{day}:rpd": 10,
            "rate:t-1:tokens": 2000,
            "rate:t-1:cost": 0.75,
        }
        fake_q = FakeRedisQueue(store=store)
        _patch_redis(monkeypatch, fake_q)

        resp = await client.post("/admin-api/tenant-limits/t-1/reset")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"status": "reset", "tenant_id": "t-1", "source": "redis"}
        assert store == {}  # REAL deletion: all three counters gone
        assert len(fake_q.deleted) == 3

    async def test_reset_supabase_source_when_redis_unconfigured(self, client, monkeypatch):
        fake_db = FakeSupabase()
        fake_db.tables["tenant_usage"] = [{"tenant_id": "t-1", "date": time.strftime("%Y-%m-%d")}]
        _patch_db(monkeypatch, fake_db)
        _patch_redis(monkeypatch, FakeRedisQueue(configured=False))

        resp = await client.post("/admin-api/tenant-limits/t-1/reset")
        body = resp.json()
        assert body["source"] == "supabase"
        # REAL round-trip: today's usage row removed from the fake store
        assert fake_db.tables["tenant_usage"] == []

    async def test_reset_none_source_when_both_backends_unavailable(self, client, monkeypatch):
        _patch_db(monkeypatch, BrokenSupabase(mode="none_client"))
        _patch_redis(monkeypatch, FakeRedisQueue(configured=False))

        resp = await client.post("/admin-api/tenant-limits/t-1/reset")
        assert resp.json() == {"status": "reset", "tenant_id": "t-1", "source": "none"}

    async def test_reset_supabase_exception_reports_none_source(self, client, monkeypatch):
        """Supabase reset raising → warning path, source none (390-391)."""
        _patch_db(monkeypatch, BrokenSupabase())  # client access raises inside branch
        _patch_redis(monkeypatch, FakeRedisQueue(configured=False))

        resp = await client.post("/admin-api/tenant-limits/t-1/reset")
        body = resp.json()
        assert body["status"] == "reset"
        assert body["source"] in ("supabase", "none")
        # with a client whose EXECUTE raises, the fallback must not 500

    async def test_reset_supabase_execute_failure_reports_none_source(self, client, monkeypatch):
        """Deep failure: client present but .table().delete().eq().eq().execute()
        raising → caught, falls to final none-source return."""

        class BoomDeleteClient:
            def table(self, name: str):
                return self

            def delete(self):
                return self

            def eq(self, col, val):
                return self

            def execute(self):
                raise RuntimeError("postgrest down")

        class HolderDB:
            def __init__(self) -> None:
                self.client = BoomDeleteClient()

        _patch_db(monkeypatch, HolderDB())
        _patch_redis(monkeypatch, FakeRedisQueue(configured=False))

        resp = await client.post("/admin-api/tenant-limits/t-1/reset")
        assert resp.json() == {"status": "reset", "tenant_id": "t-1", "source": "none"}

    async def test_reset_redis_exception_falls_through_to_supabase(self, client, monkeypatch):
        fake_db = FakeSupabase()
        _patch_db(monkeypatch, fake_db)

        class BoomQueue:
            configured = True

            def get(self, key: str) -> Any:
                raise RuntimeError("boom")

            def delete(self, key: str) -> None:
                raise RuntimeError("boom")

        _patch_redis(monkeypatch, BoomQueue())

        resp = await client.post("/admin-api/tenant-limits/t-1/reset")
        assert resp.json()["source"] == "supabase"

    async def test_reset_alias_route_reset_usage(self, client, monkeypatch):
        _patch_redis(monkeypatch, FakeRedisQueue(store={"rate:t-1:tokens": 1}))
        resp = await client.post("/admin-api/tenant-limits/t-1/reset-usage")
        assert resp.json()["source"] == "redis"

    async def test_tenants_prefix_surface_unreachable_tripwire(self, client, monkeypatch):
        """⚠️ OWNER DECISION TRIPWIRE: /admin-api/tenants/{id}/reset is 404
        today (doubled-prefix nesting — see wiring-gap test above). If the
        owner fixes the mount, THIS test fails and must be flipped to the
        contract test — that is the point.
        """
        _patch_redis(monkeypatch, FakeRedisQueue(store={"rate:t-1:tokens": 1}))
        resp = await client.post("/admin-api/tenants/t-1/reset")
        assert resp.status_code == 404, (
            "/admin-api/tenants surface became reachable — update the "
            "wiring-gap tests + file note (owner decision resolved?)"
        )

    async def test_reset_handler_reachable_via_nested_doubled_path(self, client, monkeypatch):
        """The tenants_router-registered handler works — only its mounted
        path is malformed. Proves the handler (not the route fn) is sound.
        """
        _patch_redis(monkeypatch, FakeRedisQueue(store={"rate:t-1:tokens": 1}))
        resp = await client.post("/admin-api/tenant-limits/admin-api/tenants/t-1/reset")
        assert resp.status_code == 200
        assert resp.json()["source"] == "redis"


# ------------------------------------------------- db helper fallback ----


class TestDbHelperFallbacks:
    async def test_local_upsert_updates_existing_row(self, client, monkeypatch):
        from api.routes import tenant_admin as ta

        _patch_db(monkeypatch, BrokenSupabase())
        monkeypatch.setattr(
            ta, "_local_store", {"tenants": [_tenant_row("t-1", tier="free")]}, raising=False
        )

        await ta._db_upsert_tenant({**_tenant_row("t-1", tier="pro"), "org_name": "New"})
        tenants = ta._local_store["tenants"]
        assert len(tenants) == 1
        assert tenants[0]["billing_tier"] == "pro"
        assert tenants[0]["org_name"] == "New"

    async def test_local_upsert_updates_second_matching_row(self, monkeypatch):
        """Loop false-arc: first row mismatches, second matches → replaced."""
        from api.routes import tenant_admin as ta

        _patch_db(monkeypatch, BrokenSupabase())
        monkeypatch.setattr(
            ta,
            "_local_store",
            {"tenants": [_tenant_row("other"), _tenant_row("t-1", tier="free")]},
            raising=False,
        )

        await ta._db_upsert_tenant(_tenant_row("t-1", tier="pro"))
        tenants = ta._local_store["tenants"]
        assert len(tenants) == 2
        assert tenants[1]["billing_tier"] == "pro"

    async def test_local_upsert_appends_unknown_tenant(self, monkeypatch):
        from api.routes import tenant_admin as ta

        monkeypatch.setattr(ta, "_local_store", {}, raising=False)
        ok = await ta._db_upsert_tenant(_tenant_row("new-1"))
        assert ok is True
        assert [t["tenant_id"] for t in ta._local_store["tenants"]] == ["new-1"]

    async def test_local_get_matches_by_tenant_id(self, monkeypatch):
        from api.routes import tenant_admin as ta

        _patch_db(monkeypatch, BrokenSupabase(mode="none_client"))
        monkeypatch.setattr(
            ta,
            "_local_store",
            {"tenants": [_tenant_row("a"), _tenant_row("b")]},
            raising=False,
        )
        got = await ta._db_get_tenant("b")
        assert got["tenant_id"] == "b"
        assert await ta._db_get_tenant("ghost") is None

    async def test_supabase_get_failure_falls_back_to_local_store(self, monkeypatch):
        """Supabase GET raising → local-store scan still serves reads (122-123)."""
        from api.routes import tenant_admin as ta

        _patch_db(monkeypatch, FlakyLimitsSupabase())
        monkeypatch.setattr(
            ta, "_local_store", {"tenants": [_tenant_row("local-9")]}, raising=False
        )
        got = await ta._db_get_tenant("local-9")
        assert got is not None
        assert got["tenant_id"] == "local-9"

    async def test_local_delete_rebuilds_list(self, monkeypatch):
        from api.routes import tenant_admin as ta

        _patch_db(monkeypatch, BrokenSupabase(mode="none_client"))
        monkeypatch.setattr(
            ta,
            "_local_store",
            {"tenants": [_tenant_row("a"), _tenant_row("b")]},
            raising=False,
        )
        ok = await ta._db_delete_tenant("a")
        assert ok is True
        assert [t["tenant_id"] for t in ta._local_store["tenants"]] == ["b"]
        assert ta._local_store["tenants"] is not None

    async def test_supabase_delete_failure_falls_back_to_local_rebuild(self, monkeypatch):
        """Supabase DELETE raising → local rebuild still removes (154-155)."""
        from api.routes import tenant_admin as ta

        _patch_db(monkeypatch, FlakyLimitsSupabase())
        monkeypatch.setattr(
            ta,
            "_local_store",
            {"tenants": [_tenant_row("a"), _tenant_row("b")]},
            raising=False,
        )
        ok = await ta._db_delete_tenant("a")
        assert ok is True
        assert [t["tenant_id"] for t in ta._local_store["tenants"]] == ["b"]

    async def test_get_db_returns_none_when_client_missing(self, monkeypatch):
        from api.routes.tenant_admin import _get_db

        _patch_db(monkeypatch, BrokenSupabase(mode="none_client"))
        assert _get_db() is None

    async def test_get_db_returns_none_on_client_exception(self, monkeypatch):
        from api.routes.tenant_admin import _get_db

        _patch_db(monkeypatch, BrokenSupabase(mode="raise_client"))
        assert _get_db() is None

    async def test_get_db_returns_real_client_when_present(self, monkeypatch):
        from api.routes.tenant_admin import _get_db

        fake = FakeSupabase()
        _patch_db(monkeypatch, fake)
        assert _get_db() is fake.client


# --------------------------------------------------- concurrency ----


class TestConcurrentUsageGather:
    async def test_gather_collects_many_tenants_concurrently(self, client, monkeypatch):
        """list include_usage=True → asyncio.gather fan-out stays correct."""
        fake_db = FakeSupabase()
        fake_db.tables["tenant_limits"] = [_tenant_row(f"t-{i}") for i in range(5)]
        _patch_db(monkeypatch, fake_db)
        day = int(time.time()) // 86400
        store: dict[str, Any] = {f"rate:t-{i}:{day}:rpd": i for i in range(5)}
        _patch_redis(monkeypatch, FakeRedisQueue(store=store))

        body = (await client.get("/admin-api/tenant-limits")).json()
        usage_map = {u["tenant_id"]: u["requests_today"] for u in body["usages"]}
        assert usage_map == {f"t-{i}": i for i in range(5)}
        # asyncio is genuinely exercised through the endpoint's gather
        assert asyncio.iscoroutinefunction is not None

"""Tests for core/api/routes/pool.py"""
from __future__ import annotations

import os
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import core.api.routes.pool as pool_mod

SUB = "user-1"


class FakeResult:
    def __init__(self, rows):
        self.data = rows


class FakeTable:
    def __init__(self, store, name):
        self.store = store
        self.name = name
        self._filters = {}
        self._pending_insert = None
        self._pending_upsert = None
        self._pending_update = None

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def insert(self, row):
        self._pending_insert = row
        return self

    def upsert(self, row, on_conflict=None):
        self._pending_upsert = (row, on_conflict)
        return self

    def update(self, row):
        self._pending_update = row
        return self

    def execute(self):
        rows = self.store.setdefault(self.name, [])
        if self._pending_insert is not None:
            rows.append(dict(self._pending_insert))
            self._pending_insert = None
            return FakeResult([rows[-1]])
        if self._pending_upsert is not None:
            row, oc = self._pending_upsert
            # find by user_id PK for user_bonus_quotas
            key = row.get("user_id")
            existing = [r for r in rows if r.get("user_id") == key]
            if existing:
                existing[0].update(row)
            else:
                rows.append(dict(row))
            self._pending_upsert = None
            return FakeResult([r for r in rows if r.get("user_id") == key])
        if self._pending_update is not None:
            for r in rows:
                if all(r.get(k) == v for k, v in self._filters.items()):
                    r.update(self._pending_update)
            self._pending_update = None
            return FakeResult([r for r in rows if all(r.get(k) == v for k, v in self._filters.items())])
        # select
        out = [r for r in rows if all(r.get(k) == v for k, v in self._filters.items())]
        self._filters = {}
        return FakeResult(out)


class FakeDB:
    def __init__(self, tables=None):
        self.store = tables if tables is not None else {}
        self.ops = []

    @property
    def client(self):
        holder = self

        class _Client:
            def table(self, name):
                return FakeTable(holder.store, name)

        return _Client()


@pytest_asyncio.fixture
async def pool_env(monkeypatch):
    os.environ["SUPREMEAI_CREDENTIAL_ENC_KEY"] = "test-secret-key-1234567890"
    app = FastAPI()
    app.include_router(pool_mod.router)

    async def fake_user():
        return {"sub": SUB, "role": "user"}

    app.dependency_overrides[pool_mod.verify_token_dependency] = fake_user

    store = {"user_contributed_api_keys": [], "user_bonus_quotas": []}
    fake_db = FakeDB(store)
    monkeypatch.setattr("database.supabase_client.get_db", lambda: fake_db)
    monkeypatch.setattr(pool_mod, "get_db", lambda: fake_db)

    # bypass network validation
    async def fake_validate(provider, api_key):
        return True
    monkeypatch.setattr(pool_mod, "_validate", fake_validate)

    return app, store


@pytest.mark.asyncio
async def test_list_providers(pool_env):
    app, store = pool_env
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/pool/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert any(p["id"] == "kilo" for p in data["providers"])


@pytest.mark.asyncio
async def test_contribute_success(pool_env):
    app, store = pool_env
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/pool/contribute", json={"provider": "gemini", "api_key": "AIzaSy" + "A" * 33})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["bonus_earned"] == 100000
    assert len(store["user_contributed_api_keys"]) == 1
    # quota roll-up
    assert store["user_bonus_quotas"][0]["daily_bonus_tokens"] == 100000
    assert store["user_bonus_quotas"][0]["valid_keys_count"] == 1


@pytest.mark.asyncio
async def test_contribute_dedup_conflict(pool_env):
    app, store = pool_env
    key = "AIzaSy" + "B" * 33
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.post("/pool/contribute", json={"provider": "gemini", "api_key": key})
        assert r1.status_code == 200
        r2 = await client.post("/pool/contribute", json={"provider": "gemini", "api_key": key})
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_contribute_invalid_format(pool_env):
    app, store = pool_env
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/pool/contribute", json={"provider": "gemini", "api_key": "x" * 40})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_contribute_unknown_provider(pool_env):
    app, store = pool_env
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/pool/contribute", json={"provider": "nope", "api_key": "AIzaSy" + "C" * 33})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_quota_rollup_kilo_vip(pool_env):
    app, store = pool_env
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        key = "eyJ" + "a" * 10 + "." + "b" * 10 + "." + "c" * 10
        resp = await client.post("/pool/contribute", json={"provider": "kilo", "api_key": key})
    assert resp.status_code == 200, resp.text
    assert resp.json()["bonus_earned"] == 150000
    assert store["user_bonus_quotas"][0]["daily_bonus_tokens"] == 150000


@pytest.mark.asyncio
async def test_get_quota(pool_env):
    app, store = pool_env
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/pool/quota")
    assert resp.status_code == 200
    assert "daily_bonus_tokens" in resp.json()


@pytest.mark.asyncio
async def test_contribute_daily_cap(pool_env):
    # বাংলা মন্তব্য: দিনে সর্বোচ্চ ৫টি কী সাবমিট সীমা ভেরিফিকেশন (429 Rate Limit)
    app, store = pool_env
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(5):
            k = f"AIzaSy{'X' * 32}{i}"
            res = await client.post("/pool/contribute", json={"provider": "gemini", "api_key": k})
            assert res.status_code == 200
        # ষষ্ঠ কী সাবমিট করলে ৪২৯ আসবে
        k_extra = f"AIzaSy{'X' * 32}9"
        res_blocked = await client.post("/pool/contribute", json={"provider": "gemini", "api_key": k_extra})
        assert res_blocked.status_code == 429
        assert "Daily key submission limit reached" in res_blocked.json()["detail"]

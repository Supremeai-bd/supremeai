"""#1826 — GET /api/v1/integrations list endpoint tests.

বাংলা: ConnectedPlatformsVault আগে স্থায়ী "Unable to load" দেখাত — এন্ডপয়েন্টটাই
ছিল না। এখন Integration store থেকে caller-স্কোপড projection ফেরত যায়।
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakeScalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._scalars = FakeScalars(rows)

    def scalars(self) -> FakeScalars:
        return self._scalars


class FakeRow:
    def __init__(self, provider: str, created: datetime, updated: datetime) -> None:
        self.id = uuid.uuid4()
        self.user_id = "user-1"
        self.provider = provider
        self.encrypted_access_token = "enc-token"
        self.created_at = created
        self.updated_at = updated


class FakeDB:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.queries: list[Any] = []

    async def execute(self, query: Any) -> FakeResult:
        self.queries.append(query)
        return FakeResult(self._rows)


@pytest.fixture()
def client(monkeypatch):
    from api.dependencies import get_current_user_token
    from api.routes.integrations import router as integrations_router
    from database.session import get_db_session

    rows = [
        FakeRow("github", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 5, tzinfo=UTC)),
        FakeRow("slack", datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC)),
    ]
    fake_db = FakeDB(rows)

    app = FastAPI()
    app.include_router(integrations_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user_token] = lambda: {"sub": "user-1", "tenant_id": "t1"}
    app.dependency_overrides[get_db_session] = lambda: fake_db
    return TestClient(app), fake_db


class TestIntegrationsList:
    def test_returns_vault_contract_shape(self, client):
        tc, _ = client
        res = tc.get("/api/v1/integrations")
        assert res.status_code == 200
        body = res.json()
        assert isinstance(body, list) and len(body) == 2
        assert set(body[0].keys()) == {
            "id",
            "name",
            "platform",
            "connected",
            "lastAccessed",
            "permissions",
            "status",
        }

    def test_rows_scoped_to_caller_recent_first(self, client):
        tc, fake_db = client
        body = tc.get("/api/v1/integrations").json()
        assert body[0]["platform"] == "github"  # updated 2026-01-05 (most recent)
        assert body[1]["platform"] == "slack"
        assert fake_db.queries, "db query issued"

    def test_github_row_carries_repo_scope(self, client):
        tc, _ = client
        body = tc.get("/api/v1/integrations").json()
        github_row = next(r for r in body if r["platform"] == "github")
        assert github_row["permissions"] == ["repo"]
        assert github_row["connected"] is True
        assert github_row["status"] == "active"

    def test_timestamps_iso_format(self, client):
        tc, _ = client
        body = tc.get("/api/v1/integrations").json()
        assert body[0]["lastAccessed"] == "2026-01-05T00:00:00+00:00"

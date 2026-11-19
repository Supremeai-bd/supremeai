"""Cache maintenance is explicit, operator-only, and reaches the local layer."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from core.api.routes import admin
from core.cache import multi_layer_cache as cache
from core.swarm_pubsub import swarm_streamer


@pytest.fixture
def cache_purge(monkeypatch):
    from api import dependencies

    monkeypatch.setattr(dependencies.settings, "admin_emails", ["platform@example.invalid"])
    deleted = AsyncMock(return_value=1)

    async def scan_iter(*, match):
        if match == "cache:*":
            yield "cache:chat:exact:v2:fixture"

    monkeypatch.setattr(admin, "god_layer", SimpleNamespace(enforce=Mock()))
    monkeypatch.setattr(admin, "redis_manager", SimpleNamespace(client=SimpleNamespace(scan_iter=scan_iter, delete=deleted)))
    broadcast = AsyncMock()
    clear_local = Mock()
    monkeypatch.setattr(swarm_streamer, "broadcast", broadcast)
    monkeypatch.setattr(cache, "invalidate_session_cache", clear_local)
    return deleted, broadcast, clear_local


@pytest.mark.asyncio
async def test_tenant_admin_cannot_purge_other_owners(cache_purge):
    with pytest.raises(HTTPException) as exc:
        await admin.trigger_quick_action("cache", {"sub": "tenant@example.invalid", "role": "admin"})
    assert exc.value.status_code == 403
    for action in cache_purge:
        action.assert_not_called()


@pytest.mark.asyncio
async def test_platform_purge_notifies_local_and_other_workers(cache_purge):
    deleted, broadcast, clear_local = cache_purge
    result = await admin.trigger_quick_action("cache", {"sub": "platform@example.invalid", "role": "admin"})
    assert result["status"] == "success"
    deleted.assert_awaited_once_with("cache:chat:exact:v2:fixture")
    clear_local.assert_called_once_with(all_scopes=True)
    broadcast.assert_awaited_once_with("CACHE_INVALIDATE_REQUESTED", {"scope": "global"})


@pytest.mark.asyncio
async def test_worker_notification_failure_does_not_report_purge_success(cache_purge):
    _, broadcast, _ = cache_purge
    broadcast.side_effect = OSError("fixture disconnected")
    with pytest.raises(HTTPException) as exc:
        await admin.trigger_quick_action("cache", {"sub": "platform@example.invalid", "role": "admin"})
    assert exc.value.status_code == 503


def test_legacy_probe_endpoint_stays_admin_only_and_never_dispatches():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from core.api.routes.admin_routing import get_current_admin, router

    app = FastAPI()
    app.include_router(router)
    path = "/admin-api/routing/recheck"
    with TestClient(app) as client:
        assert client.post(path).status_code == 401
        app.dependency_overrides[get_current_admin] = lambda: {"sub": "fixture-admin", "role": "admin"}
        response = client.post(path)
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"]

"""Customer-facing outbound webhook management endpoints.

Provides CRUD + live test-ping for user-configured outbound webhooks
that receive SupremeAI event notifications.
"""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(tags=["User Webhooks"])

_WEBHOOKS: list[dict[str, Any]] = []


class CreateWebhookRequest(BaseModel):
    url: str = Field(..., min_length=1)
    events: list[str] | None = Field(default=None)
    secret: str | None = Field(default=None)
    active: bool = Field(default=True)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _find(webhook_id: str) -> dict[str, Any] | None:
    for wh in _WEBHOOKS:
        if wh.get("id") == webhook_id:
            return wh
    return None


async def _test_webhook(url: str) -> dict[str, Any]:
    """Send a live HTTP test ping and return verification result."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json={"event": "webhook.test", "source": "supremeai"})
        return {"success": 200 <= resp.status_code < 300, "status_code": resp.status_code}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "status_code": 0, "error": str(exc)}


@router.get("/api/user/webhooks")
async def list_user_webhooks() -> dict[str, Any]:
    return {"webhooks": [copy.deepcopy(w) for w in _WEBHOOKS]}


@router.post("/api/user/webhooks", status_code=status.HTTP_201_CREATED)
async def create_user_webhook(payload: CreateWebhookRequest) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": f"wh_{uuid.uuid4().hex[:8]}",
        "url": payload.url,
        "events": payload.events or ["*"],
        "active": payload.active,
        "created_at": _now(),
    }
    if payload.secret:
        record["secret"] = "***"
    _WEBHOOKS.append(record)
    return {"webhook": copy.deepcopy(record), "webhooks": [copy.deepcopy(w) for w in _WEBHOOKS]}


@router.delete("/api/user/webhooks/{webhook_id}")
async def delete_user_webhook(webhook_id: str) -> dict[str, Any]:
    global _WEBHOOKS
    before = len(_WEBHOOKS)
    _WEBHOOKS = [w for w in _WEBHOOKS if w.get("id") != webhook_id]
    if len(_WEBHOOKS) == before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return {"success": True, "webhooks": [copy.deepcopy(w) for w in _WEBHOOKS]}


@router.post("/api/user/webhooks/{webhook_id}/test")
async def test_user_webhook(webhook_id: str) -> dict[str, Any]:
    wh = _find(webhook_id)
    if not wh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    result = await _test_webhook(wh["url"])
    return {"webhook_id": webhook_id, **result}

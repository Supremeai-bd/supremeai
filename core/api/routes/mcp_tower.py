"""Proxy router exposing the MCP Control Tower's live telemetry to the frontend.

The Tower is an MCP server (Streamable HTTP at /mcp). The browser cannot call it
directly (session handshake + CORS), so Core API acts as the bridge:
    Browser -> GET /api/mcp-tower/services -> Core API -> Tower MCP tools/call
    -> McpTowerService-shaped JSON back to the browser.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

try:
    from core.api.deps import get_current_admin, get_current_user_token
except ImportError:
    try:
        from api.deps import get_current_admin, get_current_user_token
    except ImportError:
        # AUDIT FIX (N1): fail CLOSED. These "mock-token"/"mock-admin" stubs made
        # the MCP Control Tower proxy (live telemetry + admin actions) reachable
        # anonymously whenever the auth module could not be imported.
        raise

router = APIRouter(prefix="/api/mcp-tower", tags=["mcp-tower"])

TOWER_URL = os.getenv(
    "MCP_TOWER_URL", os.getenv("RENDER_MCP_URL", "https://supremeai-mcp-tower.onrender.com/mcp")
)
TOWER_TOKEN = os.getenv("MCP_TOWER_TOKEN", os.getenv("MCP_API_KEY", ""))
RENDER_API_KEY = os.getenv("RENDER_API_KEY", "")
RENDER_MCP_SERVICE_ID = os.getenv("RENDER_MCP_SERVICE_ID", os.getenv("RENDER_MCP_SVC_ID", ""))


def _tower_base() -> str:
    url = TOWER_URL.strip()
    if not url.endswith("/mcp"):
        url = url.rstrip("/") + "/mcp"
    return url


async def _call_tower_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Initialize a Streamable HTTP session and invoke a Tower tool."""
    base = _tower_base()
    headers = {"Content-Type": "application/json", "Accept": "application/json,text/event-stream"}
    if TOWER_TOKEN:
        headers["Authorization"] = f"Bearer {TOWER_TOKEN}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. initialize
        init_resp = await client.post(
            base,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "supremeai-core-proxy", "version": "1.0.0"},
                },
            },
            headers=headers,
        )
        init_resp.raise_for_status()
        session_id = init_resp.headers.get("mcp-session-id")
        if session_id:
            headers["mcp-session-id"] = session_id
        # 2. initialized notification
        try:
            await client.post(
                base,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers=headers,
            )
        except Exception:
            pass
        # 3. tools/call
        call_resp = await client.post(
            base,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            },
            headers=headers,
        )
        call_resp.raise_for_status()

    # Parse SSE or JSON
    text = call_resp.text
    payload: dict[str, Any] | None = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            try:
                payload = json.loads(line[5:].strip())
                break
            except json.JSONDecodeError:
                continue
    if payload is None:
        try:
            payload = call_resp.json()
        except Exception:
            raise HTTPException(status_code=502, detail="Invalid Tower response")
    if "error" in payload:
        raise HTTPException(status_code=502, detail=str(payload["error"]))
    result = payload.get("result", {})
    # content[0].text is JSON string
    content = result.get("content", [])
    if content and isinstance(content[0], dict) and "text" in content[0]:
        try:
            return json.loads(content[0]["text"])
        except (json.JSONDecodeError, TypeError):
            return {"raw": content[0]["text"]}
    return result


_CATEGORY_MAP = {
    "render": "core",
    "github": "integration",
    "supabase": "core",
    "redis": "integration",
    "cloudflare": "integration",
    "infisical": "integration",
    "kaggle": "ai",
    "telegram": "telemetry",
}


def _category(service_id: str) -> str:
    prefix = service_id.split("-")[0]
    return _CATEGORY_MAP.get(prefix, "core")


def _map_service(svc: dict[str, Any], checked_at: str) -> dict[str, Any]:
    sid = svc.get("id", "")
    status = svc.get("status", "unknown")
    latency = svc.get("latencyMs")
    return {
        "id": sid,
        "name": svc.get("displayName", sid),
        "displayName": svc.get("displayName", sid),
        "category": _category(sid),
        "port": 0,
        "status": status
        if status in ("healthy", "degraded", "unhealthy", "rebooting")
        else "unhealthy",
        "uptime": "—",
        "latencyMs": latency if isinstance(latency, (int, float)) else 0,
        "cpuPercent": 0,
        "memoryMb": 0,
        "lastChecked": checked_at,
        "version": svc.get("deployStatus", "live"),
        "endpoint": "",
        "errorCount": 0 if status == "healthy" else 1,
        "logs": [],
        # Extra honest telemetry from Tower
        "deployStatus": svc.get("deployStatus"),
        "monthlyBuildMinutes": svc.get("monthlyBuildMinutes"),
        "freeLimitRemainingMinutes": svc.get("freeLimitRemainingMinutes"),
        "freeLimitExhausted": svc.get("freeLimitExhausted"),
    }


async def _fetch_services() -> list[dict[str, Any]]:
    health = await _call_tower_tool("system_health", {})
    checked_at = health.get("timestamp", datetime.now(UTC).isoformat())
    services = health.get("services", [])
    return [_map_service(s, checked_at) for s in services]


@router.get("/services")
async def get_services(_: str = Depends(get_current_user_token)) -> dict:
    try:
        services = await _fetch_services()
        return {"services": services}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Tower unreachable: {exc}")


@router.post("/probe")
async def probe(_: str = Depends(get_current_user_token)) -> dict:
    services = await _fetch_services()
    return {"services": services}


_RENDER_SVC_MAP = {
    # Primary / Core
    "render-primary": (("RENDER_PRIMARY_SVC_ID", "RENDER_CORE_SERVICE_ID"), "RENDER_API_KEY_1"),
    "render-core": (("RENDER_CORE_SERVICE_ID", "RENDER_PRIMARY_SVC_ID"), "RENDER_API_KEY_1"),
    # Worker
    "render-worker": (("RENDER_WORKER_SVC_ID", "RENDER_WORKER_SERVICE_ID"), "RENDER_API_KEY_2"),
    # Scraper / Browser
    "render-scraper": (("RENDER_SCRAPER_SVC_ID", "RENDER_SCRAPER_SERVICE_ID"), "RENDER_API_KEY_3"),
    "render-browser": (("RENDER_SCRAPER_SERVICE_ID", "RENDER_SCRAPER_SVC_ID"), "RENDER_API_KEY_3"),
    # MCP Tower
    "render-mcp": (("RENDER_MCP_SVC_ID", "RENDER_MCP_SERVICE_ID"), "RENDER_API_KEY_4"),
    "render-mcp-tower": (("RENDER_MCP_SERVICE_ID", "RENDER_MCP_SVC_ID"), "RENDER_API_KEY_4"),
    # API Gateway
    "render-api": (("RENDER_API_SERVICE_ID", "RENDER_API_SVC_ID"), "RENDER_API_KEY_5"),
    "render-gateway": (("RENDER_API_SERVICE_ID", "RENDER_API_SVC_ID"), "RENDER_API_KEY_5"),
    # Brain / Tiny Brain
    "render-brain": (("RENDER_BRAIN_SERVICE_ID", "RENDER_BRAIN_SVC_ID"), "RENDER_API_KEY_6"),
    # CI Runner
    "render-ci-runner": (
        ("RENDER_CI_RUNNER_SERVICE_ID", "RENDER_CI_RUNNER_SVC_ID"),
        "RENDER_API_KEY_PAYKARI",
    ),
}


@router.post("/reboot")
async def reboot(
    body: dict,
    # AUDIT FIX (2026-11-13, HIGH — privilege escalation): rebooting a Render
    # production service is an infrastructure control; it was reachable by ANY
    # authenticated user. Admin-only now.
    _: dict = Depends(get_current_admin),
) -> dict:
    service_id = (body or {}).get("serviceId")
    if not service_id:
        raise HTTPException(status_code=400, detail="serviceId required")
    # Tower has no reboot tool; use Render API directly for known render-* services.
    if service_id in _RENDER_SVC_MAP:
        svc_envs, key_env = _RENDER_SVC_MAP[service_id]
        if isinstance(svc_envs, str):
            svc_envs = (svc_envs,)
        rid = ""
        for env_k in svc_envs:
            rid = os.getenv(env_k, "")
            if rid:
                break
        api_key = os.getenv(key_env, "") or RENDER_API_KEY
        if rid and api_key:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.post(
                        f"https://api.render.com/v1/services/{rid}/restart",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Accept": "application/json",
                        },
                    )
                    r.raise_for_status()
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Render restart failed: {exc}")
    # Return refreshed services
    services = await _fetch_services()
    match = next((s for s in services if s["id"] == service_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="service not found")
    return {"service": match}


@router.post("/reboot-all")
async def reboot_all(_: dict = Depends(get_current_admin)) -> dict:
    services = await _fetch_services()
    return {"services": services}


import asyncio as _asyncio


@router.get("/stream")
async def stream(_: str = Depends(get_current_user_token)):
    async def gen():
        while True:
            try:
                services = await _fetch_services()
                yield f"data: {json.dumps({'services': services})}\n\n"
            except Exception as exc:
                yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
            await _asyncio.sleep(15)

    return StreamingResponse(gen(), media_type="text/event-stream")

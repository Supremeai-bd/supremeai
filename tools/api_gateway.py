from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger
import httpx
from typing import Dict, Any, Optional
import os

from core.auth_middleware import AuthMiddleware
from core.rate_limiter import RateLimiter

auth_middleware = AuthMiddleware.__new__(AuthMiddleware)
auth_middleware.enabled = bool(os.getenv("SUPREMEAI_API_TOKEN"))
rate_limiter = RateLimiter()

from brain.api_router import ApiRouter

api_router = ApiRouter()
router = APIRouter(prefix="/api/v1/gateway", tags=["gateway"])


class GatewayRequest(BaseModel):
    path: str
    method: str = "GET"
    payload: Optional[Dict[str, Any]] = None
    source: Optional[str] = None  # 'vscode' | 'flutter' | 'telegram' | 'web'
    headers: Optional[Dict[str, str]] = None


class InternalGateway:
    def __init__(self):
        self.n8n_url = os.getenv("N8N_URL", "http://localhost:5678")

    def trigger_n8n_workflow(self, webhook_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.n8n_url}/{webhook_path.lstrip('/')}"
        logger.info(f"Triggering n8n workflow at {url}")
        try:
            response = httpx.post(url, json=payload, timeout=10.0)
            return {
                "success": response.is_success,
                "status_code": response.status_code,
                "data": response.json() if response.is_success else response.text,
            }
        except Exception as exc:
            logger.error(f"n8n trigger failed: {exc}")
            return {"success": False, "error": str(exc)}

    def trigger_make_webhook(self, webhook_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Triggering Make.com webhook")
        try:
            response = httpx.post(webhook_url, json=payload, timeout=10.0)
            return {"success": response.is_success, "response": response.text}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


APIGateway = InternalGateway
ALLOWED_BACKEND_PATHS = {
    "vscode": ["/api/chat/completion", "/api/chat/stream", "/api/knowledge/learn", "/api/memory/ingest", "/api/codeflow/analyze"],
    "flutter": ["/api/chat/message", "/api/chat/history", "/api/knowledge/stats"],
    "telegram": ["/api/chat/message", "/api/knowledge/feedback"],
    "web": ["/api/chat/message", "/api/chat/stream"],
}


@router.post("/forward")
async def gateway_forward(request: GatewayRequest, http_request: Request) -> Response:
    source = (request.source or "web").lower()
    if source not in ALLOWED_BACKEND_PATHS:
        raise HTTPException(status_code=400, detail="unknown source")

    allowed = ALLOWED_BACKEND_PATHS.get(source, [])
    normalized = request.path.strip().lower()
    if not any(normalized == allowed_path.lower() or normalized.startswith(allowed_path.lower() + "/") for allowed_path in allowed):
        logger.warning(f"Blocked path for source={source}: {request.path}")
        raise HTTPException(status_code=403, detail="path not allowed for source")

    client_ip = http_request.client.host if http_request.client else "127.0.0.1"
    if not rate_limiter.check(client_ip):
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    backend_url = os.getenv("SUPREMEAI_BACKEND_URL", "http://localhost:8000/api/v1")
    target = backend_url.rstrip("/") + "/" + request.path.lstrip("/")

    headers = dict(request.headers or {})
    headers.setdefault("X-Source", source)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            req_method = (request.method or "GET").upper()
            if req_method == "POST":
                response = await client.post(target, json=request.payload or {}, headers=headers)
            else:
                response = await client.get(target, headers=headers)
        return JSONResponse(content=response.json(), status_code=response.status_code)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code)
    except Exception as exc:
        logger.exception("gateway forward failed")
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/dispatch/{capability}")
async def api_dispatch(capability: str, payload: Dict[str, Any]) -> JSONResponse:
    try:
        result = api_router.dispatch(capability, payload or {})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    status = 200 if result.get("success", True) else 502
    return JSONResponse(content=result, status_code=status)


@router.post("/n8n")
async def trigger_n8n(webhook_path: str = "", payload: Dict[str, Any] = {}) -> JSONResponse:
    internal = InternalGateway()
    result = internal.trigger_n8n_workflow(webhook_path, payload)
    status = 200 if result.get("success") else 502
    return JSONResponse(content=result, status_code=status)


@router.post("/make")
async def trigger_make(webhook_url: str = "", payload: Dict[str, Any] = {}) -> JSONResponse:
    internal = InternalGateway()
    result = internal.trigger_make_webhook(webhook_url, payload)
    status = 200 if result.get("success") else 502
    return JSONResponse(content=result, status_code=status)

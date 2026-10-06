"""
SupremeAI Service Topology & External Health Checker
=====================================================
Comprehensive ping-test system for ALL external services.
Checks: GitHub, Firebase, Render, Supabase, Cloudflare, Vercel, Krogger, Infisical

Author: SupremeAI Audit Patch
Version: 2.0.0
"""

import asyncio
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from api.dependencies import get_current_admin
from core.config import settings
from core.deployment_fallback_defaults import ADMIN_URL_DEFAULT, SCRAPER_URL_DEFAULT
from core.security.ws_auth import authenticate_websocket

router = APIRouter(prefix="/admin-api", tags=["service-topology"])


class ServiceStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"
    # বাংলা (#3226): নতুন status — সার্ভিস configured না থাকলে (placeholder URL
    # বা খালি env var) probe-এ না গিয়ে SKIPPED রিপোর্ট করা হবে। UNHEALTHY থেকে
    # আলাদা — কারণ configured≠broken, এটা আলাদা operational state।
    SKIPPED = "skipped"


# বাংলা (#3226): placeholder token শনাক্তকরণ — যেসব URL/evidence এখনও
# configured নয় সেগুলোর জন্য probe skip করা হবে, false-UNHEALTHY এড়াতে।
_PLACEHOLDER_TOKENS = ("<project-ref>", "<project-id>", "<your-", "<env>", "<todo>")


def _has_unresolved_placeholder(*values: str) -> bool:
    """Return True if any value contains a placeholder token or is empty."""
    for v in values:
        if not v:
            return True
        if any(tok in v for tok in _PLACEHOLDER_TOKENS):
            return True
    return False


@dataclass
class ServiceConfig:
    name: str
    display_name: str
    category: str  # infrastructure, database, auth, ci_cd, monitoring, secrets, edge
    url: str
    health_endpoint: str
    critical: bool = False
    timeout: float = 10.0
    expected_status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    check_type: str = "http"  # http, api, dns, tcp


@dataclass
class ServiceHealthResult:
    name: str
    display_name: str
    category: str
    status: ServiceStatus
    response_time_ms: float
    status_code: int | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)
    url: str = ""
    critical: bool = False

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "status": self.status.value,
            "checked_at": self.checked_at.isoformat(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# COMPLETE SERVICE REGISTRY (12+ Services)
# ══════════════════════════════════════════════════════════════════════════════

# বাংলা মন্তব্য (#3079): edge-worker URL env-চালিত — প্লেসহোল্ডার host সরানো (লাইভ প্রোব → 404);
# EDGE_WORKER_URL আনসেট হলে টপোলজি-প্রোব স্কিপ (গ্রেসফুল ডিগ্রেডেশন)।
_EDGE_WORKER_URL = os.environ.get("EDGE_WORKER_URL", "").rstrip("/")

COMPLETE_SERVICE_REGISTRY: list[ServiceConfig] = [
    # ─── CORE INFRASTRUCTURE ──────────────────────────────────────────────
    ServiceConfig(
        name="render_backend",
        display_name="Render Backend",
        category="infrastructure",
        url=settings.backend_url,
        health_endpoint="/api/v1/health",
        critical=True,
        timeout=15.0,  # Render cold start can be slow
    ),
    ServiceConfig(
        name="render_admin",
        display_name="Render Admin API",
        category="infrastructure",
        url=os.environ.get("ADMIN_URL", ADMIN_URL_DEFAULT),
        health_endpoint="/api/v1/health",
        critical=True,
        timeout=15.0,
    ),
    ServiceConfig(
        name="scraper_service",
        display_name="Scraper Microservice",
        category="infrastructure",
        url=os.environ.get("SCRAPER_URL", SCRAPER_URL_DEFAULT),
        health_endpoint="/health",
        critical=False,
        timeout=10.0,
    ),
    # ─── DATABASE & STORAGE ──────────────────────────────────────────────
    # বাংলা (#3226): আগে এখানে `url="https://<project-ref>.supabase.co"` hardcoded
    # ছিল — placeholder literal, probe-এ DNS failure → false UNHEALTHY।
    # এখন settings.supabase_url (env SUPABASE_URL) থেকে dynamically read।
    # খালি বা placeholder থাকলে _has_unresolved_placeholder → probe SKIPPED।
    ServiceConfig(
        name="supabase_db",
        display_name="Supabase Database",
        category="database",
        url=settings.supabase_url or "https://<project-ref>.supabase.co",
        health_endpoint="/rest/v1/",
        critical=True,
        timeout=8.0,
        headers={
            "apikey": os.environ.get("SUPABASE_ANON_KEY", ""),
            "Authorization": f"Bearer {os.environ.get('SUPABASE_ANON_KEY', '')}",
        },
        check_type="api",
    ),
    ServiceConfig(
        name="firebase_auth",
        display_name="Firebase Authentication",
        category="auth",
        url="https://identitytoolkit.googleapis.com",
        # বাংলা (#3226): <project-id> → env FIREBASE_PROJECT_ID (fallback
        # VITE_FIREBASE_PROJECT_ID)। খালি হলে placeholder থাকবে → SKIPPED।
        health_endpoint=f"/v1/projects/{os.environ.get('FIREBASE_PROJECT_ID') or os.environ.get('VITE_FIREBASE_PROJECT_ID') or '<project-id>'}:lookup",
        critical=True,
        timeout=8.0,
        check_type="api",
    ),
    ServiceConfig(
        name="firebase_firestore",
        display_name="Cloud Firestore",
        category="database",
        url="https://firestore.googleapis.com",
        health_endpoint=f"/v1/projects/{os.environ.get('FIREBASE_PROJECT_ID') or os.environ.get('VITE_FIREBASE_PROJECT_ID') or '<project-id>'}/databases/(default)/documents",
        critical=True,
        timeout=8.0,
        check_type="api",
    ),
    # ─── EDGE & CDN ───────────────────────────────────────────────────────
    ServiceConfig(
        name="cloudflare_worker",
        display_name="Cloudflare Edge Worker",
        category="edge",
        url=_EDGE_WORKER_URL,
        health_endpoint="/health",
        critical=True,
        timeout=5.0,
    ),
    ServiceConfig(
        name="cloudflare_dns",
        display_name="Cloudflare DNS",
        category="edge",
        url="https://cloudflare-dns.com/dns-query",
        health_endpoint="?name=google.com&type=A",
        critical=False,
        timeout=5.0,
        check_type="dns",
    ),
    # ─── CI/CD & REPOSITORY ──────────────────────────────────────────────
    ServiceConfig(
        name="github_api",
        display_name="GitHub API",
        category="ci_cd",
        url="https://api.github.com",
        health_endpoint="/rate_limit",
        critical=False,
        timeout=8.0,
        headers={"Accept": "application/vnd.github.v3+json"},
        check_type="api",
    ),
    ServiceConfig(
        name="github_actions",
        display_name="GitHub Actions CI",
        category="ci_cd",
        url="https://github.com",
        health_endpoint="/SaifulHaqueNiloy/supremeai/actions",
        critical=False,
        timeout=10.0,
        check_type="http",
    ),
    ServiceConfig(
        name="vercel_deploy",
        display_name="Vercel Deployment",
        category="ci_cd",
        url="https://vercel.com/api",
        health_endpoint="/v2/deployments",
        critical=False,
        timeout=8.0,
        check_type="api",
    ),
    # ─── MONITORING & OBSERVABILITY ───────────────────────────────────────
    ServiceConfig(
        name="krogger_monitoring",
        display_name="Krogger (Monitoring)",
        category="monitoring",
        url="https://krogger.io/api",
        health_endpoint="/v1/status",
        critical=False,
        timeout=6.0,
        check_type="api",
    ),
    ServiceConfig(
        name="sentry_error_tracking",
        display_name="Sentry Error Tracking",
        category="monitoring",
        url="https://sentry.io/api/0",
        health_endpoint="/projects/",
        critical=False,
        timeout=6.0,
        check_type="api",
    ),
    # ─── SECRETS & CONFIGURATION ─────────────────────────────────────────
    ServiceConfig(
        name="infisical_secrets",
        display_name="Infisical Secrets Manager",
        category="secrets",
        url="https://app.infisical.com/api",
        health_endpoint="/v1/secrets",
        critical=True,
        timeout=6.0,
        check_type="api",
    ),

    # ─── LLM PROVIDERS (#4046 — Roadmap v2 Phase 1.3) ───────────────────────
    # বাংলা: প্রতিটি LLM provider service_topology-তে যুক্ত। tri-state:
    #   CONFIGURED (env set) → REACHABLE (TCP+auth ok) → HEALTHY (semantic probe ok)
    # API key না থাকলে SKIPPED (false-UNHEALTHY নয় — #3226 honest-state)।
    # Health endpoint = /v1/models (OpenAI-compatible standard) — returns 200
    # if key valid + service reachable।
    # বাংলা মন্তব্য: provider list `_MODEL_KEY_MAP` থেকে derive করা হয়েছে —
    # single source of truth (backend/core/llm/llm_gateway/registry.py)।
    ServiceConfig(
        name="llm_openai",
        display_name="OpenAI API",
        category="llm_provider",
        url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        health_endpoint="/models",
        critical=False,
        timeout=8.0,
        headers={"Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}"},
        check_type="api",
    ),
    ServiceConfig(
        name="llm_anthropic",
        display_name="Anthropic API",
        category="llm_provider",
        url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/"),
        health_endpoint="/v1/models",
        critical=False,
        timeout=8.0,
        headers={
            "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
            "anthropic-version": "2023-06-01",
        },
        check_type="api",
    ),
    ServiceConfig(
        name="llm_groq",
        display_name="Groq API",
        category="llm_provider",
        url=os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
        health_endpoint="/models",
        critical=False,
        timeout=8.0,
        headers={"Authorization": f"Bearer {os.environ.get('GROQ_API_KEY', '')}"},
        check_type="api",
    ),
    ServiceConfig(
        name="llm_deepseek",
        display_name="DeepSeek API",
        category="llm_provider",
        url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/"),
        health_endpoint="/models",
        critical=False,
        timeout=8.0,
        headers={"Authorization": f"Bearer {os.environ.get('DEEPSEEK_API_KEY', '')}"},
        check_type="api",
    ),
    ServiceConfig(
        name="llm_gemini",
        display_name="Google Gemini API",
        category="llm_provider",
        url="https://generativelanguage.googleapis.com",
        health_endpoint=f"/v1beta/models?key={os.environ.get('GEMINI_API_KEY', '')}",
        critical=False,
        timeout=8.0,
        check_type="api",
    ),
    ServiceConfig(
        name="llm_openrouter",
        display_name="OpenRouter API",
        category="llm_provider",
        url="https://openrouter.ai/api/v1",
        health_endpoint="/models",
        critical=False,
        timeout=8.0,
        headers={"Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}"},
        check_type="api",
    ),
    ServiceConfig(
        name="llm_mistral",
        display_name="Mistral API",
        category="llm_provider",
        url="https://api.mistral.ai/v1",
        health_endpoint="/models",
        critical=False,
        timeout=8.0,
        headers={"Authorization": f"Bearer {os.environ.get('MISTRAL_API_KEY', '')}"},
        check_type="api",
    ),
    ServiceConfig(
        name="llm_huggingface",
        display_name="Hugging Face API",
        category="llm_provider",
        url="https://api-inference.huggingface.co",
        health_endpoint="/models",
        critical=False,
        timeout=8.0,
        headers={"Authorization": f"Bearer {os.environ.get('HF_API_KEY', '')}"},
        check_type="api",
    ),
    ServiceConfig(
        name="llm_nvidia",
        display_name="NVIDIA API",
        category="llm_provider",
        url="https://integrate.api.nvidia.com/v1",
        health_endpoint="/models",
        critical=False,
        timeout=8.0,
        headers={"Authorization": f"Bearer {os.environ.get('NVIDIA_API_KEY', '')}"},
        check_type="api",
    ),
    ServiceConfig(
        name="llm_ollama",
        display_name="Ollama (local)",
        category="llm_provider",
        url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        health_endpoint="/api/tags",
        critical=False,
        timeout=5.0,
        check_type="api",
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK ENGINE
# ══════════════════════════════════════════════════════════════════════════════


async def probe_service(service: ServiceConfig) -> ServiceHealthResult:
    """
    Perform comprehensive health check on a single service.
    Returns detailed health result with timing and error info.
    """
    start_time = time.time()

    # বাংলা (#3226): placeholder guard — URL/evidence-তে এখনও <project-ref>/
    # <project-id> থাকলে (অর্থাৎ configured নয়) probe skip করো, false-UNHEALTHY
    # এড়াতে। SKIPPED ≠ UNHEALTHY — configured≠broken, আলাদা operational state।
    if _has_unresolved_placeholder(service.url, service.health_endpoint):
        return ServiceHealthResult(
            name=service.name,
            display_name=service.display_name,
            category=service.category,
            status=ServiceStatus.SKIPPED,
            response_time_ms=0.0,
            url=service.url,
            error="service not configured — placeholder URL/endpoint unresolved (#3226)",
            critical=service.critical,
        )

    # বাংলা (#4046): LLM provider tri-state — API key absent → SKIPPED (not UNHEALTHY).
    # LLM providers need valid credentials to probe; absent key = not configured, not broken.
    # This is the honest-state pattern from #3226 extended to LLM auth.
    if service.category == "llm_provider":
        has_valid_auth = False
        for k, v in service.headers.items():
            if k.lower() in ("authorization", "x-api-key"):
                if v and len(v.strip()) > 10:  # "Bearer " = 7 chars + key
                    has_valid_auth = True
                    break
        # Gemini uses query param auth (?key=...) — check if key is non-empty after "key="
        if not has_valid_auth and "key=" in service.health_endpoint:
            if len(service.health_endpoint) > len("key=") + 10:
                has_valid_auth = True
        # Ollama is local — no auth needed
        if not has_valid_auth and service.name == "llm_ollama":
            has_valid_auth = True
        if not has_valid_auth:
            return ServiceHealthResult(
                name=service.name,
                display_name=service.display_name,
                category=service.category,
                status=ServiceStatus.SKIPPED,
                response_time_ms=0.0,
                url=service.url,
                error="LLM provider API key not configured — SKIPPED (not UNHEALTHY, per #4046/#3226)",
                critical=service.critical,
            )

    full_url = f"{service.url}{service.health_endpoint}"

    try:
        from utils.http_client import create_async_client

        async with create_async_client(timeout=service.timeout) as client:
            if service.check_type == "dns":
                # DNS check via DoH (DNS over HTTPS)
                response = await client.get(
                    full_url,
                    headers={"Accept": "application/dns-json"},
                )
            else:
                response = await client.get(
                    full_url,
                    headers=service.headers,
                    follow_redirects=True,
                )

            response_time_ms = (time.time() - start_time) * 1000

            # Determine status based on response
            if response.status_code == service.expected_status:
                status = ServiceStatus.HEALTHY

                # Check for degraded performance
                if response_time_ms > 2000:
                    status = ServiceStatus.DEGRADED

                # Try to extract additional details
                details = {}
                try:
                    if response.headers.get("content-type", "").startswith("application/json"):
                        data = response.json()
                        if isinstance(data, dict):
                            details = {
                                k: v
                                for k, v in data.items()
                                if k in ["status", "version", "uptime", "latency"]
                            }
                except Exception:
                    from core.logging_config import logger

                    logger.warning("Ignored exception")

            elif response.status_code >= 500:
                status = ServiceStatus.UNHEALTHY
                details = {"error": f"HTTP {response.status_code}"}
            elif response.status_code == 503:
                status = ServiceStatus.MAINTENANCE
                details = {"error": "Service under maintenance"}
            else:
                status = ServiceStatus.DEGRADED
                details = {"error": f"Unexpected status: {response.status_code}"}

            return ServiceHealthResult(
                name=service.name,
                display_name=service.display_name,
                category=service.category,
                status=status,
                response_time_ms=round(response_time_ms, 2),
                status_code=response.status_code,
                details=details,
                url=service.url,
                critical=service.critical,
            )

    except httpx.TimeoutException:
        return ServiceHealthResult(
            name=service.name,
            display_name=service.display_name,
            category=service.category,
            status=ServiceStatus.UNHEALTHY,
            response_time_ms=(time.time() - start_time) * 1000,
            error=f"Timeout after {service.timeout}s",
            url=service.url,
            critical=service.critical,
        )

    except httpx.ConnectError as e:
        return ServiceHealthResult(
            name=service.name,
            display_name=service.display_name,
            category=service.category,
            status=ServiceStatus.UNHEALTHY,
            response_time_ms=(time.time() - start_time) * 1000,
            error=f"Connection refused: {str(e)[:100]}",
            url=service.url,
            critical=service.critical,
        )

    except Exception as e:
        return ServiceHealthResult(
            name=service.name,
            display_name=service.display_name,
            category=service.category,
            status=ServiceStatus.UNKNOWN,
            response_time_ms=(time.time() - start_time) * 1000,
            error=str(e)[:200],
            url=service.url,
            critical=service.critical,
        )


async def probe_all_services() -> list[ServiceHealthResult]:
    """Probe all services concurrently."""
    # বাংলা মন্তব্য (#3079): খালি URL (কনফিগার-অনুপস্থিত) সার্ভিস প্রোব-তালিকা থেকে বাদ।
    probed = [svc for svc in COMPLETE_SERVICE_REGISTRY if svc.url]
    tasks = [probe_service(svc) for svc in probed]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    services = []
    for i, result in enumerate(results):
        if isinstance(result, BaseException):
            svc = probed[i]
            services.append(
                ServiceHealthResult(
                    name=svc.name,
                    display_name=svc.display_name,
                    category=svc.category,
                    status=ServiceStatus.UNKNOWN,
                    response_time_ms=0,
                    error=str(result),
                    url=svc.url,
                    critical=svc.critical,
                )
            )
        else:
            services.append(result)

    return services


def calculate_topology_data(services: list[ServiceHealthResult]) -> dict[str, Any]:
    """
    Calculate topology graph data showing service dependencies and connections.
    Returns nodes and edges for visualization.
    """
    nodes = []
    edges = []

    # Category positions for layout
    category_positions = {
        "infrastructure": {"x": 400, "y": 200},
        "database": {"x": 200, "y": 350},
        "auth": {"x": 100, "y": 200},
        "edge": {"x": 600, "y": 100},
        "ci_cd": {"x": 600, "y": 300},
        "monitoring": {"x": 400, "y": 450},
        "secrets": {"x": 100, "y": 450},
    }

    # Create nodes
    for svc in services:
        pos = category_positions.get(svc.category, {"x": 300, "y": 300})
        nodes.append(
            {
                "id": svc.name,
                "label": svc.display_name,
                "category": svc.category,
                "status": svc.status.value,
                "critical": svc.critical,
                "responseTime": svc.response_time_ms,
                "position": {
                    "x": pos["x"] + (len([s for s in services if s.category == svc.category]) * 80),
                    "y": pos["y"],
                },
            }
        )

    # Define edges (dependencies)
    edge_definitions = [
        ("render_backend", "supabase_db"),
        ("render_backend", "firebase_auth"),
        ("render_admin", "firebase_auth"),
        ("render_admin", "supabase_db"),
        ("scraper_service", "render_backend"),
        ("cloudflare_worker", "render_backend"),
        ("github_actions", "github_api"),
        ("vercel_deploy", "github_api"),
        ("krogger_monitoring", "render_backend"),
        ("infisical_secrets", "render_backend"),
    ]

    for source, target in edge_definitions:
        if any(s.name == source for s in services) and any(s.name == target for s in services):
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "type": "dependency",
                }
            )

    return {
        "nodes": nodes,
        "edges": edges,
        "generatedAt": datetime.utcnow().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# REST API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════


class TopologyResponse(BaseModel):
    timestamp: datetime
    overall_status: str
    services: list[dict]
    topology: dict[str, Any]
    summary: dict[str, int]
    alerts: list[str]


@router.get("/service-topology", response_model=TopologyResponse)
async def get_service_topology(_admin: dict = Depends(get_current_admin)):
    """
    Get complete service topology with health status.
    Returns nodes/edges for graph visualization plus health data.
    """
    services = await probe_all_services()
    topology = calculate_topology_data(services)

    # Calculate summary — বাংলা (#3226): `skipped` কাউন্ট যোগ (configured-নয় সার্ভিস)
    summary = {"healthy": 0, "degraded": 0, "unhealthy": 0, "unknown": 0, "maintenance": 0, "skipped": 0}
    for svc in services:
        summary[svc.status.value] = summary.get(svc.status.value, 0) + 1

    # Determine overall status
    critical_unhealthy = any(
        svc.critical and svc.status in [ServiceStatus.UNHEALTHY, ServiceStatus.UNKNOWN]
        for svc in services
    )

    if critical_unhealthy or summary["unhealthy"] > 0:
        overall = "unhealthy"
    elif summary["degraded"] > 0:
        overall = "degraded"
    else:
        overall = "healthy"

    # Generate alerts
    alerts = []
    for svc in services:
        if svc.critical and svc.status in [ServiceStatus.UNHEALTHY, ServiceStatus.UNKNOWN]:
            alerts.append(
                f"🚨 CRITICAL: {svc.display_name} is {svc.status.value.upper()} - {svc.error}"
            )
        elif svc.status == ServiceStatus.DEGRADED:
            alerts.append(
                f"⚠️ WARNING: {svc.display_name} is degraded ({svc.response_time_ms:.0f}ms)"
            )

    return TopologyResponse(
        timestamp=datetime.utcnow(),
        overall_status=overall,
        services=[s.to_dict() for s in services],
        topology=topology,
        summary=summary,
        alerts=alerts,
    )


@router.get("/ping-all")
async def ping_all_services(_admin: dict = Depends(get_current_admin)):
    """
    Quick ping test for all services.
    Simplified response for dashboard widgets.
    """
    services = await probe_all_services()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "count": len(services),
        "results": [
            {
                "name": s.name,
                "display": s.display_name,
                "status": s.status.value,
                "latency": s.response_time_ms,
                "critical": s.critical,
            }
            for s in services
        ],
    }


@router.get("/ping-service")
async def ping_single_service(
    service_name: str = Query(..., description="Service name to ping"),
    _admin: dict = Depends(get_current_admin),
):
    """
    Ping a specific service by name.
    Useful for debugging from admin panel.
    """
    service = next((s for s in COMPLETE_SERVICE_REGISTRY if s.name == service_name), None)

    if not service:
        return {"error": f"Service '{service_name}' not found in registry"}

    result = await probe_service(service)
    return result.to_dict()


@router.get("/service-categories")
async def get_service_categories(_admin: dict = Depends(get_current_admin)):
    """
    Get all service categories with their services.
    Useful for filtering in UI.
    """
    categories = {}
    for svc in COMPLETE_SERVICE_REGISTRY:
        if svc.category not in categories:
            categories[svc.category] = []
        categories[svc.category].append(
            {
                "name": svc.name,
                "display": svc.display_name,
                "critical": svc.critical,
                "url": svc.url,
            }
        )

    return categories


# ══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET ENDPOINT - Real-time Health Stream
# ══════════════════════════════════════════════════════════════════════════════


class ConnectionManager:
    """Manage WebSocket connections for real-time health updates."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_health(self, data: dict):
        """Send health update to all connected clients."""
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(data)
            except Exception:
                await self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/health-stream")
async def health_stream_websocket(websocket: WebSocket, token: str | None = None):
    """
    Real-time health status stream over WebSocket.
    Clients connect and receive updates every 10 seconds.

    AUD-2.1/AUD-2.6: this endpoint sits under the admin prefix but previously
    performed NO authentication. A valid admin token is now required.
    """
    token = token or websocket.query_params.get("token")
    user = await authenticate_websocket(websocket, token, require_admin=True)
    if user is None:
        return

    await manager.connect(websocket)

    try:
        # Send initial full state
        services = await probe_all_services()
        topology = calculate_topology_data(services)

        await websocket.send_json(
            {
                "type": "full_state",
                "data": {
                    "services": [s.to_dict() for s in services],
                    "topology": topology,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }
        )

        # Send updates every 10 seconds
        while True:
            await asyncio.sleep(10)

            services = await probe_all_services()

            # Only send changed services
            changes = [s.to_dict() for s in services if s.status != ServiceStatus.HEALTHY]

            await websocket.send_json(
                {
                    "type": "update",
                    "data": {
                        "services": [s.to_dict() for s in services],
                        "changes": changes,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                }
            )

    except WebSocketDisconnect:
        manager.disconnect(websocket)

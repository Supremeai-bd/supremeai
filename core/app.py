from fastapi import FastAPI, Body, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
security = HTTPBasic()
settings.validate()

from admin.god import AdminGodLayer
from brain.model_router import ModelRouter
from core.intent import IntentClassifier
from api.routes import (
    task_router,
    simulator_router,
    browser_router,
    stream_router,
    agent_router,
    media_router,
    knowledge_router,
    marketplace_router,
    metrics_router,
    auth_router,
    codeflow_router,
    feedback_router,
    memory_router,
    admin_dashboard_router,
)
from core.auth_middleware import AuthMiddleware
from core.observability_middleware import ObservabilityMiddleware
from core.rate_limiter import RateLimitMiddleware
from core.telemetry import setup_tracing
import sentry_sdk
import secrets

setup_tracing()

if settings.sentry_dsn:
    try:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=1.0,
            environment=settings.env,
        )
    except Exception:
        pass


def _docs_auth(credentials: HTTPBasicCredentials = Depends(security)):
    correct = secrets.compare_digest(credentials.username, settings.docs_username) and \
              secrets.compare_digest(credentials.password, settings.docs_password)
    if not correct:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def _maybe_docs_auth():
    if settings.docs_auth_enabled and not settings.debug:
        return [_docs_auth]
    return []


docs_auth_dep = _maybe_docs_auth()

is_prod = settings.env.lower() == "production"
docs_enabled = settings.debug or not is_prod or settings.docs_auth_enabled

app = FastAPI(
    title=f"{settings.app_name} (Phase 0)",
    debug=settings.debug,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
    dependencies=docs_auth_dep,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware, requests_per_minute=120, burst=20)
app.add_middleware(AuthMiddleware)
app.add_middleware(ObservabilityMiddleware)

from brain.parallel_cloud_router import ParallelCloudRouter
from brain.gcp_router import GCPCloudRunRouter
from core.gcp_firestore import GCPFirestoreVerificationQueue
from core.gcp_pubsub_queue import GCPPubSubQueue
from tools.gcp_cloud_functions import GCPCloudFunctionClient

model_router = ModelRouter()
intent_clf = IntentClassifier()
admin_god = AdminGodLayer(settings.admin_rules_db)
parallel_router = ParallelCloudRouter()
gcp_router = GCPCloudRunRouter()
verification_queue = GCPFirestoreVerificationQueue()
gcp_pubsub_queue = GCPPubSubQueue()
cloud_function_client = GCPCloudFunctionClient()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "orchestrator": "online",
        "env": settings.env,
    }


@app.get("/actuator/health")
def actuator_health():
    return {
        "status": "UP",
        "orchestrator": "online",
    }


@app.get("/admin/cloud-distribution")
def cloud_distribution():
    return {
        "distribution": parallel_router.get_distribution_stats(),
        "total_requests": sum(p["current_requests"] for p in parallel_router.PROVIDERS.values()),
        "active_providers": sum(1 for p in parallel_router.PROVIDERS.values() if p["status"] == "active"),
        "strategy": "parallel_active_active",
        "rebalance_interval": "1 hour"
    }


@app.get("/gcp/health")
def gcp_health():
    return {
        "status": "ok",
        "cloud_run": gcp_router.health_check(timeout=3),
        "firestore_mode": verification_queue.provider,
        "pubsub_mode": gcp_pubsub_queue.provider,
        "cloud_functions": cloud_function_client.get_config(),
    }


@app.get("/gcp/verification-queue/stats")
def gcp_verification_queue_stats():
    return verification_queue.stats()


@app.get("/gcp/pubsub/stats")
def gcp_pubsub_stats():
    return gcp_pubsub_queue.stats()


app.include_router(memory_router)
app.include_router(task_router)
app.include_router(simulator_router)
app.include_router(browser_router)
app.include_router(stream_router)
app.include_router(agent_router)
app.include_router(media_router)
app.include_router(knowledge_router)
app.include_router(marketplace_router)
app.include_router(metrics_router)
app.include_router(auth_router)
app.include_router(admin_dashboard_router)
if codeflow_router is not None:
    app.include_router(codeflow_router)
if feedback_router is not None:
    app.include_router(feedback_router)


from core.universal_rules import UniversalRulesEngine
rules_engine = UniversalRulesEngine()

@app.get("/admin/rules")
def get_admin_rules():
    return rules_engine.rules

@app.post("/admin/rules")
def post_admin_rules(payload: dict = Body(...)):
    new_rules = payload.get("rules")
    if new_rules:
        success = rules_engine.save_rules(new_rules)
        if success:
            return {"status": "success"}
    return {"status": "error", "message": "Failed to save rules"}

@app.get("/skills")
def get_skills():
    return {
        "web_scraper": {
            "name": "web_scraper",
            "version": "1.0.0",
            "description": "Scrapes website contents using BeautifulSoup."
        },
        "csv_exporter": {
            "name": "csv_exporter",
            "version": "1.0.0",
            "description": "Exports tabular data to CSV using pandas."
        }
    }


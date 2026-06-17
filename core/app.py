from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
settings.validate()

from admin.god import AdminGodLayer
from brain.model_router import ModelRouter
from core.intent import IntentClassifier
from api.routes.task import router as task_router
from api.routes.simulator import router as simulator_router
from api.routes.browser import router as browser_router
from api.routes.stream import router as stream_router
from api.routes.agent_tasks import agent_router as agent_router
from api.routes.media import router as media_router
from api.routes.knowledge import router as knowledge_router
from api.routes.marketplace import router as marketplace_router
from api.routes.metrics import router as metrics_router
from api.routes.auth import router as auth_router
try:
    from api.routes.codeflow import router as codeflow_router
except ImportError:
    codeflow_router = None
try:
    from api.routes.feedback import router as feedback_router
except ImportError:
    feedback_router = None
from core.auth_middleware import AuthMiddleware
from core.rate_limiter import RateLimitMiddleware
import sentry_sdk

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=1.0,
        environment=settings.env,
    )

app = FastAPI(title=f"{settings.app_name} (Phase 0)", debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware, requests_per_minute=120, burst=20)
app.add_middleware(AuthMiddleware)

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
if codeflow_router is not None:
    app.include_router(codeflow_router)
if feedback_router is not None:
    app.include_router(feedback_router)

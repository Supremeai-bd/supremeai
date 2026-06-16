from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from admin.god import AdminGodLayer
from brain.model_router import ModelRouter
from core.intent import IntentClassifier
from api.routes.task import router as task_router
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model_router = ModelRouter()
intent_clf = IntentClassifier()
admin_god = AdminGodLayer(settings.admin_rules_db)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "orchestrator": "online",
        "env": settings.env,
    }


app.include_router(task_router)

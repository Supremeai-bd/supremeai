"""SupremeAI Tiny AI Brain Backend — 512MB Micro-Service.

বাংলা: আল্ট্রা-লাইটওয়েট মাইক্রো-এআই ব্রেন সার্ভিস। 
512MB RAM সিলিংয়ে চলার উপযোগী অপ্টিমাইজড FastAPI মাইক্রোসার্ভিস।
- মেমোরি কনজিউম কম (100MB এর কম)
- দ্রুত মেগাস্ট্রিম বা ইনফারেন্স ক্যাশ রাউটিং
- মডেল ইনফারেন্স ডেলিগেশন ও হেলথ মেট্রিক্স
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("supremeai.tiny_brain")

# Auth header definition
API_KEY_NAME = "x-brain-token"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

BRAIN_AUTH_TOKEN = os.getenv("BRAIN_AUTH_TOKEN", "")

# Bounded worker-local cache for deterministic route decisions.
DECISION_CACHE: dict[tuple[str, str | None, str | None, bool], dict[str, Any]] = {}
CACHE_MAX_ENTRIES = 500


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(">>> Booting SupremeAI 512MB Micro-AI Brain Backend...")
    yield
    logger.info(">>> Shutting down SupremeAI Tiny AI Brain Backend...")


app = FastAPI(
    title="SupremeAI Tiny Brain Service",
    description="Ultra-lightweight 512MB Micro-AI Decision Engine and Router",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — explicit trusted origins only (no wildcard with credentials)
#
# The default used to be one comma-joined string literal, which had two problems
# the other CORS defaults did not: no env var could ADD an origin (the literal
# replaced the list rather than seeding it), and the canonical Studio origin
# from config/service_registry.yaml was absent while retired hosts were present.
# The floor comes from core.middleware.cors_policy when available; if deployed
# in an isolated container context where `core` is not packaged, a defensive fallback is used.
try:
    from core.middleware.cors_policy import (  # noqa: E402
        DEFAULT_USER_ALLOWED_ORIGINS as _BRAIN_ORIGIN_FLOOR,
    )
except (ImportError, ModuleNotFoundError):
    # বাংলা মন্তব্য: আইসোলেটেড ব্রেন ডকার কন্টেইনারে `core` প্যাকেজ অনুপস্থিত থাকলে নিরাপদ ফলব্যাক অরিজিন
    _BRAIN_ORIGIN_FLOOR = (
        "https://supremeai-studio.pages.dev",
        "https://studio.supremeai.lat",
    )

_DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")

_env_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "").split(",")
    if o.strip() and o.strip() != "*"
]
ALLOWED_ORIGINS = list(
    dict.fromkeys([*_env_origins, *_BRAIN_ORIGIN_FLOOR, *_DEV_ORIGINS])
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    # Credentialed CORS must not reflect arbitrary request headers. These are
    # the only headers used by this service's browser-facing API contract.
    allow_headers=["Accept", "Authorization", "Content-Type", API_KEY_NAME],
)


def verify_brain_token(token: str | None = Depends(api_key_header)) -> bool:
    """Validate internal microservice authorization if BRAIN_AUTH_TOKEN is configured."""
    if not BRAIN_AUTH_TOKEN:
        return True
    if token != BRAIN_AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized brain access")
    return True


# Schemas
class RouteRequest(BaseModel):
    task: str = Field(..., description="Task description or prompt")
    complexity: str | None = Field("low", description="low | medium | high")
    preferred_provider: str | None = Field("auto", description="auto | openrouter | gemini | local")
    context_length: int | None = Field(0, description="Estimated token length")


class RouteDecision(BaseModel):
    recommended_model: str
    tier: str
    estimated_latency_ms: int
    delegation_url: str | None = None
    cached: bool = False


class CognitiveEvalRequest(BaseModel):
    prompt: str
    options: list[str]


class CognitiveEvalResponse(BaseModel):
    selected_option: str
    confidence: float
    reasoning: str


@app.get("/")
def root():
    return {
        "service": "supremeai-tiny-brain",
        "status": "online",
        "memory_profile": "512MB-optimized",
        "timestamp": time.time(),
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "cache_size": len(DECISION_CACHE),
        "uptime": time.time(),
    }


@app.get("/release")
def release():
    commit = (
        os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("GIT_COMMIT")
        or os.getenv("GITHUB_SHA")
        or os.getenv("COMMIT_SHA")
        or ""
    ).strip()
    return {
        "service": os.getenv("RENDER_SERVICE_NAME") or "supremeai-tiny-brain",
        "environment": os.getenv("RENDER_ENV") or os.getenv("ENV", "production"),
        "commit": commit,
        "build_id": os.getenv("RENDER_DEPLOY_ID") or os.getenv("RENDER_INSTANCE_ID") or "",
    }


@app.post("/v1/brain/route", response_model=RouteDecision)
def route_task(req: RouteRequest, authorized: bool = Depends(verify_brain_token)):
    """Ultra-fast deterministic model routing based on memory footprint and complexity."""
    # Cache the context bucket used by the rule, not an unrelated prior decision.
    use_flagship = req.complexity == "high" or (req.context_length or 0) > 8000
    cache_key = (req.task[:100], req.complexity, req.preferred_provider, use_flagship)
    if cached_result := DECISION_CACHE.get(cache_key):
        return {**cached_result, "cached": True}

    # Minimal deterministic routing logic
    if use_flagship:
        decision = {
            "recommended_model": "google/gemini-2.5-pro",
            "tier": "flagship",
            "estimated_latency_ms": 950,
            "delegation_url": "https://openrouter.ai/api/v1",
            "cached": False,
        }
    elif req.complexity == "medium":
        decision = {
            "recommended_model": "google/gemini-2.5-flash",
            "tier": "standard",
            "estimated_latency_ms": 350,
            "delegation_url": "https://openrouter.ai/api/v1",
            "cached": False,
        }
    else:
        # Low complexity / Micro-AI
        decision = {
            "recommended_model": "google/gemma-2-9b-it:free",
            "tier": "zero-cost-micro",
            "estimated_latency_ms": 120,
            "delegation_url": "https://openrouter.ai/api/v1",
            "cached": False,
        }

    # Evict if cache exceeds threshold
    if len(DECISION_CACHE) >= CACHE_MAX_ENTRIES:
        DECISION_CACHE.pop(next(iter(DECISION_CACHE)))
    DECISION_CACHE[cache_key] = decision

    return decision


@app.post("/v1/brain/evaluate", response_model=CognitiveEvalResponse)
def evaluate_options(req: CognitiveEvalRequest, authorized: bool = Depends(verify_brain_token)):
    """Fast heuristics-based decision arbitrator without full LLM roundtrip overhead."""
    if not req.options:
        raise HTTPException(status_code=400, detail="Options list cannot be empty")

    # Lightweight heuristics scoring
    best_opt = req.options[0]
    best_score = 0.0

    prompt_tokens = set(req.prompt.lower().split())
    for opt in req.options:
        opt_tokens = set(opt.lower().split())
        overlap = len(prompt_tokens.intersection(opt_tokens))
        score = overlap / max(len(opt_tokens), 1)
        if score > best_score:
            best_score = score
            best_opt = opt

    confidence = min(round(0.5 + (best_score * 0.5), 2), 0.99)
    return {
        "selected_option": best_opt,
        "confidence": confidence,
        "reasoning": f"Heuristic overlap confidence score: {confidence}",
    }
# --- PR risk evaluation endpoint (AI-Gated Auto-Merge) ---

class PRRiskRequest(BaseModel):
    pr_number: int = Field(..., description="Pull request number")
    files: list[str] = Field(default_factory=list, description="Changed file paths")
    diff_stats: dict[str, int] = Field(default_factory=dict, description="additions/deletions")
    ci_test_status: str = Field("100%_PASS", description="CI test status")


class PRRiskDecision(BaseModel):
    verdict: str = Field(..., description="AUTO_MERGE or HUMAN_REVIEW")
    risk_level: str = Field(..., description="LOW or HIGH")
    confidence: float = Field(..., description="0..1 confidence")
    reasoning: str = Field(..., description="Short reasoning")


@app.post("/v1/brain/pr-risk", response_model=PRRiskDecision)
def evaluate_pr_risk(req: PRRiskRequest, authorized: bool = Depends(verify_brain_token)):
    """Lightweight PR risk decision for AI-gated auto-merge (fail-closed friendly)."""
    if req.ci_test_status != "100%_PASS":
        return {
            "verdict": "HUMAN_REVIEW",
            "risk_level": "HIGH",
            "confidence": 0.5,
            "reasoning": "CI tests are not fully green; escalating to human review.",
        }
    additions = int((req.diff_stats or {}).get("additions", 0) or 0)
    if additions > 500:
        return {
            "verdict": "HUMAN_REVIEW",
            "risk_level": "HIGH",
            "confidence": 0.7,
            "reasoning": "Large diff (>500 added lines); requires human review.",
        }
    if not req.files:
        return {
            "verdict": "HUMAN_REVIEW",
            "risk_level": "HIGH",
            "confidence": 0.6,
            "reasoning": "No changed files reported; escalating for safety.",
        }
    return {
        "verdict": "AUTO_MERGE",
        "risk_level": "LOW",
        "confidence": 0.98,
        "reasoning": "Routine change with green CI and bounded diff.",
    }

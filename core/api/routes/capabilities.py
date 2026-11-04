from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import get_current_user_token
from core.capability_discovery import discover_capabilities
from core.capability_gateway import HEALTH_CAPABILITY, execute_capability

router = APIRouter(prefix="/api/v1/capabilities", tags=["capabilities"])

# Mirror of scripts/ci/check_free_tier_limits.py HEAVY_PACKAGES — the deps the
# free-tier dependency policy deliberately excludes from production builds.
# Issue #450: silent degradations must be REPORTED, not just enforced in CI.
_HEAVY_PACKAGES = {
    "torch": "torch",
    "torchvision": "torchvision",
    "torchaudio": "torchaudio",
    "sentence_transformers": "sentence-transformers",
    "transformers": "transformers",
    "tensorflow": "tensorflow",
    "keras": "keras",
}

# feature key → (import module, pip package, honest degradation note)
_RUNTIME_FEATURES: list[tuple[str, str, str, str]] = [
    (
        "local_semantic_encoder",
        "sentence_transformers",
        "sentence-transformers",
        "Local encoder unavailable — embeddings ride the Cloudflare Workers AI → "
        "LiteLLM → hash chain (core/embeddings.py); quality degraded, not dead.",
    ),
    (
        "gpu_training",
        "torch",
        "torch",
        "Local model training impossible in this container — remote providers "
        "only (Kaggle/RunPod).",
    ),
    (
        "hf_transformers",
        "transformers",
        "transformers",
        "Transformers pipelines unavailable — remote inference providers only.",
    ),
    (
        "vector_store_chromadb",
        "chromadb",
        "chromadb",
        "ChromaDB unavailable or gated by LOW_MEMORY_MODE — Supabase pgvector "
        "serves as the persistent vector store.",
    ),
    (
        "vector_store_qdrant",
        "qdrant_client",
        "qdrant-client",
        "Qdrant client unavailable — Redis/Supabase context paths only.",
    ),
    (
        "browser_automation",
        "playwright",
        "playwright",
        "Playwright browser automation unavailable — deep research falls back "
        "to the scout crawler (CrawlPolicy-gated) only.",
    ),
    (
        "tts_edge",
        "edge_tts",
        "edge-tts",
        "edge-tts unavailable — TTS requires the ElevenLabs provider key.",
    ),
    (
        "sandbox_e2b",
        "e2b",
        "e2b",
        "E2B cloud sandbox unavailable — code execution returns honest "
        "SANDBOX_UNAVAILABLE (issue #448 doctrine).",
    ),
    (
        "llm_litellm",
        "litellm",
        "litellm",
        "LiteLLM bridge unavailable — dynamic AI provider chain narrowed.",
    ),
]


def _has_key(*names: str) -> bool:
    """True if ANY of the given env vars is set to a non-empty value."""
    return any(os.getenv(n, "").strip() for n in names)


@router.get("/runtime")
async def runtime_capabilities(user: dict = Depends(get_current_user_token)) -> dict:
    """Honest runtime capability matrix (issue #450).

    Reports what THIS running container can actually do: per-feature import
    availability, whether the free-tier dependency policy excludes it, the
    honest degradation path, and which third-party provider keys are wired.
    Values only — never secret contents.
    """
    from core.integrations._flags import import_available

    low_memory_mode = os.getenv("LOW_MEMORY_MODE", "false").lower() == "true"

    features = []
    for feature, module, package, degradation in _RUNTIME_FEATURES:
        importable = import_available(module)
        # LOW_MEMORY_MODE deliberately refuses the local encoder even when the
        # package is installed (core/embeddings.py gates it off).
        available = importable and not (module == "sentence_transformers" and low_memory_mode)
        features.append(
            {
                "feature": feature,
                "available": available,
                "importable": importable,
                "policy_excluded": package in _HEAVY_PACKAGES.values(),
                "degradation_note": None if available else degradation,
            }
        )

    integrations = {
        "gemini_vision": _has_key("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "groq_stt": _has_key("GROQ_API_KEY"),
        "openrouter_llm": _has_key("OPENROUTER_API_KEY"),
        "openai_llm": _has_key("OPENAI_API_KEY"),
        "cloudflare_workers_ai": _has_key("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_API_KEY")
        and _has_key("CLOUDFLARE_ACCOUNT_ID"),
        "elevenlabs_tts": _has_key("ELEVENLABS_API_KEY"),
        "kaggle_training": _has_key(
            "KAGGLE_API_TOKEN",
            "KAGGLE_API_TOKEN_1",
            "KAGGLE_USERNAME",
        ),
        "runpod_training": _has_key("RUNPOD_API_KEY"),
        "supabase_memory": _has_key("SUPABASE_URL", "SUPABASE_KEY"),
        "telegram_alerts": _has_key("TELEGRAM_BOT_TOKEN"),
    }

    return {
        "environment": os.getenv("ENV", "production"),
        "low_memory_mode": low_memory_mode,
        "features": features,
        "integrations": integrations,
        "note": "availability truth-source: importlib at request time; "
        "policy exclusions mirror scripts/ci/check_free_tier_limits.py",
    }


class CapabilityExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str = Field(default=HEALTH_CAPABILITY, min_length=1, max_length=160)
    source: str = Field(default="api", min_length=1, max_length=40)
    payload: dict = Field(default_factory=dict)


@router.get("")
async def list_capabilities(user: dict = Depends(get_current_user_token)) -> dict:
    actor_id = str(user.get("sub") or "")
    tenant_id = str(user.get("tenant_id") or actor_id)
    if not actor_id or not tenant_id:
        raise HTTPException(status_code=401, detail="Execution identity is incomplete")
    return {"capabilities": discover_capabilities(tenant_id)}


@router.post("/execute")
async def execute(
    request: CapabilityExecuteRequest,
    user: dict = Depends(get_current_user_token),
) -> dict:
    actor_id = str(user.get("sub") or "")
    tenant_id = str(user.get("tenant_id") or actor_id)
    if not actor_id or not tenant_id:
        raise HTTPException(status_code=401, detail="Execution identity is incomplete")

    result = await execute_capability(
        actor_id=actor_id,
        tenant_id=tenant_id,
        source=request.source,
        capability=request.capability,
        payload=request.payload,
    )
    if result.status.value == "unavailable":
        raise HTTPException(
            status_code=404, detail=result.error_message or "Capability unavailable"
        )
    if result.status.value == "rejected":
        raise HTTPException(status_code=403, detail=result.error_message or "Capability rejected")
    return result.model_dump(mode="json")
from core.services.config_registry import safe_defaults as _safe_defaults


class _CapabilityStatus(BaseModel):
    state: str  # live | degraded | unavailable | planned | deprecated
    requires_auth: bool = False
    reason_code: str | None = None


class _CapabilitiesStatusResponse(BaseModel):
    config_version: int = 1
    capabilities: dict[str, _CapabilityStatus]


def _browser_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


@router.get("/status", response_model=_CapabilitiesStatusResponse)
async def capability_status() -> _CapabilitiesStatusResponse:
    """Public capability status profile (no auth).

    Used by frontend degraded banners, navigation visibility, admin health
    dashboard, smoke tests and release checks. State is one of:
    live | degraded | unavailable | planned | deprecated.
    """
    defaults = _safe_defaults(public_only=True)
    features = {
        "chat": bool(defaults.get("feature.chat", True)),
        "research": bool(defaults.get("feature.research", True)),
        "scheduled_tasks": bool(defaults.get("feature.scheduled_tasks", True)),
        "browser": bool(defaults.get("feature.browser", False)),
        "billing": bool(defaults.get("feature.billing", True)),
    }
    maintenance = bool(defaults.get("system.maintenance_mode", False))

    caps: dict[str, _CapabilityStatus] = {}

    def _simple(name: str, feat: bool, requires_auth: bool) -> None:
        if maintenance:
            caps[name] = _CapabilityStatus(state="degraded", requires_auth=requires_auth, reason_code="MAINTENANCE_MODE")
        elif feat:
            caps[name] = _CapabilityStatus(state="live", requires_auth=requires_auth)
        else:
            caps[name] = _CapabilityStatus(state="unavailable", requires_auth=requires_auth, reason_code="FEATURE_DISABLED")

    _simple("chat", features["chat"], False)
    _simple("research", features["research"], True)
    _simple("scheduled_tasks", features["scheduled_tasks"], True)
    _simple("billing", features["billing"], True)

    # Browser has a planned/unavailable distinction.
    if not features["browser"]:
        caps["browser"] = _CapabilityStatus(state="planned", reason_code="FEATURE_DISABLED")
    elif not _browser_available():
        caps["browser"] = _CapabilityStatus(state="unavailable", requires_auth=True, reason_code="BROWSER_RUNTIME_MISSING")
    elif maintenance:
        caps["browser"] = _CapabilityStatus(state="degraded", requires_auth=True, reason_code="MAINTENANCE_MODE")
    else:
        caps["browser"] = _CapabilityStatus(state="live", requires_auth=True)

    return _CapabilitiesStatusResponse(capabilities=caps)

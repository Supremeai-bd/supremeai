"""Cognitive pipeline dispatch surface — Core API → MasterCognitiveOrchestrator.

Bridges the canonical API to the MasterCognitiveOrchestrator so the cognitive
chains (REPAIR / FEATURE_SYNTHESIS / AUDIT_RADAR / EVOLUTION) are reachable
through the same authenticated app that serves the rest of the API — instead
of being an internal-only singleton.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user_token
from core.orchestration.cognitive_pipeline_dispatcher import (
    CognitiveIntent,
    get_master_orchestrator,
)

router = APIRouter(
    prefix="/api/v1/cognitive",
    tags=["cognitive"],
    dependencies=[Depends(get_current_user_token)],
)

_ALLOWED_INTENTS = {intent.value for intent in CognitiveIntent}


class CognitiveDispatchRequest(BaseModel):
    intent: str = Field(..., description="One of: " + ", ".join(sorted(_ALLOWED_INTENTS)))
    payload: dict = Field(default_factory=dict, description="Pipeline input payload")


@router.post("/dispatch")
async def dispatch_cognitive(request: CognitiveDispatchRequest) -> dict:
    """Run a cognitive pipeline and return the honest execution report."""
    try:
        intent = CognitiveIntent(request.intent)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown intent '{request.intent}'. Allowed: {sorted(_ALLOWED_INTENTS)}",
        ) from exc

    orchestrator = get_master_orchestrator()
    result = await orchestrator.dispatch(intent, request.payload)
    return result.to_dict()


@router.get("/intents")
async def list_intents() -> dict:
    """List the intents the Core API can dispatch."""
    return {"intents": sorted(_ALLOWED_INTENTS)}

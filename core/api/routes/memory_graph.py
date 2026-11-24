"""core.api.routes.memory_graph — the user's own memory surface (blueprint pillar 1).

বাংলা: ``core.services.memory_graph`` গ্রাফ ও নিষ্কাশন চালায়; এই রাউটার শুধু
চুক্তি ও টেন্যান্ট-অ্যাট্রিবিউশন। ইউজার নিয়ন্ত্রণ এখানেই:

* ``GET    /api/memory/graph``   — নিজের পুরো গ্রাফ (স্বচ্ছতা: সিস্টেম কী জানে);
* ``POST   /api/memory/graph/absorb`` — এক প্যাসেজ থেকে ফ্যাক্ট নেওয়া
  (চ্যাট/ভয়েস পথেও best-effort হয়, এটা ম্যানুয়াল/সিঙ্ক পথ);
* ``POST   /api/memory/graph/forget`` — এক ফ্যাক্ট ভুলে যাওয়া (নিজের ডেটা,
  নিজের সিদ্ধান্ত);
* ``DELETE /api/memory/graph``   — পুরো গ্রাফ মুছুন (right-to-be-forgotten);
* ``GET    /api/memory/briefing`` — প্রো-অ্যাক্টিভ মর্নিং ব্রিফিং কার্ডের ডেটা।

কিল-সুইচ: ``SUPREMEAI_MEMORY_GRAPH=false`` → সব সাফে সৎ ``enabled: false``
উত্তর (৪০৩ নয়) — টুল-সারফেসের ``enabled: false`` চুক্তির মতোই।
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import get_current_user_token

from core.services.memory_graph import (
    KILL_SWITCH_ENV,
    STORE_DIR_ENV,
    absorb_text,
    forget_fact,
    get_graph,
    memory_enabled,
    morning_briefing,
    wipe_graph,
)

router = APIRouter(prefix="/api/memory", tags=["User-Memory-Graph"])

UserToken = Annotated[dict, Depends(get_current_user_token)]


def _tenant_of(token: dict) -> str:
    return str(token.get("tenant_id") or token.get("sub") or "").strip()


class AbsorbPayload(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    source: Literal["chat", "voice", "manual", "sync"] = "manual"


class ForgetPayload(BaseModel):
    factId: str = Field(min_length=2, max_length=64)


@router.get("/graph")
async def read_graph(token: UserToken) -> dict[str, Any]:
    """Return the caller's full memory graph — total transparency, own data only."""
    tenant = _tenant_of(token)
    graph = get_graph(tenant)
    graph["env"] = {"killSwitch": KILL_SWITCH_ENV, "storeDir": STORE_DIR_ENV}
    return graph


@router.post("/graph/absorb")
async def absorb(payload: AbsorbPayload, token: UserToken) -> dict[str, Any]:
    """Extract facts from one passage into the caller's graph (deterministic, no LLM)."""
    result = absorb_text(_tenant_of(token), payload.text, source=payload.source)
    return result


@router.post("/graph/forget")
async def forget(payload: ForgetPayload, token: UserToken) -> dict[str, Any]:
    """Forget one fact — the user's data, the user's decision."""
    removed = forget_fact(_tenant_of(token), payload.factId)
    return {"removed": removed, "factId": payload.factId}


@router.delete("/graph")
async def wipe(token: UserToken) -> dict[str, Any]:
    """Wipe the caller's entire memory graph (right-to-be-forgotten)."""
    wiped = wipe_graph(_tenant_of(token))
    return {"wiped": wiped, "enabled": memory_enabled()}


@router.get("/briefing")
async def briefing(token: UserToken) -> dict[str, Any]:
    """Proactive morning-briefing card data — only facts that are really known."""
    return morning_briefing(_tenant_of(token))

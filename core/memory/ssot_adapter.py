"""G5.2b — route → `public.memories` SSOT dual-write adapter.

বাংলা মন্তব্য: reaudit-এ তিনটা write path ছিল (ai_memory / learned_facts /
memories SSOT)। এই অ্যাডাপ্টার পুরনো API shape না ভেঙে route-লেকে SSOT-এ
**best-effort dual-write** দেয় (status=candidate, HITL confirm পরে)।

Contracts (mirror of sidecar `save_memory` — infrastructure/.../mcp_server.py):
  * PII stripped before insert (email/phone/card);
  * owner_id must be a UUID — derived deterministically when caller has none
    (same uuid5 namespace as the sidecar so tenant isolation matches);
  * kind ∈ fact|decision|task|preference|contact|doc_chunk;
  * status always ``candidate`` — training never auto-confirms;
  * **fail-open**: any error returns ``{"success": False, ...}`` and never
    raises — the primary (ai_memory / learned_facts) write must not regress.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from core.monitoring.logging_config import logger

_PII_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PII_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
_PII_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)")

_ALLOWED_KINDS = frozenset(
    {"fact", "decision", "task", "preference", "contact", "doc_chunk"}
)

# task_type (legacy ai_memory) → memories.kind
_TASK_TYPE_KIND = {
    "user_memory": "preference",
    "session": "task",
    "session_summary": "task",
    "summarize": "task",
    "decision": "decision",
    "preference": "preference",
    "contact": "contact",
    "note": "doc_chunk",
}


def strip_pii(text: str) -> str:
    """Best-effort PII redaction before SSOT insert (training/PII policy)."""
    out = _PII_EMAIL.sub("[EMAIL]", text)
    out = _PII_PHONE.sub("[PHONE]", out)
    out = _PII_CARD.sub("[CARD]", out)
    return out


def tenant_owner_id(tenant_id: str) -> str:
    """Deterministic per-tenant owner UUID — same formula as the memory sidecar."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"supremeai.memory.owner:{tenant_id}"))


def resolve_owner_id(user_id: str | None, tenant_id: str = "tenant_default") -> str:
    """Prefer a real auth UUID; else derive one (sidecar-compatible)."""
    raw = (user_id or "").strip()
    if raw:
        try:
            uuid.UUID(raw)
            return raw
        except ValueError:
            return tenant_owner_id(raw)
    return tenant_owner_id(tenant_id or "tenant_default")


def map_kind(kind: str | None = None, task_type: str | None = None) -> str:
    if kind and kind in _ALLOWED_KINDS:
        return kind
    if task_type:
        mapped = _TASK_TYPE_KIND.get(task_type.lower())
        if mapped:
            return mapped
    return "fact"


def save_memory_ssot(
    *,
    content: str,
    kind: str | None = None,
    task_type: str | None = None,
    user_id: str | None = None,
    tenant_id: str = "tenant_default",
    source_type: str = "chat",
    source_ref: str | None = None,
    source_quote: str | None = None,
    confidence: float | None = None,
    workspace_id: str | None = None,
    embedding: list[float] | None = None,
    created_by: str = "agent:route",
) -> dict[str, Any]:
    """Insert one row into ``public.memories`` (status=candidate). Fail-open.

    Returns ``{"success": True, "id": ..., "status": "candidate"}`` or
    ``{"success": False, "error": ...}``. Never raises.
    """
    try:
        text_raw = str(content or "").strip()
        if not text_raw:
            return {"success": False, "error": "content is required"}

        resolved_kind = map_kind(kind=kind, task_type=task_type)
        owner_id = resolve_owner_id(user_id, tenant_id)

        ws = (workspace_id or "").strip() or None
        if ws:
            try:
                uuid.UUID(ws)
            except ValueError:
                return {"success": False, "error": "workspace_id must be a UUID"}

        conf: float | None = None
        if confidence is not None:
            try:
                conf = float(confidence)
                if not (0.0 <= conf <= 1.0):
                    conf = None
            except (TypeError, ValueError):
                conf = None

        content = strip_pii(text_raw)
        row: dict[str, Any] = {
            "owner_id": owner_id,
            "workspace_id": ws,
            "kind": resolved_kind,
            "content": content,
            "source_type": str(source_type or "chat"),
            "source_ref": source_ref,
            "source_quote": source_quote,
            "created_by": created_by,
            "status": "candidate",  # HITL — never auto-confirm
            "confidence": conf,
        }
        if embedding:
            row["embedding"] = embedding

        from core.config import settings

        url = getattr(settings, "supabase_url", "") or ""
        key = getattr(settings, "supabase_key", "") or ""
        if not url or not key:
            return {
                "success": False,
                "error": "supabase not configured",
                "status": "candidate_not_saved",
                "owner_id": owner_id,
                "kind": resolved_kind,
            }

        from supabase import create_client

        client = create_client(url, key)
        # supabase-py is sync — caller may wrap with asyncio.to_thread.
        result = client.table("memories").insert(row).execute()
        data = getattr(result, "data", None) or []
        saved = data[0] if data else {}
        return {
            "success": True,
            "id": saved.get("id"),
            "status": saved.get("status", "candidate"),
            "owner_id": owner_id,
            "kind": resolved_kind,
            "pii_stripped": content != text_raw,
        }
    except Exception as exc:  # noqa: BLE001 — dual-write must never break primary
        logger.warning(f"ssot_adapter.save_memory_ssot failed (fail-open): {exc}")
        return {"success": False, "error": str(exc)}


def dual_write_route_memory(
    *,
    summary: str,
    task_type: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    embedding: list[float] | None = None,
) -> dict[str, Any]:
    """Convenience wrapper for memory routes (ai_memory writers)."""
    return save_memory_ssot(
        content=summary,
        task_type=task_type,
        user_id=user_id,
        source_type="chat",
        source_ref=session_id,
        source_quote=None,
        confidence=None,
        embedding=embedding,
        created_by="agent:route",
    )


def dual_write_learned_fact(
    fact: dict[str, Any],
    *,
    content_text: str | None = None,
) -> dict[str, Any]:
    """Best-effort SSOT mirror of a learned_facts write."""
    text = content_text
    if text is None:
        text = str(
            fact.get("content")
            or fact.get("text")
            or fact.get("fact")
            or ""
        ).strip()
    tags = fact.get("tags") or []
    kind = "fact"
    if isinstance(tags, list) and tags:
        tag0 = str(tags[0]).lower()
        if tag0 in _ALLOWED_KINDS:
            kind = tag0
    return save_memory_ssot(
        content=text,
        kind=kind,
        user_id=fact.get("user_id") or fact.get("owner_id"),
        tenant_id=str(fact.get("tenant_id") or "tenant_default"),
        source_type="mcp",
        source_ref=str(fact.get("id") or "") or None,
        confidence=fact.get("confidence"),
        created_by="agent:learned_fact",
    )

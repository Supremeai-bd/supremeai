"""Admin API for the agent-constitution update queue (owner dashboard → rules.yml).

বাংলা: admin dashboard থেকে rules/AGENTS.md update প্রস্তাব জমা ও পরিচালনার endpoint।
Flow: admin POSTs a proposal → row lands in Supabase ``agent_rule_updates``
(status=proposed, deduped by content hash) → the scheduled
``apply-agent-rule-proposals`` job renders it into rules.yml and opens an
auto-PR → admin marks the proposal applied/rejected from the dashboard.
Admin-auth is enforced by ``get_current_admin`` on every endpoint.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_admin

router = APIRouter(prefix="/admin-api/agent-rules", tags=["agent-rules"])

REPO_ROOT = Path(__file__).resolve().parents[3]
RULES_PATH = REPO_ROOT / ".github" / "constitution" / "rules.yml"
OWNER_QUEUE_ISSUE = 966
VALID_STATUSES = ("proposed", "applied", "rejected")
TABLE = "agent_rule_updates"


class RuleProposalRequest(BaseModel):
    """A new constitution-rule update proposal from the dashboard."""

    rule_key: str = Field(..., pattern=r"^[a-z0-9_]{3,60}$", description="rules.yml key (snake_case)")
    title: str = Field(..., min_length=3, max_length=200)
    rule_text: str = Field(..., min_length=10, max_length=4000)


class ProposalStatusRequest(BaseModel):
    """Admin-only status flip for a proposal (the 'admin done' edit)."""

    status: str = Field(..., pattern=r"^(applied|rejected)$")
    applied_pr: int | None = Field(None, ge=1)


def _supabase_conf() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not url.startswith("https://") or not key:
        raise HTTPException(status_code=503, detail="Supabase configuration unavailable")
    return url, key


def _rest_request(url: str, key: str, method: str, path: str, payload: dict | None = None) -> list[dict]:
    req = urllib.request.Request(
        f"{url}/rest/v1/{path}",
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body.strip() else []
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise HTTPException(status_code=502, detail=f"Supabase error ({exc.code}): {detail}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Supabase unreachable: {type(exc).__name__}") from exc


def _rules_version() -> str | None:
    try:
        import yaml

        data = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}
        return str((data.get("constitution") or {}).get("rules_version") or "") or None
    except Exception:
        return None


@router.get("/summary")
async def rules_summary_endpoint(_admin: Any = Depends(get_current_admin)) -> dict[str, Any]:
    """Dashboard landing state: SSOT version, queue issue, proposal counts."""
    url, key = _supabase_conf()
    rows = _rest_request(url, key, "GET", f"{TABLE}?select=status&order=created_at.desc&limit=500")
    counts: dict[str, int] = {status: 0 for status in VALID_STATUSES}
    for row in rows:
        status = str(row.get("status") or "")
        if status in counts:
            counts[status] += 1
    return {
        "ssot": ".github/constitution/rules.yml",
        "rules_version": _rules_version(),
        "generated": "AGENTS.md (via scripts/ci/generate_agents_md.py; CI drift gate enforces sync)",
        "public_sync": "unified-pipeline → sync_to_public_repo.py auto-PRs AGENTS.md to supremeai-public",
        "owner_action_queue_issue": OWNER_QUEUE_ISSUE,
        "proposals": counts,
    }


@router.get("/proposals")
async def list_proposals_endpoint(
    status: str | None = None,
    _admin: Any = Depends(get_current_admin),
) -> list[dict[str, Any]]:
    """List rule-update proposals (optional status filter: proposed|applied|rejected)."""
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {VALID_STATUSES}")
    url, key = _supabase_conf()
    query = f"{TABLE}?select=proposal_id,rule_key,title,rule_text,status,applied_pr,created_by,created_at&order=created_at.desc&limit=200"
    if status:
        query += f"&status=eq.{status}"
    return _rest_request(url, key, "GET", query)


@router.post("/proposals")
async def create_proposal_endpoint(
    request: RuleProposalRequest,
    admin: Any = Depends(get_current_admin),
) -> dict[str, Any]:
    """Queue a rules.yml update. Duplicate proposed content is rejected (no dupes)."""
    url, key = _supabase_conf()
    content_sha = hashlib.sha256(f"{request.rule_key}:{request.rule_text}".encode()).hexdigest()
    existing = _rest_request(
        url, key, "GET", f"{TABLE}?content_sha256=eq.{content_sha}&status=eq.proposed&select=proposal_id&limit=1"
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"identical proposal already pending: {existing[0]['proposal_id']}")
    created = _rest_request(
        url,
        key,
        "POST",
        TABLE,
        {
            "rule_key": request.rule_key,
            "title": request.title,
            "rule_text": request.rule_text,
            "content_sha256": content_sha,
            "created_by": f"admin-dashboard:{getattr(admin, 'sub', None) or 'admin'}",
        },
    )
    row = created[0] if created else {}
    return {"status": "queued", "proposal_id": row.get("proposal_id"), "content_sha256": content_sha[:12]}


@router.post("/proposals/{proposal_id}/status")
async def set_proposal_status_endpoint(
    proposal_id: str,
    request: ProposalStatusRequest,
    _admin: Any = Depends(get_current_admin),
) -> dict[str, Any]:
    """Admin-only flip: applied (after the auto-PR merged) or rejected."""
    url, key = _supabase_conf()
    patch: dict[str, Any] = {"status": request.status, "updated_at": "now()"}
    if request.applied_pr:
        patch["applied_pr"] = request.applied_pr
    updated = _rest_request(url, key, "PATCH", f"{TABLE}?proposal_id=eq.{proposal_id}", patch)
    if not updated:
        raise HTTPException(status_code=404, detail=f"proposal {proposal_id} not found")
    row = updated[0] if isinstance(updated, list) else updated
    return {"status": "ok", "proposal_id": proposal_id, "new_status": row.get("status")}

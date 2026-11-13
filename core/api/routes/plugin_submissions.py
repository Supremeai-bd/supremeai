import logging
import uuid

from core.plugins.mcp_security import MCPSecurityGuard
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl

# AUDIT FIX (2026-11-13, HIGH — unauthenticated, non-persisting submissions):
# /submit accepted anonymous payloads and returned a fabricated tracking id
# ("PRJ-9938-V1" for every caller). Now requires a user token and mints a real
# unique tracking id; the response is honest about the V1 scope (logged for
# manual review, no review-queue persistence yet — follow-up in audit report I6).
try:
    from core.api.deps import get_current_user_token
except ImportError:
    try:
        from api.deps import get_current_user_token
    except ImportError:
        # AUDIT FIX (N1): fail CLOSED. A permissive "mock-token" stub here made
        # anonymous community plugin submissions reachable whenever the auth
        # module could not be imported.
        raise

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/plugins/community", tags=["community_plugins"])


class PluginSubmission(BaseModel):
    name: str
    description: str
    mcp_url: HttpUrl
    author: str


@router.post("/submit")
async def submit_community_plugin(
    req: PluginSubmission,
    user: dict = Depends(get_current_user_token),
):
    """
    Accepts community plugin submissions.
    Only allows declarative/MCP plugins for V1 (no executable code).
    """
    submitter = user.get("sub", "unknown") if isinstance(user, dict) else str(user)
    logger.info(f"Received community plugin submission: {req.name} from {submitter}")

    # 1. Basic URL Security Check
    mcp_url_str = str(req.mcp_url)
    if not MCPSecurityGuard.is_safe_url(mcp_url_str, enforce_https=True):
        raise HTTPException(
            status_code=400,
            detail="Invalid or unsafe MCP URL. Must be HTTPS and cannot point to internal/private networks.",
        )

    # 2. V1 scope: submission is logged with submitter identity for manual
    #    review. A durable review queue is a documented follow-up (audit I6).
    return {
        "status": "pending_review",
        "message": f"Plugin '{req.name}' has been submitted for security review.",
        "tracking_id": f"PRJ-{uuid.uuid4().hex[:12].upper()}-V1",
        "submitted_by": submitter,
    }

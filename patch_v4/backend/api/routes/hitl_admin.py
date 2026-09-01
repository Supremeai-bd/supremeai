from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.dependencies import get_current_admin
from api.deps import get_tenant_db  # PATCH v4: get_tenant_db lives in api.deps, NOT core.tenant_db
from database.tenant_db import TenantAwareFirestore  # PATCH v4: direct import (skip deprecation shim)
from services.hitl.engine import HITLEngine

router = APIRouter()


class RejectionRequest(BaseModel):
    reason: str


@router.get("/pending", dependencies=[Depends(get_current_admin)])
async def get_pending_approvals(db: TenantAwareFirestore = Depends(get_tenant_db)):
    """
    Get all pending actions requiring human approval.
    """
    engine = HITLEngine(db=db)
    return engine.get_pending_approvals()


@router.post("/approve/{record_id}", dependencies=[Depends(get_current_admin)])
async def approve_pending_action(
    record_id: str,
    current_admin: dict = Depends(get_current_admin),
    db: TenantAwareFirestore = Depends(get_tenant_db),
):
    """
    Approve a pending action.
    """
    engine = HITLEngine(db=db)
    try:
        record = engine.approve(
            admin_user_id=current_admin.get("user_id", "admin"), record_id=record_id
        )

        return {"status": "success", "message": f"Record {record_id} approved.", "record": record}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/reject/{record_id}", dependencies=[Depends(get_current_admin)])
async def reject_pending_action(
    record_id: str,
    payload: RejectionRequest,
    current_admin: dict = Depends(get_current_admin),
    db: TenantAwareFirestore = Depends(get_tenant_db),
):
    """
    Reject a pending action.
    """
    engine = HITLEngine(db=db)
    try:
        record = engine.reject(
            admin_user_id=current_admin.get("user_id", "admin"),
            record_id=record_id,
            reason=payload.reason,
        )
        return {"status": "success", "message": f"Record {record_id} rejected.", "record": record}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

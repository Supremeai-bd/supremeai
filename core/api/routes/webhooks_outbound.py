"""Deprecation response for Core's unsupported outbound webhook delivery.

Do not store shared subscriptions or send test requests here. The Gateway's
separate compatibility API manages owner-scoped metadata, not delivery.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_current_user_token

router = APIRouter(dependencies=[Depends(get_current_user_token)], include_in_schema=False)


@router.get("/api/user/webhooks")
@router.post("/api/user/webhooks")
@router.delete("/api/user/webhooks/{webhook_id}")
@router.post("/api/user/webhooks/{webhook_id}/test")
async def outbound_webhooks_unavailable() -> None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Outbound webhook subscriptions and delivery are unavailable on Core.",
    )

"""Canonical browser automation endpoints (owner-scoped).

Split out of the former single-module api/routes/browser.py verbatim:
saved-session catalog CRUD, isolated automation session lifecycle and the
generic per-session action executor. Routes register on the shared
``router`` in the original file order (see package ``__init__.py``).
"""

from typing import Any, Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from core.api.deps import get_current_user_token
from core.api.routes.browser import router
from core.browser_session_catalog import SavedBrowserSession, browser_session_catalog
from core.browser_session_manager import session_manager


class AutomationSessionRequest(BaseModel):
    """Create an isolated session; credentials are entered by the user in-browser."""

    label: str = Field(default="Browser session", min_length=1, max_length=120)
    saved_url: str | None = Field(default=None, max_length=2048)


class SavedSessionRequest(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2048)
    session_id: str | None = Field(default=None, max_length=128)


class BrowserActionRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    action: Literal[
        "navigate", "click", "fill", "type", "screenshot", "content", "extract",
        "back", "forward", "reload",
    ]
    url: str | None = Field(default=None, max_length=2048)
    selector: str | None = Field(default=None, min_length=1, max_length=512)
    value: str | None = Field(default=None, max_length=20_000)
    full_page: bool = False


class BrowserSessionResponse(BaseModel):
    session_id: str
    status: str
    url: str


@router.get("/automation/saved-sessions")
async def list_saved_sessions(user: dict = Depends(get_current_user_token)):
    owner_id = str(user.get("sub") or "")
    tenant_id = str(user.get("tenant_id") or "")
    if not owner_id or not tenant_id:
        raise HTTPException(status_code=401, detail="Authenticated tenant claim required")
    return {
        "sessions": [item.__dict__ for item in browser_session_catalog.list(tenant_id, owner_id)]
    }


@router.post("/automation/saved-sessions")
async def save_session(payload: SavedSessionRequest, user: dict = Depends(get_current_user_token)):
    from core.security import is_safe_url

    owner_id = str(user.get("sub") or "")
    tenant_id = str(user.get("tenant_id") or "")
    if not owner_id or not tenant_id:
        raise HTTPException(status_code=401, detail="Authenticated tenant claim required")
    if not owner_id or not tenant_id or not is_safe_url(payload.url):
        raise HTTPException(
            status_code=400, detail="Valid authenticated owner and safe URL are required"
        )
    item = browser_session_catalog.save(
        SavedBrowserSession(
            tenant_id=tenant_id,
            owner_id=owner_id,
            label=payload.label,
            url=payload.url,
            session_id=payload.session_id,
        )
    )
    return {"session": item.__dict__}


@router.delete("/automation/saved-sessions/{saved_session_id}")
async def revoke_saved_session(saved_session_id: str, user: dict = Depends(get_current_user_token)):
    owner_id = str(user.get("sub") or "")
    tenant_id = str(user.get("tenant_id") or "")
    if not owner_id or not tenant_id:
        raise HTTPException(status_code=401, detail="Authenticated tenant claim required")
    if not browser_session_catalog.revoke(saved_session_id, tenant_id, owner_id):
        raise HTTPException(status_code=404, detail="Saved browser session not found")
    return {"success": True}


def _owner_id(user: dict) -> str:
    """Canonical owner key for a browser session (audit item ⑥/AUTOMATION-OWNER).

    ``get_current_user_token`` returns a **dict** (``{"sub", "tenant_id", ...}``),
    but the automation session routes used to receive it in a parameter typed
    ``user_token: str`` and hand the whole dict to the session pool as
    ``owner_id``. Three real consequences, all fixed here by deriving the owner
    exactly like every other browser route does:

    1. ``pause_owner(...)`` stored the dict in a ``set`` → ``TypeError:
       unhashable type: 'dict'`` the moment an operator paused automation.
    2. ``/automation/pause`` keyed on ``user["sub"]`` while sessions were keyed
       on the dict object, so "pause" never gated an automation session — a
       paused owner could keep clicking.
    3. Session records (and the metrics snapshot) carried token payloads instead
       of an owner id.

    Fail closed: no subject claim → 401, never an anonymous shared pool.
    """
    owner_id = str(user.get("sub") or "").strip()
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authenticated owner required")
    return owner_id


@router.post("/automation/sessions", response_model=BrowserSessionResponse)
async def create_automation_session(
    req: AutomationSessionRequest,
    user: dict = Depends(get_current_user_token),
):
    from core.security import is_safe_url

    owner_id = _owner_id(user)
    if req.saved_url and not is_safe_url(req.saved_url):
        raise HTTPException(status_code=400, detail="Unsafe or invalid saved URL")
    try:
        session = await session_manager.create(
            owner_id, label=req.label, saved_url=req.saved_url
        )
    except PermissionError as exc:  # owner paused automation
        raise HTTPException(status_code=423, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — no browser → honest 503, not a fake 200
        raise HTTPException(
            status_code=503, detail=f"Browser session could not be started: {exc}"
        ) from exc
    return BrowserSessionResponse(session_id=session.id, status="ready", url=session.page.url)


@router.get("/automation/sessions")
async def list_automation_sessions(user: dict = Depends(get_current_user_token)):
    owner_id = _owner_id(user)
    return {"sessions": [s for s in session_manager.snapshot() if s["owner_id"] == owner_id]}


@router.delete("/automation/sessions/{session_id}")
async def close_automation_session(
    session_id: str, user: dict = Depends(get_current_user_token)
):
    if not await session_manager.close(session_id, _owner_id(user)):
        raise HTTPException(status_code=404, detail="Browser session not found")
    return {"success": True}


@router.post("/automation/actions")
async def execute_automation_action(
    req: BrowserActionRequest, user: dict = Depends(get_current_user_token)
):
    from core.security import is_safe_url

    async def _await_actionable(locator, action: str) -> None:
        """ERR-A06 FIX (2026-09-16): explicitly wait for the element to be
        visible before click/fill/type. On dynamic SPAs the node can match
        while still not actionable (mid re-render, animating, detached by a
        framework patch), which used to surface as raw 15s TimeoutErrors.
        A wait that still times out becomes an honest HTTP 408 with the
        verbatim reason instead of an opaque failure."""
        try:
            await locator.wait_for(state="visible", timeout=15_000)
        except Exception as exc:  # noqa: BLE001 — playwright TimeoutError et al.
            raise HTTPException(
                status_code=408,
                detail=f"Element {req.selector!r} not actionable for {action!r} within 15s: {exc}",
            ) from exc

    owner_id = _owner_id(user)
    try:
        session = await session_manager.get(req.session_id, owner_id)
    except PermissionError as exc:  # owner paused automation
        raise HTTPException(status_code=423, detail=str(exc)) from exc
    except KeyError as exc:
        # Unknown / expired / someone-else's session id is a 404, not a 500.
        raise HTTPException(status_code=404, detail=str(exc).strip("'\"")) from exc
    page = session.page
    action = req.action.lower()

    async def _page_title() -> str:
        """Best-effort page title for real-browser UI chrome (never fatal)."""
        try:
            return await page.title()
        except Exception:  # noqa: BLE001 — title is metadata, never fail the action
            return ""
    if action not in session.allowed_actions:
        raise HTTPException(status_code=403, detail="Action is not allowed for this session")
    if action == "navigate":
        if not req.url or not is_safe_url(req.url):
            raise HTTPException(status_code=400, detail="Unsafe or invalid URL")
        await page.goto(req.url, wait_until="domcontentloaded", timeout=30_000)
    elif action == "click":
        if not req.selector:
            raise HTTPException(status_code=422, detail="selector is required")
        locator = page.locator(req.selector)
        await _await_actionable(locator, "click")
        await locator.click(timeout=15_000)
    elif action in {"fill", "type"}:
        if not req.selector or req.value is None:
            raise HTTPException(status_code=422, detail="selector and value are required")
        locator = page.locator(req.selector)
        await _await_actionable(locator, action)
        await locator.fill(req.value, timeout=15_000)
    elif action == "back":
        if not await page.go_back(timeout=30_000):
            raise HTTPException(status_code=409, detail="No previous page in this session's history")
    elif action == "forward":
        if not await page.go_forward(timeout=30_000):
            raise HTTPException(status_code=409, detail="No next page in this session's history")
    elif action == "reload":
        await page.reload(wait_until="domcontentloaded", timeout=30_000)
    elif action == "screenshot":
        image = await page.screenshot(type="png", full_page=req.full_page)
        import base64

        return {
            "success": True,
            "action": action,
            "url": page.url,
            "screenshot": base64.b64encode(image).decode("ascii"),
            "title": await _page_title(),
        }
    elif action in {"content", "extract"}:
        return {
            "success": True,
            "action": action,
            "url": page.url,
            "content": await page.locator("body").inner_text(timeout=15_000),
            "title": await _page_title(),
        }
    else:
        raise HTTPException(status_code=422, detail="Unsupported browser action")
    return {
        "success": True,
        "action": action,
        "url": page.url,
        "title": await _page_title(),
    }


@router.post("/automation/pause")
async def pause_automation(user: dict = Depends(get_current_user_token)):
    owner_id = str(user.get("sub") or "")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authenticated owner required")
    session_manager.pause_owner(owner_id)
    return {"status": "paused"}


@router.post("/automation/resume")
async def resume_automation(user: dict = Depends(get_current_user_token)):
    owner_id = str(user.get("sub") or "")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authenticated owner required")
    session_manager.resume_owner(owner_id)
    return {"status": "active"}


class VaultSyncRequest(BaseModel):
    service: str = Field(min_length=1, max_length=120)
    cookies: list[dict[str, Any]] = Field(default_factory=list)
    local_storage: dict[str, Any] = Field(default_factory=dict)
    label: str | None = None


class ScheduledExecutionRequest(BaseModel):
    service: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2048)
    actions: list[dict[str, Any]] = Field(default_factory=list)


def _get_owner_vault(owner_id: str):
    import os
    import re
    from pathlib import Path

    from core.browser_session_vault import BrowserSessionVault

    clean_owner = re.sub(r"[^a-zA-Z0-9_\-]", "_", owner_id or "default")
    vault_base = Path(os.getenv("VAULT_DIR", "data/browser_vaults"))
    owner_path = vault_base / clean_owner
    owner_path.mkdir(parents=True, exist_ok=True)
    return BrowserSessionVault(owner_path)


@router.post("/automation/vault/sync")
async def sync_vault_session(
    payload: VaultSyncRequest,
    user: dict = Depends(get_current_user_token),
):
    owner_id = str(user.get("sub") or "")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authenticated owner required")
    from core.browser_session_vault import SessionVaultError

    try:
        vault = _get_owner_vault(owner_id)
        vault.save_session(payload.service, payload.cookies, payload.local_storage)
        return {
            "status": "success",
            "service": payload.service,
            "cookies_count": len(payload.cookies),
            "valid": True,
        }
    except SessionVaultError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/automation/vault/services")
async def list_vault_services(user: dict = Depends(get_current_user_token)):
    owner_id = str(user.get("sub") or "")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authenticated owner required")
    try:
        vault = _get_owner_vault(owner_id)
        return {"services": vault.list_services()}
    except Exception as exc:
        return {"services": [], "error": str(exc)}


@router.delete("/automation/vault/services/{service}")
async def delete_vault_service(service: str, user: dict = Depends(get_current_user_token)):
    owner_id = str(user.get("sub") or "")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authenticated owner required")
    try:
        vault = _get_owner_vault(owner_id)
        forgotten = vault.forget(service)
        if not forgotten:
            raise HTTPException(status_code=404, detail=f"Service '{service}' not found in vault")
        return {"status": "success", "service": service}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/automation/vault/execute")
async def execute_scheduled_task(
    payload: ScheduledExecutionRequest,
    user: dict = Depends(get_current_user_token),
):
    owner_id = str(user.get("sub") or "")
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authenticated owner required")
    from core.security import is_safe_url
    if not is_safe_url(payload.url):
        raise HTTPException(status_code=400, detail="Unsafe URL requested")

    vault = _get_owner_vault(owner_id)
    storage_state = None
    if vault.is_session_valid(payload.service):
        try:
            storage_state = vault.load_state(payload.service)
        except Exception as load_err:
            from core.monitoring.logging_config import logger
            logger.warning(f"Failed to load storage_state for {payload.service}: {load_err}")

    # Launch isolated session with injected storage_state
    session = await session_manager.create(
        owner_id=owner_id,
        label=f"Scheduled: {payload.service}",
        saved_url=payload.url,
        storage_state=storage_state,
    )

    results: list[dict[str, Any]] = []
    try:
        await session.page.goto(payload.url, wait_until="domcontentloaded", timeout=30_000)
        results.append({"action": "navigate", "url": session.page.url, "success": True})

        for act in payload.actions:
            action_name = act.get("action", "")
            if action_name in {"content", "extract"}:
                text = await session.page.locator("body").inner_text(timeout=15_000)
                results.append({"action": action_name, "content": text[:5000], "success": True})
            elif action_name == "click" and act.get("selector"):
                await session.page.locator(act["selector"]).click(timeout=15_000)
                results.append({"action": "click", "selector": act["selector"], "success": True})
            elif action_name == "screenshot":
                img = await session.page.screenshot(type="png")
                import base64
                results.append({"action": "screenshot", "image": base64.b64encode(img).decode("ascii")})

        page_title = await session.page.title()
        return {
            "status": "success",
            "service": payload.service,
            "title": page_title,
            "final_url": session.page.url,
            "results": results,
            "session_authenticated": storage_state is not None,
        }
    finally:
        await session_manager.close(session.id, owner_id)


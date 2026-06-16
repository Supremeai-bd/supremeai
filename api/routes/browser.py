from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
import base64

from core.audit_logger import AuditLogger
from core.secure_credential_store import SecureCredentialStore

audit = AuditLogger()
credential_store = SecureCredentialStore()

router = APIRouter(prefix="/api/browser", tags=["browser"])
BROWSER_STATUS = {"browsing": False, "currentUrl": "about:blank"}
RECENT_ACTIVITIES = []
CREDENTIALS = []
PAUSED_STATE = {"paused": False}
URL_PERMISSIONS = []
PERMISSION_REQUESTS = []
SYSTEM_LEARNING = {"enabled": True}
TASKS = {}
FINDINGS = []

class GoalRequest(BaseModel):
    goal: str

class NavigateRequest(BaseModel):
    url: str

class ClickRequest(BaseModel):
    selector: str

class FillRequest(BaseModel):
    selector: str
    value: str

class ClickAtRequest(BaseModel):
    x: int
    y: int

class KeyRequest(BaseModel):
    key: str

class CredentialRequest(BaseModel):
    serviceName: str
    username: str
    password: str
    userId: Optional[str] = "default"

class UrlPermissionRequest(BaseModel):
    urlPattern: str
    userId: Optional[str] = "default"
    reason: Optional[str] = "None"

class DecisionRequest(BaseModel):
    approved: bool

@router.get("/surf/status")
def get_status():
    return BROWSER_STATUS

@router.post("/surf/start")
def start_surf():
    BROWSER_STATUS["browsing"] = True
    return {"status": "started"}

@router.post("/surf/stop")
def stop_surf():
    BROWSER_STATUS["browsing"] = False
    return {"status": "stopped"}

@router.get("/activity/recent")
def get_recent_activity():
    return {"activities": RECENT_ACTIVITIES}

@router.get("/credentials")
def get_credentials(userId: str = "default"):
    user_creds = []
    for c in CREDENTIALS:
        if c.get("userId") == userId:
            decrypted = credential_store.decrypt(c)
            user_creds.append(credential_store.mask(decrypted))
    return {"credentials": user_creds}

@router.post("/credentials")
def save_credential(cred: CredentialRequest):
    new_cred = credential_store.encrypt(cred.model_dump())
    new_cred["id"] = f"cred_{len(CREDENTIALS) + 1}"
    CREDENTIALS.append(new_cred)
    audit.log_decision(
        action_type="browser_credential_saved",
        decision_details=f"Stored credential for service '{cred.serviceName}'",
        reasoning=f"User '{cred.userId}' saved browser credential.",
    )
    return {"id": new_cred["id"], "serviceName": cred.serviceName}

@router.delete("/credentials/{id}")
def delete_credential(id: str):
    global CREDENTIALS
    CREDENTIALS = [c for c in CREDENTIALS if c.get("id") != id]
    return {"success": True}

@router.post("/surf/resume")
def resume_surf(body: Dict[str, str]):
    PAUSED_STATE["paused"] = False
    return {"status": "resumed"}

@router.post("/surf/skip-auth")
def skip_auth(body: Dict[str, str]):
    PAUSED_STATE["paused"] = False
    return {"status": "auth_skipped"}

@router.post("/surf/pause-manual")
def pause_manual(body: Dict[str, str]):
    PAUSED_STATE["paused"] = True
    return {"status": "paused_for_manual"}

@router.get("/surf/paused-state")
def get_paused_state():
    return PAUSED_STATE

@router.get("/urls/allowed")
def get_allowed_urls(userId: str = "default"):
    allowed = [u for u in URL_PERMISSIONS if u.get("type") == "allowed" and u.get("userId") == userId]
    return {"urls": allowed}

@router.get("/urls/denied")
def get_denied_urls(userId: str = "default"):
    denied = [u for u in URL_PERMISSIONS if u.get("type") == "denied" and u.get("userId") == userId]
    return {"urls": denied}

@router.post("/urls/allowed")
def add_allowed_url(req: UrlPermissionRequest):
    perm = req.model_dump()
    perm["id"] = f"perm_{len(URL_PERMISSIONS) + 1}"
    perm["type"] = "allowed"
    URL_PERMISSIONS.append(perm)
    return perm

@router.post("/urls/denied")
def add_denied_url(req: UrlPermissionRequest):
    perm = req.model_dump()
    perm["id"] = f"perm_{len(URL_PERMISSIONS) + 1}"
    perm["type"] = "denied"
    URL_PERMISSIONS.append(perm)
    return perm

@router.post("/urls/allowAll")
def allow_all_urls(userId: str = "default"):
    perm = {
        "id": f"perm_{len(URL_PERMISSIONS) + 1}",
        "urlPattern": "*",
        "userId": userId,
        "type": "allowAll",
        "reason": "Allow all URLs"
    }
    URL_PERMISSIONS.append(perm)
    return perm

@router.delete("/urls/{id}")
def delete_url(id: str):
    global URL_PERMISSIONS
    URL_PERMISSIONS = [u for u in URL_PERMISSIONS if u.get("id") != id]
    return {"success": True}

@router.get("/urls/requests")
def get_requests():
    return {"requests": PERMISSION_REQUESTS}

@router.post("/urls/requests/{id}/decision")
def decision(id: str, req: DecisionRequest):
    for r in PERMISSION_REQUESTS:
        if r["id"] == id:
            r["status"] = "APPROVED" if req.approved else "DENIED"
            return {"success": True}
    raise HTTPException(status_code=404, detail="Request not found")

@router.get("/system-learning")
def get_system_learning():
    return SYSTEM_LEARNING

@router.post("/system-learning/toggle")
def toggle_learning(body: Dict[str, bool]):
    SYSTEM_LEARNING["enabled"] = body.get("enabled", True)
    return {"success": True}

@router.get("/tasks")
def get_tasks():
    return {"tasks": list(TASKS.values())}

@router.post("/tasks")
def create_task(req: GoalRequest):
    task_id = f"task_{len(TASKS) + 1}"
    task = {
        "id": task_id,
        "goal": req.goal,
        "status": "ACTIVE",
        "createdAt": datetime.utcnow().isoformat()
    }
    TASKS[task_id] = task
    return task

@router.delete("/tasks/{id}")
def delete_task(id: str):
    if id in TASKS:
        del TASKS[id]
        return {"success": True}
    raise HTTPException(status_code=404, detail="Task not found")

@router.get("/tasks/{id}/findings")
def get_findings(id: str):
    task_findings = [f for f in FINDINGS if f.get("taskId") == id]
    return {"findings": task_findings}

@router.post("/findings")
def add_finding(finding: Dict[str, Any]):
    FINDINGS.append(finding)
    return finding

@router.get("/surf/screenshot")
def get_screenshot():
    # Return a mock transparent 1x1 PNG or read browser screenshot if initialized
    mock_png = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    return {"screenshot": mock_png}

@router.post("/surf/navigate")
def navigate(req: NavigateRequest):
    BROWSER_STATUS["currentUrl"] = req.url
    RECENT_ACTIVITIES.append({
        "url": req.url,
        "action": "navigate",
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"success": True}

@router.post("/surf/click")
def click(req: ClickRequest):
    RECENT_ACTIVITIES.append({
        "url": BROWSER_STATUS["currentUrl"],
        "action": f"click {req.selector}",
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"success": True}

@router.post("/surf/fill")
def fill(req: FillRequest):
    RECENT_ACTIVITIES.append({
        "url": BROWSER_STATUS["currentUrl"],
        "action": f"fill {req.selector} with {req.value}",
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"success": True}

@router.post("/surf/click-at")
def click_at(req: ClickAtRequest):
    RECENT_ACTIVITIES.append({
        "url": BROWSER_STATUS["currentUrl"],
        "action": f"click at {req.x}, {req.y}",
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"success": True}

@router.post("/surf/type-key")
def type_key(req: KeyRequest):
    RECENT_ACTIVITIES.append({
        "url": BROWSER_STATUS["currentUrl"],
        "action": f"type key {req.key}",
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"success": True}

@router.get("/surf/accessibility")
def get_accessibility_tree():
    return {
        "role": "WebArea",
        "name": "SupremeAI Console",
        "children": []
    }

@router.post("/simulate-activity")
def simulate_activity(body: Dict[str, str]):
    activity = {
        "url": body.get("url", "http://example.com"),
        "action": body.get("action", "surf"),
        "title": body.get("title", "Page Title"),
        "reasoning": body.get("reasoning", "Exploring content"),
        "timestamp": datetime.utcnow().isoformat()
    }
    RECENT_ACTIVITIES.append(activity)
    return activity

@router.post("/tasks/{id}/step")
def execute_step(id: str):
    if id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    # Simulate a step execution
    return {"success": True, "action": "navigated to dashboard", "details": "Autonomous step succeeded"}

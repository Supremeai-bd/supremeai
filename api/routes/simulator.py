from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime

router = APIRouter(prefix="/api/simulator", tags=["simulator"])

# Mock database / state store
PROFILES = {}
SESSIONS = {}

# Default device profiles
DEVICE_PROFILES = [
    {
        "type": "PIXEL_6",
        "name": "Google Pixel 6",
        "osVersion": "Android 12",
        "screenResolution": "1080x2400",
        "densityDpi": 411
    },
    {
        "type": "IPHONE_13",
        "name": "Apple iPhone 13",
        "osVersion": "iOS 15",
        "screenResolution": "1170x2532",
        "densityDpi": 460
    }
]

class DeviceUpdateRequest(BaseModel):
    type: str
    osVersion: Optional[str] = None
    screenResolution: Optional[str] = None
    densityDpi: Optional[int] = None

class ProfileUpdateRequest(BaseModel):
    installQuota: Optional[int] = None
    device: Optional[DeviceUpdateRequest] = None

class InstallRequest(BaseModel):
    appId: str
    deviceProfile: Optional[str] = "PIXEL_6"

def get_or_create_profile(user_id: str) -> Dict[str, Any]:
    if user_id not in PROFILES:
        PROFILES[user_id] = {
            "userId": user_id,
            "installQuota": 5,
            "activeInstalls": 0,
            "device": DEVICE_PROFILES[0],
            "installedApps": []
        }
    return PROFILES[user_id]

@router.get("/profile")
def get_profile(userId: str = "default"):
    return get_or_create_profile(userId)

@router.post("/profile")
def update_profile(updates: ProfileUpdateRequest, userId: str = "default"):
    profile = get_or_create_profile(userId)
    if updates.installQuota is not None:
        profile["installQuota"] = updates.installQuota
    if updates.device is not None:
        device_update = updates.device.model_dump(exclude_unset=True)
        profile["device"].update(device_update)
    return profile

@router.post("/install")
def install_app(req: InstallRequest, userId: str = "default"):
    profile = get_or_create_profile(userId)
    
    if profile["activeInstalls"] >= profile["installQuota"]:
        raise HTTPException(status_code=400, detail="Install quota exceeded")
        
    # Check if already installed
    existing = next((app for app in profile["installedApps"] if app["appId"] == req.appId), None)
    if existing:
        return {
            "success": True,
            "app": existing,
            "quota": {"used": profile["activeInstalls"], "total": profile["installQuota"]}
        }
        
    app = {
        "appId": req.appId,
        "appName": f"App {req.appId}",
        "version": "1.0.0",
        "previewUrl": f"http://localhost:8000/preview/{req.appId}",
        "installedAt": datetime.utcnow().isoformat(),
        "launchCount": 0,
        "lastLaunchedAt": None,
        "status": "INSTALLED"
    }
    
    profile["installedApps"].append(app)
    profile["activeInstalls"] += 1
    
    return {
        "success": True,
        "app": app,
        "quota": {"used": profile["activeInstalls"], "total": profile["installQuota"]}
    }

@router.delete("/install/{appId}")
def uninstall_app(appId: str, userId: str = "default"):
    profile = get_or_create_profile(userId)
    initial_len = len(profile["installedApps"])
    profile["installedApps"] = [app for app in profile["installedApps"] if app["appId"] != appId]
    
    if len(profile["installedApps"]) < initial_len:
        profile["activeInstalls"] -= 1
        
    return {"success": True}

@router.get("/installed")
def get_installed_apps(userId: str = "default"):
    profile = get_or_create_profile(userId)
    return {
        "installedApps": profile["installedApps"],
        "quota": {
            "used": profile["activeInstalls"],
            "total": profile["installQuota"]
        }
    }

@router.post("/session/start")
def start_session(appId: str, userId: str = "default"):
    profile = get_or_create_profile(userId)
    app = next((a for a in profile["installedApps"] if a["appId"] == appId), None)
    if not app:
        raise HTTPException(status_code=404, detail="App not installed")
        
    app["launchCount"] += 1
    app["lastLaunchedAt"] = datetime.utcnow().isoformat()
    app["status"] = "RUNNING"
    
    session_id = f"sess_{userId}_{appId}"
    session = {
        "sessionId": session_id,
        "websocketUrl": f"ws://localhost:8000/ws/simulator/{session_id}",
        "previewUrl": app["previewUrl"],
        "state": "RUNNING",
        "startedAt": datetime.utcnow().isoformat(),
        "activeAppId": appId,
        "lastHeartbeat": datetime.utcnow().isoformat()
    }
    SESSIONS[userId] = session
    return session

@router.post("/session/stop")
def stop_session(userId: str = "default"):
    if userId in SESSIONS:
        session = SESSIONS[userId]
        app_id = session.get("activeAppId")
        profile = get_or_create_profile(userId)
        app = next((a for a in profile["installedApps"] if a["appId"] == app_id), None)
        if app:
            app["status"] = "INSTALLED"
        del SESSIONS[userId]
    return {"success": True}

@router.get("/session/status")
def get_session_status(userId: str = "default"):
    if userId not in SESSIONS:
        return {"hasSession": False}
        
    session = SESSIONS[userId]
    return {
        "hasSession": True,
        "sessionId": session["sessionId"],
        "activeAppId": session["activeAppId"],
        "state": session["state"],
        "lastHeartbeat": session["lastHeartbeat"]
    }

@router.get("/devices")
def get_available_devices():
    return DEVICE_PROFILES

@router.get("/admin/usage")
def get_all_usage():
    deployments = []
    for user_id, profile in PROFILES.items():
        for app in profile["installedApps"]:
            deployments.append({
                "appId": app["appId"],
                "deviceType": profile["device"]["type"],
                "previewUrl": app["previewUrl"],
                "status": app["status"],
                "deployedAt": app["installedAt"]
            })
    return {
        "totalDeployments": len(deployments),
        "deployments": deployments
    }

@router.post("/admin/set-quota/{userId}")
def admin_set_quota(userId: str, quota: int):
    profile = get_or_create_profile(userId)
    profile["installQuota"] = max(1, min(20, quota))
    return profile

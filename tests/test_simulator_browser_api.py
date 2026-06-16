from fastapi.testclient import TestClient
import pytest
from core.app import app

client = TestClient(app)

def test_simulator_profile_endpoints():
    # Get Profile
    resp = client.get("/api/simulator/profile?userId=testuser")
    assert resp.status_code == 200
    data = resp.json()
    assert data["userId"] == "testuser"
    assert data["installQuota"] == 5

    # Update Profile
    resp = client.post(
        "/api/simulator/profile?userId=testuser",
        json={"installQuota": 10, "device": {"type": "IPHONE_13"}}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["installQuota"] == 10
    assert data["device"]["type"] == "IPHONE_13"

def test_simulator_install_uninstall():
    # Install app
    resp = client.post("/api/simulator/install?userId=testuser", json={"appId": "myapp"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["app"]["appId"] == "myapp"

    # Get installed
    resp = client.get("/api/simulator/installed?userId=testuser")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["installedApps"]) == 1
    assert data["installedApps"][0]["appId"] == "myapp"

    # Start Session
    resp = client.post("/api/simulator/session/start?appId=myapp&userId=testuser")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "RUNNING"
    assert data["activeAppId"] == "myapp"

    # Session Status
    resp = client.get("/api/simulator/session/status?userId=testuser")
    assert resp.status_code == 200
    data = resp.json()
    assert data["hasSession"] is True
    assert data["activeAppId"] == "myapp"

    # Stop Session
    resp = client.post("/api/simulator/session/stop?userId=testuser")
    assert resp.status_code == 200

    # Uninstall app
    resp = client.delete("/api/simulator/install/myapp?userId=testuser")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

def test_browser_endpoints():
    # Surf Status
    resp = client.get("/api/browser/surf/status")
    assert resp.status_code == 200
    assert resp.json()["browsing"] is False

    # Start Surf
    resp = client.post("/api/browser/surf/start")
    assert resp.status_code == 200

    # Navigate
    resp = client.post("/api/browser/surf/navigate", json={"url": "https://google.com"})
    assert resp.status_code == 200

    # Screenshot
    resp = client.get("/api/browser/surf/screenshot")
    assert resp.status_code == 200
    assert "screenshot" in resp.json()

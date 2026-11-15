from .conftest import ADMIN_HEADERS, client


def test_commandcenter_observe_metrics():
    resp = client.get("/admin-api/commandcenter/observe/metrics", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


def test_commandcenter_observe_logs():
    resp = client.get("/admin-api/commandcenter/observe/logs", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_commandcenter_observe_events():
    resp = client.get("/admin-api/commandcenter/observe/events", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_commandcenter_observe_health():
    resp = client.get("/admin-api/commandcenter/observe/health", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "overall_health_percent" in resp.json()


def test_commandcenter_observe_traffic():
    resp = client.get("/admin-api/commandcenter/observe/traffic", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "current_rps" in resp.json()

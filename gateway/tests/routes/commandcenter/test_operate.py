from .conftest import ADMIN_HEADERS, client


def test_commandcenter_operate_agents():
    resp = client.get("/admin-api/commandcenter/operate/agents", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_commandcenter_operate_swarm():
    resp = client.get("/admin-api/commandcenter/operate/swarm", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "nodes" in resp.json()


def test_commandcenter_operate_tasks():
    resp = client.get("/admin-api/commandcenter/operate/tasks", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_commandcenter_operate_sessions():
    resp = client.get("/admin-api/commandcenter/operate/sessions", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_commandcenter_operate_tenants():
    resp = client.get("/admin-api/commandcenter/operate/tenants", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

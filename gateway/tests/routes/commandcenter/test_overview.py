from .conftest import ADMIN_HEADERS, client


def test_commandcenter_overview_success():
    response = client.get("/admin-api/commandcenter/overview", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "active_agents" in data
    assert "active_tasks" in data
    assert "health_percent" in data
    assert data["health_percent"] is None
    assert data.get("status") == "stub"

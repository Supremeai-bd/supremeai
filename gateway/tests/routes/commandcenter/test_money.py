from .conftest import ADMIN_HEADERS, client


def test_commandcenter_money_cost():
    resp = client.get("/admin-api/commandcenter/money/cost", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "report" in resp.json()


def test_commandcenter_money_usage():
    resp = client.get("/admin-api/commandcenter/money/usage", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "cost_projected_monthly" in resp.json()


def test_commandcenter_money_budget():
    resp = client.get("/admin-api/commandcenter/money/budget", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    post_resp = client.post(
        "/admin-api/commandcenter/money/budget", json={"cap": 100}, headers=ADMIN_HEADERS
    )
    assert post_resp.status_code == 200


def test_commandcenter_money_roi():
    resp = client.get("/admin-api/commandcenter/money/roi", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "semantic_cache_hits" in resp.json()

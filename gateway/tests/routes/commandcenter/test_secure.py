from .conftest import ADMIN_HEADERS, client


def test_commandcenter_secure_threats():
    resp = client.get("/admin-api/commandcenter/secure/threats", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "findings" in resp.json()


def test_commandcenter_secure_rules():
    resp = client.get("/admin-api/commandcenter/secure/rules", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    post_resp = client.post(
        "/admin-api/commandcenter/secure/rules",
        json={"rule_name": "test_rule", "action": "allow", "pattern": ".*"},
        headers=ADMIN_HEADERS,
    )
    assert post_resp.status_code == 200


def test_commandcenter_secure_secrets():
    resp = client.get("/admin-api/commandcenter/secure/secrets", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "secrets" in resp.json()


def test_commandcenter_secure_ratelimits():
    resp = client.get("/admin-api/commandcenter/secure/ratelimits", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "current_429_events" in resp.json()
